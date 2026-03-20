"""
Formatadores e montagem de linhas para exportacao de relatorio.
Portado da logica de TablePortalCliente/index.jsx + utils/formatters.js.
"""

from datetime import datetime
from client_templates import LABELS, STATUS_LABELS


def apply_format(value, format_type: str = None) -> str:
    """Formata um valor conforme o tipo definido no template."""
    if value is None:
        return ""

    if format_type == "date":
        if isinstance(value, str):
            try:
                return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                return str(value)
        return str(value)

    if format_type == "datetime":
        return str(value)

    if format_type == "time":
        if isinstance(value, str):
            parts = value.split(" ")
            if len(parts) >= 2:
                return parts[1][:5]
        return str(value)

    if format_type == "number":
        try:
            num = float(str(value).replace(",", "."))
            return f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return str(value)

    if format_type == "unit":
        try:
            num = float(str(value).replace(",", "."))
            return f"{num:,.0f}".replace(",", ".")
        except Exception:
            return str(value)

    if format_type == "status":
        try:
            key = int(value) if str(value).lstrip("-").isdigit() else str(value)
        except Exception:
            key = str(value)
        return STATUS_LABELS.get(key, str(value))

    return str(value)


def resolve_label(label: str) -> str:
    """Traduz a chave de label para texto legivel."""
    return LABELS.get(label, label)


def expand_rows(rows: list, concat_documentos: bool) -> list:
    """
    Replica a regra do frontend:
    - concatDocumentos=True: mantem as linhas
    - concatDocumentos=False: explode NR_DCO/NR_NFE quando houver valores com espaco
    """
    if concat_documentos:
        return rows

    keys_to_split = ["NR_DCO", "NR_NFE"]
    out = []

    for row in rows:
        should_split = any(
            isinstance(row.get(k), str) and " " in (row.get(k) or "")
            for k in keys_to_split
        )

        if not should_split:
            out.append(row)
            continue

        split_values = {}
        for key in keys_to_split:
            raw = row.get(key) or ""
            values = raw.split(" ") if isinstance(raw, str) and raw else [raw]
            if key == "NR_NFE":
                values = [f"'{v.strip(chr(39))}'" for v in values]
            split_values[key] = values

        max_len = max(len(v) for v in split_values.values()) if split_values else 1

        for i in range(max_len):
            nr = dict(row)
            for key in keys_to_split:
                vals = split_values.get(key, [])
                nr[key] = vals[i] if i < len(vals) else ""
            out.append(nr)

    return out


def format_rows_for_output(rows: list, headers: list, concat_documentos: bool) -> list:
    """Aplica expansao + formatacao por coluna conforme template."""
    expanded = expand_rows(rows, concat_documentos)
    formatted_rows = []

    for row in expanded:
        fr = {}
        for h in headers:
            key = h["key"]
            fr[key] = apply_format(row.get(key), h.get("format"))
        formatted_rows.append(fr)

    return formatted_rows
