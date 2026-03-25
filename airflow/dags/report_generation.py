import os
import sys
import io
import json
import logging
import smtplib
import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Garante que o diretório de plugins está no path do Python
sys.path.insert(0, os.path.join(os.environ.get('AIRFLOW_HOME', '/opt/airflow'), 'plugins'))

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'relatorio',
    'start_date': days_ago(1),
    'email': ['admin@vertti.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

def extract_report_data(**context):
    """
    TASK 1: Extrai dados diretamente do Oracle Database.
    Porta completa de portalCliente::getAnalitic() — sem chamar o PHP.

    Lê o payload do dag_run.conf, conecta no Oracle via oracle_connector,
    executa as 3 queries (dados, mensal, aderência) e agrega os resultados.
    Salva o resultado em XCom para a task de transformação.
    """
    from portal_cliente_extractor import extract_analitic

    dag_run_conf = context['dag_run'].conf
    report_id = dag_run_conf.get('report_id')
    payload = dag_run_conf.get('payload', {})
    cliente = dag_run_conf.get('cliente') or payload.get('cliente')
    if cliente:
        payload['cliente'] = cliente

    logger.info("Iniciando extração para relatório: %s", report_id)
    logger.info("Cliente da extração: %s", cliente)
    logger.info("Período: %s → %s",
                payload.get('periodos', [{}])[0].get('ini'),
                payload.get('periodos', [{}])[0].get('fim'))

    result = extract_analitic(payload)

    # Salva no XCom para próxima task (não serializa GROUPED completo por tamanho)
    summary = {
        'report_id': report_id,
        'VOL_EXP': result['VOL_EXP'],
        'VOL_RCP': result['VOL_RCP'],
        'NR_EXP': result['NR_EXP'],
        'NR_RCP': result['NR_RCP'],
        'RETENCAO': result['RETENCAO'],
        'DESCONTO': result['DESCONTO'],
        'SALDO': result['SALDO'],
        'total_registros': len(result.get('GROUPED', [])),
    }
    logger.info("Extração concluída: %s", summary)

    context['task_instance'].xcom_push(key='oracle_result', value=result)
    context['task_instance'].xcom_push(key='result_summary', value=summary)

    return summary

def _generate_csv(oracle_result, cliente='default'):
    """Gera bytes CSV conforme template por cliente."""
    from client_templates import get_template
    from report_formatter import format_rows_for_output, resolve_label

    template = get_template(cliente)
    headers = template['headers']['csv']
    concat_documentos = template['concatDocumentos']
    rows = oracle_result.get('GROUPED', [])

    col_labels = [resolve_label(h['label']) for h in headers]
    keys = [h['key'] for h in headers]

    output = io.StringIO()
    output.write(';'.join(col_labels) + '\n')

    if rows:
        formatted_rows = format_rows_for_output(rows, headers, concat_documentos)
        for row in formatted_rows:
            output.write(';'.join(str(row.get(k, '')) for k in keys) + '\n')

    return output.getvalue().encode('utf-8-sig')

def _generate_pdf(oracle_result, report_id, cliente='default'):
    """Gera bytes PDF conforme template por cliente."""
    # Compatibilidade com ambientes onde hashlib.md5 nao aceita usedforsecurity.
    import hashlib
    original_md5 = hashlib.md5

    def compat_md5(*args, **kwargs):
        kwargs.pop('usedforsecurity', None)
        return original_md5(*args, **kwargs)

    hashlib.md5 = compat_md5

    from client_templates import get_template
    from report_formatter import format_rows_for_output, resolve_label
    from reportlab.lib.pagesizes import A2, A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.styles import getSampleStyleSheet

    template = get_template(cliente)
    headers = template['headers']['pdf']
    concat_documentos = template['concatDocumentos']
    pdf_style = template.get('pdf_style', {})
    rows = oracle_result.get('GROUPED', [])

    header_color = colors.HexColor(pdf_style.get('header_color', '#003366'))
    row_alt_color = colors.HexColor(pdf_style.get('row_alt_color', '#f0f4f8'))
    grid_color = colors.HexColor(pdf_style.get('grid_color', '#808080'))

    title_text = pdf_style.get('title') or f'Relatório #{report_id}'
    logo_path = pdf_style.get('logo_path') if cliente == 'rhall' else None

    title_font_size = int(pdf_style.get('title_font_size', 15))
    meta_font_size = int(pdf_style.get('meta_font_size', 10))
    summary_font_size = int(pdf_style.get('summary_font_size', 8))
    detail_font_size = int(pdf_style.get('detail_font_size', 7))

    col_labels = [resolve_label(h['label']) for h in headers]
    col_keys = [h['key'] for h in headers]
    col_aligns = [h.get('align', 'left') for h in headers]
    formatted_rows = format_rows_for_output(rows, headers, concat_documentos) if rows else []

    page_format = A2 if len(headers) > 15 else A4

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(page_format), leftMargin=1*cm, rightMargin=1*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    styles['Title'].fontSize = title_font_size
    styles['Normal'].fontSize = meta_font_size
    elements = []

    if logo_path and os.path.exists(logo_path):
        elements.append(Image(logo_path, width=4.2 * cm, height=1.2 * cm))
        elements.append(Spacer(1, 0.25 * cm))

    elements.append(Paragraph(title_text, styles['Title']))
    elements.append(Paragraph(f'Cliente: {cliente}', styles['Normal']))
    elements.append(Paragraph(f'Gerado em: {datetime.now().strftime("%d/%m/%Y %H:%M")}', styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))

    summary = [
        ['Volume Expedido', 'Volume Recebido', 'Nº Expedições', 'Nº Recebimentos', 'Retenção', 'Desconto', 'Saldo'],
        [
            str(oracle_result.get('VOL_EXP', 0)),
            str(oracle_result.get('VOL_RCP', 0)),
            str(oracle_result.get('NR_EXP', 0)),
            str(oracle_result.get('NR_RCP', 0)),
            str(oracle_result.get('RETENCAO', 0)),
            str(oracle_result.get('DESCONTO', 0)),
            str(oracle_result.get('SALDO', 0)),
        ],
    ]
    summary_table = Table(summary, repeatRows=1)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), header_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), summary_font_size),
        ('GRID', (0, 0), (-1, -1), 0.5, grid_color),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, row_alt_color]),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.5*cm))

    if formatted_rows:
        table_data = [col_labels] + [[str(row.get(h, '')) for h in col_keys] for row in formatted_rows]
        detail_table = Table(table_data, repeatRows=1)

        style_rules = [
            ('BACKGROUND', (0, 0), (-1, 0), header_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), detail_font_size),
            ('GRID', (0, 0), (-1, -1), 0.5, grid_color),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, row_alt_color]),
        ]
        for idx, align in enumerate(col_aligns):
            style_rules.append(('ALIGN', (idx, 0), (idx, -1), 'RIGHT' if align == 'right' else 'LEFT'))

        detail_table.setStyle(TableStyle(style_rules))
        elements.append(detail_table)
    else:
        elements.append(Paragraph('Nenhum registro encontrado para o período selecionado.', styles['Normal']))

    try:
        doc.build(elements)
        return buffer.getvalue()
    finally:
        hashlib.md5 = original_md5

def _upload_file_to_nestjs(nestjs_url, report_id, file_bytes, fmt, content_type):
    """Faz upload do arquivo para o NestJS que armazena no OCI bucket."""
    response = requests.post(
        f'{nestjs_url}/api/reports/{report_id}/store',
        params={'format': fmt},
        files={'file': (f'relatorio.{fmt}', file_bytes, content_type)},
        timeout=60,
    )
    response.raise_for_status()
    logger.info("Upload %s realizado com sucesso: %s", fmt.upper(), response.json())

def transform_report_data(**context):
    """
    Gera CSV e PDF a partir dos dados do Oracle e faz upload para o OCI via NestJS.
    """
    task_instance = context['task_instance']
    oracle_result = task_instance.xcom_pull(task_ids='extract_data', key='oracle_result')
    dag_run_conf = context['dag_run'].conf
    report_id = dag_run_conf.get('report_id')
    cliente = dag_run_conf.get('cliente') or (dag_run_conf.get('payload') or {}).get('cliente') or 'default'
    nestjs_url = os.getenv('NESTJS_API_URL', 'http://nestjs-api:3000')

    logger.info("Gerando arquivos para o relatório: %s (cliente=%s)", report_id, cliente)

    csv_bytes = _generate_csv(oracle_result, cliente)
    logger.info("CSV gerado: %d bytes", len(csv_bytes))

    pdf_bytes = _generate_pdf(oracle_result, report_id, cliente)
    logger.info("PDF gerado: %d bytes", len(pdf_bytes))

    _upload_file_to_nestjs(nestjs_url, report_id, csv_bytes, 'csv', 'text/csv')
    _upload_file_to_nestjs(nestjs_url, report_id, pdf_bytes, 'pdf', 'application/pdf')

    transformed_data = {
        'report_id': report_id,
        'status': 'TRANSFORMED',
        'pdf_download_path': f'/api/reports/{report_id}/download/pdf',
        'csv_download_path': f'/api/reports/{report_id}/download/csv',
        'created_at': datetime.now().isoformat(),
    }

    task_instance.xcom_push(key='transformed_data', value=transformed_data)
    logger.info("Transformação concluída: %s", transformed_data)
    return transformed_data
def send_report_to_email(**context):
    """
    Envia relatório por email
    """
    task_instance = context['task_instance']
    transformed_data = task_instance.xcom_pull(task_ids='transform_data', key='transformed_data')
    dag_run_conf = context['dag_run'].conf
    usuario_email = dag_run_conf.get('usuario_email')
    report_id = dag_run_conf.get('report_id')

    smtp_host = os.getenv('SMTP_HOST', '')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USER', '')
    smtp_password = os.getenv('SMTP_PASSWORD', '')
    smtp_from = os.getenv('SMTP_FROM', smtp_user)

    logger.info("Enviando relatório por email para: %s", usuario_email)

    try:
        if not usuario_email:
            raise ValueError('usuario_email não informado no dag_run.conf')
        if not smtp_host or not smtp_user or not smtp_password:
            raise ValueError('Configuração SMTP incompleta: definir SMTP_HOST, SMTP_USER e SMTP_PASSWORD')

        message = MIMEMultipart('alternative')
        message['Subject'] = f'Relatório assíncrono #{report_id} processado'
        message['From'] = smtp_from
        message['To'] = usuario_email

        public_url = os.getenv('REPORTS_PUBLIC_URL', 'http://localhost:3000')
        pdf_url = f"{public_url}{transformed_data.get('pdf_download_path', '')}"
        csv_url = f"{public_url}{transformed_data.get('csv_download_path', '')}"

        body = f"""Olá,

    Seu relatório assíncrono foi processado com sucesso.

    Request ID: {report_id}

    Download PDF:  {pdf_url}
    Download CSV:  {csv_url}

    Os links expiram em 1 hora. Após isso, acesse novamente para gerar um novo link.

    Atenciosamente,
    Velog""".strip()
        message.attach(MIMEText(body, 'plain', 'utf-8'))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [usuario_email], message.as_string())

        logger.info("Email enviado com sucesso para %s", usuario_email)
        task_instance.xcom_push(key='delivery_status', value='DELIVERED')
        return True

    except Exception as e:
        logger.error("Erro ao enviar email: %s", str(e))
        raise

def callback_nestjs_success(**context):
    """
    Chama callback na API NestJS quando tudo OK
    """
    task_instance = context['task_instance']
    transformed_data = task_instance.xcom_pull(task_ids='transform_data', key='transformed_data')
    dag_run_conf = context['dag_run'].conf
    report_id = dag_run_conf.get('report_id')

    nestjs_url = os.getenv('NESTJS_API_URL', 'http://nestjs-api:3000')

    try:
        response = requests.patch(
            f'{nestjs_url}/api/reports/{report_id}/status',
            json={
                'status': 'COMPLETED',
                'airflow_dag_run_id': context['dag_run'].run_id,
                'resultado': transformed_data,
            }
        )
        response.raise_for_status()
        print(f"NestJS callback success for report: {report_id}")

    except Exception as e:
        print(f"Error in NestJS callback: {str(e)}")
        raise

def callback_nestjs_failure(**context):
    """
    Chama callback na API NestJS quando falha
    """
    dag_run_conf = context['dag_run'].conf
    report_id = dag_run_conf.get('report_id')

    exception = context.get('exception')
    error_msg = str(exception) if exception else 'Unknown error'

    nestjs_url = os.getenv('NESTJS_API_URL', 'http://nestjs-api:3000')

    try:
        response = requests.patch(
            f'{nestjs_url}/api/reports/{report_id}/status',
            json={
                'status': 'FAILED',
                'error_message': error_msg,
                'airflow_dag_run_id': context['dag_run'].run_id,
            }
        )
        response.raise_for_status()
        print(f"NestJS callback failure for report: {report_id}")

    except Exception as e:
        print(f"Error in NestJS failure callback: {str(e)}")

# Define DAG
with DAG(
    dag_id='report_generation_dag',
    default_args=default_args,
    description='DAG para gerar relatórios assíncronos',
    schedule_interval=None,  # Only triggered manually via API
    catchup=False,
    tags=['relatorio', 'velog'],
) as dag:

    extract_task = PythonOperator(
        task_id='extract_data',
        python_callable=extract_report_data,
        provide_context=True,
    )

    transform_task = PythonOperator(
        task_id='transform_data',
        python_callable=transform_report_data,
        provide_context=True,
    )

    email_task = PythonOperator(
        task_id='send_email',
        python_callable=send_report_to_email,
        provide_context=True,
    )

    callback_success = PythonOperator(
        task_id='callback_success',
        python_callable=callback_nestjs_success,
        provide_context=True,
        trigger_rule='all_success',
    )

    callback_failure = PythonOperator(
        task_id='callback_failure',
        python_callable=callback_nestjs_failure,
        provide_context=True,
        trigger_rule='one_failed',
    )

    # Task dependencies
    extract_task >> transform_task >> email_task >> [callback_success, callback_failure]
