"""Lectura de PDFs y detección automática de cuentas y montos."""
import io, re, unicodedata
import pdfplumber

CUENTAS = {
    "activo_total": "Activo total", "activo_circulante": "Activo circulante",
    "activo_disponible": "Activo disponible (disponibilidad)", "activo_fijo": "Activo fijo",
    "pasivo_total": "Pasivo total", "pasivo_circulante": "Pasivo circulante",
    "pasivo_exigible": "Pasivo exigible", "reservas_tecnicas": "Reservas técnicas",
    "rva_prevision": "Reserva de previsión", "rva_riesgos": "Reserva de riesgos en curso",
    "capital_contable": "Capital contable", "capital_pagado": "Capital pagado",
    "reserva_capital": "Reservas de capital",
    "prima_directa": "Prima directa",
    "prima_emitida": "Prima emitida", "prima_cedida": "Prima cedida",
    "prima_retenida": "Prima retenida", "prima_dev_ret": "Prima devengada de retención",
    "costo_operacion": "Costo de operación", "costo_adq": "Costo neto de adquisición",
    "siniestro_ret": "Siniestro de retención", "comision_rea": "Comisión por reaseguro cedido",
    "utilidad_neta": "Utilidad neta", "capital_trabajo": "Capital de trabajo",
}
# "$" al final = coincidencia exacta; sin "$" = el rótulo empieza con el alias
ALIASES = {
    "activo_total": ["activo$", "activo total", "suma del activo"],
    "activo_circulante": ["activo circulante", "activo corriente"],
    "activo_disponible": ["disponibilidad", "caja y bancos", "efectivo y equivalentes", "disponible$"],
    "activo_fijo": ["inmuebles mobiliario y equipo", "mobiliario y equipo", "activo fijo", "propiedades mobiliario y equipo"],
    "pasivo_total": ["pasivo$", "pasivo total", "suma del pasivo"],
    "pasivo_exigible": ["suma del pasivo"],
    "reservas_tecnicas": ["reservas tecnicas", "reserva tecnica"],
    "rva_prevision": ["reserva de riesgos catastroficos", "reserva de prevision", "reservas de prevision"],
    "rva_riesgos": ["de riesgos en curso$", "reserva de riesgos en curso", "reservas de riesgos en curso"],
    "rva_opc": ["reservas para obligaciones pendientes de cumplir", "reserva para obligaciones pendientes de cumplir", "obligaciones pendientes de cumplir"],
    "capital_contable": ["capital$", "capital contable"],
    "capital_pagado": ["capital o fondo social pagado", "capital pagado", "capital social pagado", "capital social"],
    "reserva_capital": ["reservas$", "reservas de capital", "reserva de capital"],
    "margen_solvencia": ["margen de solvencia"],
    "capital_garantia": ["capital minimo de garantia", "capital de garantia"],
    "prima_directa": ["prima directa", "primas directas", "primas del seguro directo"],
    "prima_emitida": ["emitidas$", "primas emitidas", "prima emitida"],
    "prima_cedida": ["cedidas$", "primas cedidas", "prima cedida"],
    "prima_retenida": ["de retencion$", "prima retenida", "primas retenidas", "prima de retencion"],
    "prima_dev_ret": ["primas de retencion devengadas", "prima devengada de retencion", "primas devengadas de retencion",
                      "prima devengada retenida", "prima de retencion devengada"],
    "costo_operacion": ["costo de operacion", "costos de operacion", "gastos de operacion"],
    "costo_adq": ["costo neto de adquisicion"],
    "siniestro_ret": ["costo neto de siniestralidad", "siniestros de retencion",
                      "siniestralidad y otras obligaciones contractuales", "siniestralidad retenida"],
    "comision_rea": ["comisiones por reaseguro cedido", "comision de reaseguro cedido",
                     "comisiones por reaseguro y reafianzamiento cedido"],
    "utilidad_neta": ["resultado o remanente del ejercicio"],
    "capital_trabajo": ["capital de trabajo"],
}
CUENTAS.update({
    "inversiones_corto": "Valores y operaciones con productos derivados",
    "credito": "Cartera de crédito (neto)", "deudores": "Deudores",
    "reas_reaf": "Reaseguradores y reafianzadores (neto)",
    "rva_por_cumplir": "Reservas para obligaciones por cumplir" ,
    "acreedores": "Acreedores",
    "reas_reaf_pass": "Reaseguradores y reafianzadores"  ,
    "otros_pasivos": "Otros pasivos" 
})
ALIASES.update({
    "inversiones_corto": ["valores y operaciones con producto derivados", "valores y operaciones con productos derivados"],
    "credito": ["cartera de credito neto"],
    "deudores": ["deudores$"],
    "reas_reaf": ["reaseguradores y reafianzadores neto"],

    "rva_por_cumplir": ["reservas para obligaciones pendientes de cumplir$"],
    "acreedores":["acreedores"],
    "reas_reaf_pass": ["reaseguradores y reafianzadores"],
    "otros_pasivos": ["otros pasivos"]
    
})

# cuenta_resultante: [cuentas que se suman si el PDF no la trae directamente]
COMPUESTAS = {
    "activo_circulante": ["inversiones_corto", "activo_disponible", "credito", "deudores", "reas_reaf"],
    "pasivo_circulante": ["rva_por_cumplir", "acreedores", "reas_reaf_pass", "otros_pasivos"]
}

MESES = {m: i + 1 for i, m in enumerate(
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split())}
NUM = re.compile(r"\(?-?\$?\s?\d[\d,]*(?:\.\d+)?\)?")


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9$ ]", " ", s)).strip()


def _num(tok):
    neg = tok.strip().startswith("(") or "-" in tok
    d = re.sub(r"[^\d.]", "", tok)
    try:
        v = float(d)
    except ValueError:
        return None
    return -v if neg else v


def _match(label):
    best, blen = None, 0
    for key, als in ALIASES.items():
        for a in als:
            ok = label == a[:-1] if a.endswith("$") else (label == a or label.startswith(a + " "))
            if ok and len(a) > blen:
                best, blen = key, len(a)
    return best


def detectar_periodo(texto):
    t = norm(texto[:4000])
    ms = re.findall(r"(\d{1,2}) de ([a-z]+) (?:de |del )?(20\d{2})", t)
    fechas = [(int(y), MESES[m]) for _, m, y in ms if m in MESES]
    return max(fechas) if fechas else None


GRUPO = re.compile(r"(?:\(?-?\$?\d[\d,]*(?:\.\d+)?\)?[ \t]*)+")


def segmentos(linea):
    """Una línea puede traer varias parejas 'nombre + monto' (Activo | Pasivo)."""
    out, pos = [], 0
    for m in GRUPO.finditer(linea):
        out.append((linea[pos:m.start()], NUM.findall(m.group())))
        pos = m.end()
    return out


def extraer(pdf_bytes, columna=0):
    """Devuelve (hallazgos, periodo, hay_texto). hallazgos = {cuenta: (valor, segmento_origen)}"""
    hallazgos, texto = {}, ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            texto += (page.extract_text() or "") + "\n"
    for linea in texto.splitlines():
        for etiqueta, toks in segmentos(linea):
            if len(toks) > 1 and "," not in toks[0] and "." not in toks[0] and abs(_num(toks[0]) or 0) < 100:
                toks = toks[1:]  # referencia de nota
            etiqueta = norm(etiqueta)
            etiqueta = re.sub(r"^(total de la|total del|total de|total|suma de la|suma del|suma de|suma)\s+", "", etiqueta)
            if not etiqueta or "y capital" in etiqueta or not toks:
                continue
            key = _match(etiqueta)
            if key and key not in hallazgos:
                v = _num(toks[min(columna, len(toks) - 1)])
                if v is not None:
                    hallazgos[key] = (v, f"{etiqueta} {toks[0]}")
    return hallazgos, detectar_periodo(texto), len(texto.strip()) > 0
