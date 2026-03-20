"""
Templates de colunas por cliente para geracao de PDF/CSV.
Portado da logica do frontend (TablePortalCliente/templates).
"""

LABELS = {
    "data": "Data",
    "contrato": "Contrato",
    "situacao": "Situacao",
    "ticket": "Ticket",
    "produto": "Produto",
    "transportador": "Transportador",
    "classificador": "Classificador",
    "un_medida": "Unid. Medida",
    "UMI": "UMI",
    "IMP": "IMP",
    "AVA": "AVA",
    "QBD": "QBD",
    "ESV": "ESV",
    "remetente": "Remetente",
    "destinatario": "Destinatario",
    "recebedor": "Recebedor",
    "operacao": "Operacao",
    "tipo": "Tipo",
    "placa": "Placa",
    "1º Peso": "1o Peso",
    "2º Peso": "2o Peso",
    "documento": "Documento",
    "nr_nfe": "NFe",
    "data_emissao": "Data Emissao",
    "valor": "Valor",
    "peso_origem": "Peso Origem",
    "peso_balanca": "Peso Balanca",
    "diferenca": "Diferenca",
    "retencao": "Retencao",
    "desconto": "Desconto",
    "peso_liquido": "Peso Liquido",
    "remetente_doc": "Remetente/Doc",
    "modal": "Modal",
}

STATUS_LABELS = {
    0: "Pendente",
    1: "Aprovado",
    2: "Reprovado",
    3: "Cancelado",
    4: "Em Andamento",
    5: "Finalizado",
    "A": "Aprovado",
    "P": "Pendente",
    "C": "Cancelado",
    "R": "Reprovado",
}

_DEFAULT_PDF_HEADERS = [
    {"label": "data", "key": "DT_OPR2", "format": "date"},
    {"label": "contrato", "key": "ID_CN", "align": "right"},
    {"label": "operacao", "key": "TP_OPRPRT"},
    {"label": "tipo", "key": "TP_PRT"},
    {"label": "placa", "key": "ID_VCL"},
    {"label": "1º Peso", "key": "DT_OPR1H", "format": "time"},
    {"label": "2º Peso", "key": "DT_OPR2H", "format": "time"},
    {"label": "documento", "key": "NR_DCO", "format": "raw", "align": "right"},
    {"label": "valor", "key": "VL_ORG", "format": "number", "align": "right"},
    {"label": "peso_origem", "key": "QT_ORG", "format": "unit", "align": "right"},
    {"label": "peso_balanca", "key": "QT_PSG", "format": "unit", "align": "right"},
    {"label": "diferenca", "key": "QT_DFO", "format": "unit", "align": "right"},
    {"label": "retencao", "key": "RETENCAO", "format": "unit", "align": "right"},
    {"label": "desconto", "key": "DESCONTO", "format": "unit", "align": "right"},
    {"label": "peso_liquido", "key": "QT_LIQ", "format": "unit", "align": "right"},
]

_DEFAULT_CSV_HEADERS = [
    {"label": "data", "key": "DT_OPR2", "format": "date"},
    {"label": "contrato", "key": "ID_CN", "align": "right"},
    {"label": "remetente", "key": "NOME_RMT"},
    {"label": "destinatario", "key": "NOME_DST"},
    {"label": "recebedor", "key": "NOME_PRCRCB"},
    {"label": "operacao", "key": "TP_OPRPRT"},
    {"label": "tipo", "key": "TP_PRT"},
    {"label": "placa", "key": "ID_VCL"},
    {"label": "1º Peso", "key": "DT_OPR1H", "format": "time"},
    {"label": "2º Peso", "key": "DT_OPR2H", "format": "time"},
    {"label": "documento", "key": "NR_DCO", "format": "raw", "align": "right"},
    {"label": "nr_nfe", "key": "NR_NFE", "format": "raw"},
    {"label": "data_emissao", "key": "DT_DCO"},
    {"label": "valor", "key": "VL_ORG", "format": "number", "align": "right"},
    {"label": "peso_origem", "key": "QT_ORG", "format": "unit", "align": "right"},
    {"label": "peso_balanca", "key": "QT_PSG", "format": "unit", "align": "right"},
    {"label": "diferenca", "key": "QT_DFO", "format": "unit", "align": "right"},
    {"label": "retencao", "key": "RETENCAO", "format": "unit", "align": "right"},
    {"label": "desconto", "key": "DESCONTO", "format": "unit", "align": "right"},
    {"label": "peso_liquido", "key": "QT_LIQ", "format": "unit", "align": "right"},
]

_FULL_HEADERS = [
    {"label": "data", "key": "DT_OPR2", "format": "date"},
    {"label": "contrato", "key": "ID_CN", "align": "right"},
    {"label": "situacao", "key": "CD_STS", "format": "status"},
    {"label": "ticket", "key": "ID_UOCC"},
    {"label": "produto", "key": "NM_PRORED"},
    {"label": "transportador", "key": "NM_PES"},
    {"label": "classificador", "key": "CLASSIFICADOR"},
    {"label": "un_medida", "key": "ID_UNDMQTD"},
    {"label": "UMI", "key": "UMI"},
    {"label": "IMP", "key": "IMP"},
    {"label": "AVA", "key": "AVA"},
    {"label": "QBD", "key": "QBD"},
    {"label": "ESV", "key": "ESV"},
    {"label": "remetente", "key": "NOME_RMT"},
    {"label": "destinatario", "key": "NOME_DST"},
    {"label": "recebedor", "key": "NOME_PRCRCB"},
    {"label": "operacao", "key": "TP_OPRPRT"},
    {"label": "tipo", "key": "TP_PRT"},
    {"label": "placa", "key": "ID_VCL"},
    {"label": "1º Peso", "key": "DT_OPR1H", "format": "time"},
    {"label": "2º Peso", "key": "DT_OPR2H", "format": "time"},
    {"label": "documento", "key": "NR_DCO", "format": "raw", "align": "right"},
    {"label": "nr_nfe", "key": "NR_NFE", "format": "raw"},
    {"label": "data_emissao", "key": "DT_DCO"},
    {"label": "valor", "key": "VL_ORG", "format": "number", "align": "right"},
    {"label": "peso_origem", "key": "QT_ORG", "format": "unit", "align": "right"},
    {"label": "peso_balanca", "key": "QT_PSG", "format": "unit", "align": "right"},
    {"label": "diferenca", "key": "QT_DFO", "format": "unit", "align": "right"},
    {"label": "retencao", "key": "RETENCAO", "format": "unit", "align": "right"},
    {"label": "desconto", "key": "DESCONTO", "format": "unit", "align": "right"},
    {"label": "peso_liquido", "key": "QT_LIQ", "format": "unit", "align": "right"},
]

_RHALL_PDF_HEADERS = [
    {"label": "data", "key": "DT_OPR2", "format": "date"},
    {"label": "contrato", "key": "ID_CN", "align": "right"},
    {"label": "produto", "key": "NM_PRORED"},
    {"label": "remetente_doc", "key": "NOME_COMPLETO_RMT"},
    {"label": "destinatario", "key": "NOME_COMPLETO_DST"},
    {"label": "recebedor", "key": "NOME_COMPLETO_REC"},
    {"label": "operacao", "key": "TP_OPRPRT"},
    {"label": "tipo", "key": "TP_PRT"},
    {"label": "placa", "key": "ID_VCL"},
    {"label": "1º Peso", "key": "DT_OPR1H", "format": "datetime"},
    {"label": "2º Peso", "key": "DT_OPR2H", "format": "datetime"},
    {"label": "documento", "key": "NR_DCO", "format": "raw", "align": "right"},
    {"label": "valor", "key": "VL_ORG", "format": "number", "align": "right"},
    {"label": "peso_origem", "key": "QT_ORG", "format": "unit", "align": "right"},
    {"label": "peso_balanca", "key": "QT_PSG", "format": "unit", "align": "right"},
    {"label": "diferenca", "key": "QT_DFO", "format": "unit", "align": "right"},
    {"label": "retencao", "key": "RETENCAO", "format": "unit", "align": "right"},
    {"label": "desconto", "key": "DESCONTO", "format": "unit", "align": "right"},
    {"label": "peso_liquido", "key": "QT_LIQ", "format": "unit", "align": "right"},
]

_RHALL_CSV_HEADERS = _RHALL_PDF_HEADERS + [
    {"label": "nr_nfe", "key": "NR_NFE", "format": "raw"},
    {"label": "data_emissao", "key": "DT_DCO"},
]

TEMPLATES = {
    "default": {
        "headers": {"pdf": _DEFAULT_PDF_HEADERS, "csv": _DEFAULT_CSV_HEADERS},
        "concatDocumentos": False,
    },
    "alvorada": {
        "headers": {"pdf": _FULL_HEADERS, "csv": _FULL_HEADERS},
        "concatDocumentos": True,
    },
    "alvorada_gerencial": {
        "headers": {"pdf": _FULL_HEADERS, "csv": _FULL_HEADERS},
        "concatDocumentos": True,
    },
    "chs": {
        "headers": {"pdf": _FULL_HEADERS, "csv": _FULL_HEADERS},
        "concatDocumentos": True,
    },
    "chs_teste": {
        "headers": {"pdf": _FULL_HEADERS, "csv": _FULL_HEADERS},
        "concatDocumentos": True,
    },
    "rhall": {
        "headers": {"pdf": _RHALL_PDF_HEADERS, "csv": _RHALL_CSV_HEADERS},
        "concatDocumentos": True,
    },
}

_FULL_TEMPLATE_CLIENTS = {
    "3tentos", "3tentos_hom", "3tentos_teste",
    "agrofel", "agrofel_hom",
    "bocchi", "bocchi_hom",
    "brancoperes", "brancoperes_hom",
    "cotrijal_hom",
    "cvale", "cvale_hom",
    "gnova", "gnova_hom",
    "jbs_hom",
    "norte", "norte_hom",
    "potencial", "potencial_hom",
    "ricolog",
    "rumo", "rumo_hom",
    "santahelena", "santahelena_hom",
    "savixx",
    "seara",
    "sucden",
    "tradicao", "tradicao_hom",
    "vertti",
    "viterra", "viterra_hom",
    "zll",
    "dev",
}


def get_template(cliente: str) -> dict:
    """Retorna o template para o cliente com fallback para default."""
    if cliente in TEMPLATES:
        return TEMPLATES[cliente]

    if cliente in _FULL_TEMPLATE_CLIENTS:
        return {
            "headers": {"pdf": _FULL_HEADERS, "csv": _FULL_HEADERS},
            "concatDocumentos": True,
        }

    return TEMPLATES["default"]
