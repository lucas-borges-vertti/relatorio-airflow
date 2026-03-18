import os
import sys
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

def transform_report_data(**context):
    """
    Transforma dados extraídos do Oracle em PDF/XML.
    """
    task_instance = context['task_instance']
    oracle_result = task_instance.xcom_pull(task_ids='extract_data', key='oracle_result')
    dag_run_conf = context['dag_run'].conf
    report_id = dag_run_conf.get('report_id')

    print(f"Transforming data for report: {report_id}")

    try:
        # Aqui entra a lógica de transformação
        # Por enquanto, apenas simulamos o resultado
        transformed_data = {
            'report_id': report_id,
            'status': 'TRANSFORMED',
            'pdf_url': f'/reports/{report_id}/relatorio.pdf',
            'xml_url': f'/reports/{report_id}/relatorio.xml',
            'created_at': datetime.now().isoformat(),
        }

        task_instance.xcom_push(key='transformed_data', value=transformed_data)
        print(f"Data transformed successfully")
        return transformed_data

    except Exception as e:
        print(f"Error transforming data: {str(e)}")
        raise

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

        body = f"""
Olá,

Seu relatório assíncrono foi processado.

Request ID: {report_id}
PDF: {transformed_data.get('pdf_url')}
XML: {transformed_data.get('xml_url')}

Atenciosamente,
Velog
""".strip()

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
