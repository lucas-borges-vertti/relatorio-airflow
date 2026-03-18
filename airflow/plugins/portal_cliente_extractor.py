"""
Portal Cliente Extractor
Porta de portalCliente::getAnalitic() do PHP para Python nativo com Oracle.
Executa as queries diretamente no Oracle — sem chamar o backend PHP.

Queries portadas:
  1. Main query   → PRT_APR + JOINs (mesmos filtros do PHP)
  2. Monthly agg  → Agrupamento mensal com janela de -3 meses
  3. Aderencia    → PRT_COTA (portado de gerencial::aderencia)
"""
import logging
import re
from typing import Any, Dict, List, Tuple

from oracle_connector import query, build_in_clause, resolve_schema_by_cliente

logger = logging.getLogger(__name__)

_SCHEMA_OBJECTS = [
  'OPR_CN',
  'OPR_CNI',
  'PRT_APR',
  'V_MPR_CLS',
  'PRT_MTRB',
  'PRT_DCO',
  'PRT_DCOI',
  'PDT_PRO',
  'PRC_PESBSC',
  'PDT_CLSI',
  'V_PRT_MTRB',
  'SEG_USR',
  'SIS_DIROBJ',
  'PRT_COTA',
]


def _qualify_sql_with_schema(sql: str, schema: str) -> str:
  """
  Prefixa tabelas/views/funcoes Oracle com o schema do cliente.
  Evita prefixar objetos ja qualificados.
  """
  qualified = sql
  for obj in _SCHEMA_OBJECTS:
    pattern = rf'(?<!\.)\b{obj}\b'
    qualified = re.sub(pattern, f'{schema}.{obj}', qualified, flags=re.IGNORECASE)

  qualified = re.sub(
    r'(?<!\.)\bf_evaluate_exp\b',
    f'{schema}.F_EVALUATE_EXP',
    qualified,
    flags=re.IGNORECASE,
  )
  return qualified

# ---------------------------------------------------------------------------
# SQL principal — portado diretamente do PHP (getAnalitic)
# ---------------------------------------------------------------------------
_MAIN_SQL = """
SELECT
  apr.ID_UOCC,
  apr.DT_PRT,
  apr.ID_VCL,
  apr.TP_OPRPRT,
  apr.TP_PRT,
  apr.CD_STS,
  apr.ID_CN,
  (SELECT NR_DCO FROM OPR_CN WHERE ID_UOCC = apr.ID_CN) NR_DCO_CN,
  pro.nm_prored,
  apr.ID_TRP,
  rmt_dcoi.NM_PES AS NOME_RMT_DOC,
  rmt.NM_PES AS NOME_RMT,
  dst.NM_PES AS NOME_DST,
  dst.NM_PESFSCJRD AS NOME_APELIDO_DST,
  COALESCE(rmt_doc.NM_PESFSCJRD, rmt_doc.NM_PESRED, rmt_doc.NM_PES) AS NOME_COMPLETO_RMT,
  COALESCE(dst.NM_PESFSCJRD, dst.NM_PESRED, dst.NM_PES) AS NOME_COMPLETO_DST,
  COALESCE(rec.NM_PESFSCJRD, rec.NM_PESRED, rec.NM_PES) AS NOME_COMPLETO_REC,
  prcrcb.NM_PES AS NOME_PRCRCB,
  mclsi.VL_CLSI,
  mclsi.ID_CLSI,
  clsi.NM_CLSI,
  clsi.NM_CLSIRED,
  TRP.NM_PES,
  VMTRB.DT_OPR2,
  PRO.ID_UNDMQTD,
  TO_CHAR(MTRB.DT_OPR1, 'DD/MM/YYYY HH24:MI:SS') DT_OPR1H,
  TO_CHAR(MTRB.DT_OPR2, 'DD/MM/YYYY HH24:MI:SS') DT_OPR2H,
  TO_CHAR(dco.DT_DCO, 'DD/MM/YYYY') DT_DCO,
  (SELECT U.NM_USR FROM SEG_USR U WHERE U.ID_USR = mclsi.ID_OPR AND ROWNUM = 1) CLASSIFICADOR,
  (SELECT D.VL_DIR FROM SIS_DIROBJ D WHERE D.ID_OBJ = apr.id_prc AND D.NM_DIR = 'ClassificaGrainT') GRAINT,
  CASE
    WHEN apr.CD_STS IN (4, 5, 1, 2, 3, 20, 60, -1) THEN
      CASE WHEN apr.TP_OPRPRT = 'E' THEN
        CASE WHEN mtrb.QT_PSG < 500 THEN mtrb.QT_PSG * 1000
        ELSE NVL(mtrb.QT_PSG, 0) END
      ELSE
        CASE WHEN apr.TP_OPRPRT = 'R' THEN
          CASE WHEN mtrb.QT_PSG < 500 THEN mtrb.QT_PSG * 1000
          ELSE NVL(mtrb.QT_PSG, 0) END
        ELSE 0 END
      END
    ELSE 0
  END QT_PSG,
  CASE
    WHEN apr.CD_STS IN (4, 5, 1, 2, 3, 20, 60, -1) THEN
      CASE WHEN apr.TP_OPRPRT = 'R' THEN
        CASE WHEN mtrb.QT_ORG < 500 THEN mtrb.QT_ORG * 1000
        ELSE NVL(mtrb.QT_ORG, 0) END
      ELSE 0 END
    ELSE 0
  END QT_ORG,
  (SELECT SUM(VL_ORG)
     FROM PRT_DCOI V
    WHERE V.ID_UPRT = apr.ID_UPRT
      AND V.ID_PRT = apr.ID_PRT
      AND V.DT_PRT = apr.DT_PRT
      AND V.TP_DF = '55'
      AND V.CD_STS <> -3) AS VL_ORG,
  (SELECT LISTAGG(TRIM(V.NR_DCO), ' ') WITHIN GROUP (ORDER BY ID_UOCC) AS NR_DCO
     FROM PRT_DCOI V
    WHERE V.ID_UPRT = apr.ID_UPRT
      AND V.ID_PRT = apr.ID_PRT
      AND V.DT_PRT = apr.DT_PRT
      AND V.TP_DF = '55'
      AND V.CD_STS <> -3) AS NR_DCO,
  (SELECT LISTAGG(TO_CHAR(TRIM(dco.NR_NFE)), ' ') WITHIN GROUP (ORDER BY ID_UOCC) AS NR_NFE
     FROM PRT_DCO dco
    WHERE dco.ID_UPRT = apr.ID_UPRT
      AND dco.ID_PRT = apr.ID_PRT
      AND dco.DT_PRT = apr.DT_PRT
      AND dco.TP_DF = '55'
      AND dco.CD_STS <> -3) AS NR_NFE,
  CASE
    WHEN clsi.NM_CLSIRED LIKE '%AV TO%' THEN 'AVA'
    WHEN clsi.NM_CLSIRED LIKE '%AVARIADOS%' THEN 'AVA'
    WHEN clsi.NM_CLSIRED LIKE '%UMIDADE%' THEN 'UMI'
    WHEN clsi.NM_CLSIRED LIKE '%QUEBRA%' THEN 'QBD'
    WHEN clsi.NM_CLSIRED LIKE '%IMPUREZA%' THEN 'IMP'
    WHEN clsi.NM_CLSIRED LIKE '%ESVERDEADOS%' THEN 'ESV'
    ELSE clsi.NM_CLSIRED
  END TRATADO,
  CASE WHEN apr.TP_VCL = 1 THEN 'FERRO' ELSE 'RODO' END MODAL,
  CASE WHEN apr.TP_OPRPRT = 'R' THEN 'RECEPÇÃO' ELSE 'EXPEDIÇÃO' END OPERACAO,
  CASE WHEN (f_evaluate_exp(replace(replace(rtrim(clsi.DS_RGVLDANM, '.'), ',', '.'), 'valor',
    replace(mclsi.VL_CLSI, ',', '.'))) = 1 AND apr.CD_STS = 1) THEN 1 ELSE 0 END VALIDACAO,
  clsi.DS_RGVLDANM ANORMALIDADE,
  VMTRB.QT_ENT,
  VMTRB.QT_SAI,
  VMTRB.QT_RTN RETENCAO,
  VMTRB.QT_AD DESCONTO
FROM
  PRT_APR apr
LEFT JOIN V_MPR_CLS mclsi
  ON apr.ID_UPRT = mclsi.ID_UDCO
  AND apr.DT_PRT = mclsi.DT_DCO
  AND apr.ID_PRT = mclsi.NR_DCO
  AND mclsi.VL_CLSI IS NOT NULL
  AND mclsi.VL_CLSI NOT IN ('0', '.0', '0.')
  AND (TRANSLATE(mclsi.VL_CLSI, '.1234567890', '.') IN ('.', '', ' ')
    OR TRANSLATE(mclsi.VL_CLSI, '.1234567890', '.') IS NULL)
LEFT JOIN PRT_MTRB mtrb
  ON mtrb.id_uprt = apr.id_uprt
  AND mtrb.id_prt = apr.id_prt
  AND mtrb.dt_prt = apr.dt_prt
LEFT JOIN OPR_CN cn
  ON cn.ID_UOCC = apr.ID_CN
LEFT JOIN OPR_CNI cni
  ON cni.ID_UCN = cn.ID_UCN
  AND cni.DT_CN = cn.DT_CN
  AND cni.NR_CN = cn.NR_CN
LEFT JOIN PRT_DCO dco
  ON dco.ID_UPRT = apr.ID_UPRT
  AND dco.ID_PRT = apr.ID_PRT
  AND dco.DT_PRT = apr.DT_PRT
LEFT JOIN PRT_DCOI dcoi
  ON dcoi.ID_UPRT = apr.ID_UPRT
  AND dcoi.ID_PRT = apr.ID_PRT
  AND dcoi.DT_PRT = apr.DT_PRT
LEFT JOIN PDT_PRO pro
  ON pro.ID_PRO = cni.ID_PRO
LEFT JOIN PRC_PESBSC unid
  ON unid.ID_PES = apr.ID_UPRT
LEFT JOIN PRC_PESBSC prc
  ON prc.ID_PES = apr.id_prc
LEFT JOIN PRC_PESBSC rmt
  ON cn.ID_RMT = rmt.ID_PES
LEFT JOIN PRC_PESBSC rmt_dcoi
  ON rmt_dcoi.ID_PES = dcoi.ID_RMT
LEFT JOIN PRC_PESBSC rmt_doc
  ON dco.ID_RMT = rmt_doc.ID_PES
LEFT JOIN PRC_PESBSC dst
  ON cn.ID_DST = dst.ID_PES
LEFT JOIN OPR_CN opr
  ON opr.ID_UOCC = apr.ID_CN
LEFT JOIN PRC_PESBSC rec
  ON rec.ID_PES = opr.ID_PRCRCB
LEFT JOIN PRC_PESBSC prcrcb
  ON cn.ID_PRCRCB = prcrcb.ID_PES
LEFT JOIN PDT_CLSI clsi
  ON clsi.ID_CLSI = mclsi.ID_CLSI
LEFT JOIN PRC_PESBSC TRP
  ON apr.ID_TRP = TRP.ID_PES
LEFT JOIN V_PRT_MTRB VMTRB
  ON VMTRB.ID_CN = cn.ID_UOCC
  AND VMTRB.CD_STS = -1
  AND VMTRB.ID_UPRT  = apr.ID_UPRT
  AND VMTRB.ID_PRT   = apr.ID_PRT
  AND VMTRB.DT_PRT   = apr.DT_PRT
WHERE
  apr.CD_STS != -3
  AND TRUNC(VMTRB.DT_OPR2) BETWEEN TO_DATE(:DT_CNS_INI, 'YYYY-MM-DD') AND TO_DATE(:DT_CNS_FIM, 'YYYY-MM-DD')
  AND pro.ID_PRO = :ID_PRO
"""

# ---------------------------------------------------------------------------
# SQL agrupamento mensal — portado do segundo query PHP (getAnalitic)
# ---------------------------------------------------------------------------
_MONTH_SQL_BASE = """
SELECT TO_CHAR(v.DT_OPR2, 'YYYY-MM') AS MONTH,
       SUM(v.VL_EXP) AS VL_EXP,
       SUM(v.VL_RCP) AS VL_RCP
FROM (
  SELECT VMTRB.DT_OPR2,
    CASE
      WHEN apr.CD_STS IN (4,5,1,2,3,20,60,-1) AND apr.TP_OPRPRT = 'E' THEN
        CASE WHEN mtrb.QT_PSG < 500 THEN mtrb.QT_PSG * 1000 ELSE NVL(mtrb.QT_PSG, 0) END
      ELSE 0
    END AS VL_EXP,
    CASE
      WHEN apr.CD_STS IN (4,5,1,2,3,20,60,-1) AND apr.TP_OPRPRT = 'R' THEN
        CASE WHEN mtrb.QT_PSG < 500 THEN mtrb.QT_PSG * 1000 ELSE NVL(mtrb.QT_PSG, 0) END
      ELSE 0
    END AS VL_RCP
  FROM PRT_APR apr
  LEFT JOIN PRT_MTRB mtrb
    ON mtrb.id_uprt = apr.id_uprt
    AND mtrb.id_prt = apr.id_prt
    AND mtrb.dt_prt = apr.dt_prt
  LEFT JOIN OPR_CN cn
    ON cn.ID_UOCC = apr.ID_CN
  LEFT JOIN OPR_CNI cni
    ON cni.ID_UCN = cn.ID_UCN
    AND cni.DT_CN = cn.DT_CN
    AND cni.NR_CN = cn.NR_CN
  LEFT JOIN PDT_PRO pro
    ON pro.ID_PRO = cni.ID_PRO
  LEFT JOIN PRC_PESBSC unid
    ON unid.ID_PES = apr.ID_UPRT
  LEFT JOIN PRC_PESBSC prc
    ON prc.ID_PES = apr.id_prc
  LEFT JOIN PRC_PESBSC rmt
    ON cn.ID_RMT = rmt.ID_PES
  LEFT JOIN PRC_PESBSC dst
    ON cn.ID_DST = dst.ID_PES
  LEFT JOIN PRC_PESBSC prcrcb
    ON cn.ID_PRCRCB = prcrcb.ID_PES
  LEFT JOIN V_PRT_MTRB VMTRB
    ON VMTRB.ID_CN = cn.ID_UOCC
    AND VMTRB.CD_STS = -1
    AND VMTRB.ID_UPRT  = apr.ID_UPRT
    AND VMTRB.ID_PRT   = apr.ID_PRT
    AND VMTRB.DT_PRT   = apr.DT_PRT
  WHERE VMTRB.DT_OPR2 BETWEEN
    ADD_MONTHS(TRUNC(TO_DATE(:DT_CNS_INI, 'YYYY-MM-DD'), 'MM'), -3)
    AND LAST_DAY(TO_DATE(:DT_CNS_FIM, 'YYYY-MM-DD'))
    AND apr.CD_STS != -3
    AND pro.ID_PRO = :ID_PRO
"""

# ---------------------------------------------------------------------------
# SQL aderência — portado de gerencial::aderencia() + createWhere()
# ---------------------------------------------------------------------------
_ADERENCIA_SQL_BASE = """
SELECT *
FROM (
  SELECT C.DT_COTA AS DT_ORDEM,
         TO_CHAR(C.DT_COTA, 'DD/MM') AS DS_DATA,
         SUM(CASE WHEN C.ID_COTAPAI IS NULL THEN C.QT_COTA END) AS QT_COTA,
         SUM(A.QT_CNS) AS QT_CNS
  FROM PRT_COTA C
  OUTER APPLY (
    SELECT COUNT(1) AS QT_CNS
    FROM PRT_APR A
    WHERE A.ID_COTA = C.ID_UOCC
      AND A.CD_STS != -3
  ) A
  JOIN LATERAL (
    SELECT COALESCE(P.NM_PESRED, P.NM_PESFSCJRD, P.NM_PES) AS NM_ORI,
           P.IN_UORG
    FROM PRC_PESBSC P
    WHERE P.NR_CPFCNPJ = C.NR_CNPJORI
      AND P.CD_STS != -3
    FETCH FIRST 1 ROW ONLY
  ) ORI ON 1=1
  WHERE C.DT_COTA BETWEEN TO_DATE(:DT_INI, 'YYYY-MM-DD') AND TO_DATE(:DT_FIM, 'YYYY-MM-DD')
    AND C.CD_STS != -3
"""

# ---------------------------------------------------------------------------
# Builder de filtros dinâmicos — replica a lógica do PHP
# ---------------------------------------------------------------------------

def _build_filters(payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """
    Constrói sufixo SQL e params extras com base nos filtros do payload.
    Retorna (sql_suffix, extra_params).
    Replicação direta dos if/foreach do PHP getAnalitic().
    """
    sql_parts: List[str] = []
    params: Dict[str, Any] = {}

    lst_cnpj_und = payload.get('cnpjund') or []
    lst_cnpj_parceiro = payload.get('cnpjparceiro') or []
    lst_cnpj_remetente = payload.get('remetentes') or []
    lst_cnpj_destinatario = payload.get('destinatarios') or []
    lst_cnpj_recebedor = payload.get('recebedores') or []
    operacao = payload.get('operacao', 'T')
    id_rv = payload.get('id_rv', '')
    contrato = payload.get('contrato', '')
    modal = payload.get('modal', 'TODOS')
    aprovacao = payload.get('aprovacoes', None)

    if lst_cnpj_und:
        fragment, new_p = build_in_clause('CNPJ_UND', lst_cnpj_und, params)
        sql_parts.append(f" AND unid.nr_cpfcnpj IN ({fragment})")
        params.update(new_p)

    if lst_cnpj_parceiro:
        fragment, new_p = build_in_clause('CNPJ_PARCEIRO', lst_cnpj_parceiro, params)
        sql_parts.append(f" AND prc.nr_cpfcnpj IN ({fragment})")
        params.update(new_p)

    if lst_cnpj_remetente:
        fragment, new_p = build_in_clause('CNPJ_REMETENTE', lst_cnpj_remetente, params)
        sql_parts.append(f" AND rmt.nr_cpfcnpj IN ({fragment})")
        params.update(new_p)

    if lst_cnpj_destinatario:
        fragment, new_p = build_in_clause('CNPJ_DESTINATARIO', lst_cnpj_destinatario, params)
        sql_parts.append(f" AND dst.nr_cpfcnpj IN ({fragment})")
        params.update(new_p)

    if lst_cnpj_recebedor:
        fragment, new_p = build_in_clause('CNPJ_RECEBEDOR', lst_cnpj_recebedor, params)
        sql_parts.append(f" AND prcrcb.nr_cpfcnpj IN ({fragment})")
        params.update(new_p)

    if aprovacao == 'APROVADOS':
        sql_parts.append("""
          AND (
            (f_evaluate_exp(replace(replace(rtrim(clsi.DS_RGVLDANM, '.'), ',', '.'),
              'valor', replace(mclsi.VL_CLSI, ',', '.'))) != 1)
            OR (
              f_evaluate_exp(replace(replace(rtrim(clsi.DS_RGVLDANM, '.'), ',', '.'),
                'valor', replace(mclsi.VL_CLSI, ',', '.'))) = 1
              AND apr.CD_STS IN (2,3,6,20,-1)
            )
          )
        """)
    elif aprovacao == 'REPROVADOS':
        sql_parts.append("""
          AND (f_evaluate_exp(replace(replace(rtrim(clsi.DS_RGVLDANM, '.'), ',', '.'),
            'valor', replace(mclsi.VL_CLSI, ',', '.'))) = 1)
          AND apr.CD_STS = 1
        """)

    if operacao and operacao != 'T':
        sql_parts.append(" AND apr.TP_OPRPRT = :OPERACAO")
        params['OPERACAO'] = operacao

    if id_rv and str(id_rv).lstrip('-').isdigit():
        sql_parts.append(" AND apr.ID_UOCC = :ID_RV")
        params['ID_RV'] = int(id_rv)

    if contrato and str(contrato).lstrip('-').isdigit():
        sql_parts.append(" AND apr.ID_CN = :CONTRATO")
        params['CONTRATO'] = int(contrato)

    if modal == 'RODO':
        sql_parts.append(" AND apr.TP_VCL != 1")
    elif modal == 'FERRO':
        sql_parts.append(" AND apr.TP_VCL = 1")

    return "".join(sql_parts), params


def _build_aderencia_filters(payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """
    Constrói filtros para a query de aderência.
    Porta gerencial::createWhere() no contexto do portalCliente.
    """
    sql_parts: List[str] = []
    params: Dict[str, Any] = {}

    lst_und = payload.get('cnpjund') or []
    id_pro = payload.get('id_pro')
    operacao = payload.get('operacao')

    if lst_und:
        fragment, new_p = build_in_clause('UND', lst_und, params)
        sql_parts.append(f" AND C.NR_CNPJUND IN ({fragment})")
        params.update(new_p)

    if id_pro:
        sql_parts.append(" AND C.ID_PRO = :ID_PRO_ADR")
        params['ID_PRO_ADR'] = id_pro

    if operacao in ('E', 'R'):
        sql_parts.append(" AND C.TP_OPRPRT = :TP_OP_ADR")
        params['TP_OP_ADR'] = operacao

    return "".join(sql_parts), params


# ---------------------------------------------------------------------------
# Agregação dos resultados — replica o foreach PHP
# ---------------------------------------------------------------------------

def _process_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Processa as linhas retornadas pela query principal,
    replicando o foreach do PHP getAnalitic().
    """
    days: dict = {}
    quality: dict = {}
    grouped: dict = {}
    grouped_month: dict = {}
    processed_tickets: list = []

    volume_expedicao = 0.0
    veiculos_expedicao = 0
    volume_recepcao = 0.0
    volume_recepcao_bruto = 0.0
    veiculos_recepcao = 0
    retencao = 0.0
    desconto = 0.0
    retencao_veiculo = 0
    desconto_veiculo = 0

    for row in rows:
        # --- qualidade ---
        vl_clsi = row.get('VL_CLSI')
        nm_clsired = row.get('NM_CLSIRED')
        if vl_clsi is not None and nm_clsired:
            key = nm_clsired
            if key not in quality:
                quality[key] = {'VALORES': [], 'ANORMALIDADE': False, 'VALIDACAO': []}
            quality[key]['VALORES'].append(vl_clsi)
            quality[key]['ANORMALIDADE'] = row.get('ANORMALIDADE') or False
            quality[key]['VALIDACAO'].append(row.get('VALIDACAO', 0))

        # --- dia ---
        day = row.get('DT_OPR2')
        if day:
            day_str = str(day)[:10] if hasattr(day, '__str__') else day
            if day_str not in days:
                days[day_str] = {'VL_EXP': 0.0, 'VL_RCP': 0.0}

            month = day_str[:7]
            if month not in grouped_month:
                grouped_month[month] = {'MONTH': month, 'VL_EXP': 0.0, 'VL_RCP': 0.0}

        row['NR_NFE'] = f"'{row['NR_NFE']}'" if row.get('NR_NFE') else ''

        ticket_id = row.get('ID_UOCC')
        if ticket_id not in processed_tickets:
            processed_tickets.append(ticket_id)
            qt_psg = float(row.get('QT_PSG') or 0)
            qt_org = float(row.get('QT_ORG') or 0)

            if row.get('TP_OPRPRT') == 'E':
                veiculos_expedicao += 1
                volume_expedicao += qt_psg
                if day and day_str:
                    days[day_str]['VL_EXP'] += qt_psg
                    grouped_month[day_str[:7]]['VL_EXP'] += qt_psg
            else:
                veiculos_recepcao += 1
                volume_recepcao += qt_psg
                volume_recepcao_bruto += qt_org
                if day and day_str:
                    days[day_str]['VL_RCP'] += qt_psg
                    grouped_month[day_str[:7]]['VL_RCP'] += qt_psg

            if row.get('RETENCAO') is not None:
                retencao += float(row['RETENCAO'] or 0)
                retencao_veiculo += 1
            if row.get('DESCONTO') is not None:
                desconto += float(row['DESCONTO'] or 0)
                desconto_veiculo += 1

        # --- grouped ---
        tratado = row.get('TRATADO') or ''
        row['QT_DFO'] = float(row.get('QT_PSG') or 0) - float(row.get('QT_ORG') or 0)
        row['QT_LIQ'] = float(row.get('QT_PSG') or 0) - float(row.get('RETENCAO') or 0)

        if ticket_id not in grouped:
            grouped[ticket_id] = dict(row)

        if tratado:
            grouped[ticket_id][tratado] = vl_clsi

    # Formata dias
    days_return = [{'date': k, **v} for k, v in sorted(days.items())]

    # Formata qualidade
    quality_formatted = []
    for key, q in quality.items():
        vals = [float(v) for v in q['VALORES'] if v is not None]
        if not vals:
            continue
        quality_formatted.append({
            'nome': key,
            'max': max(vals),
            'min': min(vals),
            'avg': int((sum(vals) / len(vals)) * 100) / 100,
            'anormalidade': q['ANORMALIDADE'],
            'anormais': sum(q['VALIDACAO']),
        })

    return {
        'rows': list(grouped.values()),
        'days': days_return,
        'grouped_month': grouped_month,
        'quality': quality_formatted,
        'volume_expedicao': volume_expedicao,
        'veiculos_expedicao': veiculos_expedicao,
        'volume_recepcao': volume_recepcao,
        'volume_recepcao_bruto': volume_recepcao_bruto,
        'veiculos_recepcao': veiculos_recepcao,
        'retencao': retencao,
        'desconto': desconto,
        'retencao_veiculo': retencao_veiculo,
        'desconto_veiculo': desconto_veiculo,
    }


# ---------------------------------------------------------------------------
# Função principal exportada — chamada pelo Airflow task
# ---------------------------------------------------------------------------

def extract_analitic(payload: dict) -> dict:
    """
    Porta completa de portalCliente::getAnalitic($arg) em Python.
    Conecta diretamente no Oracle e retorna o mesmo formato do PHP.

    Args:
        payload: dict equivalente ao $arg do PHP (periodos, id_pro, filtros, etc.)

    Returns:
        dict com chaves: GROUPED, QUALITY, DIA, MES, VOL_EXP, NR_EXP,
                         VOL_RCP, VOL_RCP_BRU, NR_RCP, SALDO, RETENCAO,
                         DESCONTO, RETENCAO_VEICULO, DESCONTO_VEICULO, ADERENCIA
    """
    periodos = payload.get('periodos', [{}])
    cliente = payload.get('cliente')
    dt_ini = periodos[0].get('ini') if periodos else None
    dt_fim = periodos[0].get('fim') if periodos else None
    id_pro = payload.get('id_pro', '-1')
    schema = resolve_schema_by_cliente(cliente)

    if not dt_ini or not dt_fim:
        raise ValueError("Payload deve conter periodos[0].ini e periodos[0].fim")
    if not schema:
      raise ValueError("Nao foi possivel resolver schema Oracle para o cliente informado")

    base_params = {
        'DT_CNS_INI': dt_ini,
        'DT_CNS_FIM': dt_fim,
        'ID_PRO': id_pro,
    }

    filter_sql, filter_params = _build_filters(payload)

    # ---- Query 1: dados principais ----
    main_sql = _qualify_sql_with_schema(_MAIN_SQL + filter_sql, schema)
    main_params = {**base_params, **filter_params}

    logger.info(
      "Executando query principal no Oracle: cliente=%s schema=%s DT_INI=%s DT_FIM=%s ID_PRO=%s",
      cliente,
      schema,
      dt_ini,
      dt_fim,
      id_pro,
    )
    rows = query(main_sql, main_params, cliente=cliente)
    logger.info("Query principal retornou %d registros", len(rows))

    processed = _process_rows(rows)

    # ---- Query 2: agrupamento mensal (janela de -3 meses) ----
    month_sql = _qualify_sql_with_schema(
      _MONTH_SQL_BASE + filter_sql + ") v GROUP BY TO_CHAR(v.DT_OPR2, 'YYYY-MM') ORDER BY month",
      schema,
    )
    logger.info("Executando query mensal no Oracle")
    month_rows = query(month_sql, main_params, cliente=cliente)

    # Mescla meses vindos da query 2 sobre os já calculados no loop principal
    grouped_month = processed['grouped_month']
    for month_data in month_rows:
        month_key = month_data.get('MONTH')
        if month_key:
            grouped_month[month_key] = {
                'MONTH': month_key,
                'VL_EXP': float(month_data.get('VL_EXP') or 0),
                'VL_RCP': float(month_data.get('VL_RCP') or 0),
            }

    month_return = sorted(grouped_month.values(), key=lambda x: x['MONTH'])

    # ---- Query 3: aderência ----
    aderencia_filter_sql, aderencia_extra_params = _build_aderencia_filters(payload)
    aderencia_sql = _qualify_sql_with_schema(
      _ADERENCIA_SQL_BASE + aderencia_filter_sql + " GROUP BY C.DT_COTA ) ORDER BY DT_ORDEM",
      schema,
    )
    aderencia_params = {
        'DT_INI': dt_ini,
        'DT_FIM': dt_fim,
        **aderencia_extra_params,
    }
    logger.info("Executando query de aderência no Oracle")
    aderencia_rows = query(aderencia_sql, aderencia_params, cliente=cliente)

    aderencia = [
        {
            'Data': r['DS_DATA'],
            'Cota': int(r['QT_COTA'] or 0),
            'Consumida': int(r['QT_CNS'] or 0),
        }
        for r in aderencia_rows
    ]

    # ---- Montar retorno no mesmo formato do PHP ----
    vol_rcp = processed['volume_recepcao']
    vol_exp = processed['volume_expedicao']
    retencao = processed['retencao']
    desconto = processed['desconto']

    return {
        'DESCONTO': desconto,
        'DESCONTO_VEICULO': processed['desconto_veiculo'],
        'RETENCAO': retencao,
        'RETENCAO_VEICULO': processed['retencao_veiculo'],
        'MES': month_return,
        'GROUPED': processed['rows'],
        'ADERENCIA': aderencia,
        'VOL_EXP': vol_exp,
        'NR_EXP': processed['veiculos_expedicao'],
        'VOL_RCP': vol_rcp,
        'VOL_RCP_BRU': processed['volume_recepcao_bruto'],
        'SALDO': vol_rcp - vol_exp - retencao - desconto,
        'NR_RCP': processed['veiculos_recepcao'],
        'DIA': processed['days'],
        'QUALITY': processed['quality'],
    }
