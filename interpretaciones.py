"""Interpretaciones y recomendaciones por razón (umbrales referenciales)."""
from ratios import META, nivel, fmt, ICONO

T = {  # id: (qué mide, riesgo si no es favorable, recomendación)
 "l1": ("capacidad de cubrir obligaciones de corto plazo con activos de corto plazo",
        "posible tensión de caja para cumplir obligaciones inmediatas",
        "mejorar la gestión de flujo, acelerar cobranza de primas y escalonar vencimientos de inversiones"),
 "l2": ("recursos inmediatos (caja y bancos) frente a las deudas exigibles",
        "baja liquidez inmediata ante pagos de siniestros o proveedores",
        "mantener un colchón de efectivo y líneas de contingencia para siniestros"),
 "l3": ("cobertura de los pasivos exigibles con el activo circulante",
        "los pasivos exigibles superan la capacidad de pago de corto plazo",
        "reducir pasivos exigibles o reforzar activos líquidos"),
 "l4": ("respaldo de las reservas técnicas con activos de corto plazo",
        "las reservas técnicas no están plenamente respaldadas por activos circulantes",
        "revisar la política de inversión de reservas y su calce de plazos"),
 "s1": ("cuántos pesos de activo respaldan cada peso de pasivo",
        "estructura financiera débil y poco margen ante pérdidas",
        "fortalecer capital (aportaciones o retención de utilidades) y revisar pasivos"),
 "s2": ("respaldo de los pasivos sin reservas técnicas específicas con activos no fijos",
        "activos disponibles insuficientes frente a pasivos distintos a reservas",
        "reducir inmovilizaciones y mejorar la liquidez del activo"),
 "s3": ("apalancamiento operativo: primas retenidas por cada peso de capital",
        "exceso de suscripción para el capital disponible; riesgo de insolvencia",
        "reforzar capital o aumentar la cesión en reaseguro para reducir la retención"),
 "s4": ("holgura del margen de solvencia frente al capital de garantía requerido",
        "margen regulatorio ajustado; riesgo de incumplimiento",
        "capitalizar, reducir riesgos retenidos y monitorear mensualmente el requerimiento"),
 "s5": ("endeudamiento total respecto al capital propio",
        "alto apalancamiento, mayor vulnerabilidad ante desviaciones",
        "capitalizar utilidades y limitar el crecimiento financiado con pasivos"),
 "s6": ("peso de las reservas técnicas sobre el capital",
        "capital reducido para el volumen de compromisos técnicos",
        "evaluar suficiencia de reservas y fortalecer el capital"),
 "p1": ("gasto de operación por cada peso de prima directa",
        "estructura de gastos pesada que erosiona el margen técnico",
        "optimizar gastos administrativos, automatizar procesos y renegociar contratos"),
 "p2": ("costo de adquirir negocio (comisiones, etc.) por peso de prima retenida",
        "comisiones y costos de colocación elevados",
        "revisar esquemas de comisiones y canales de distribución"),
 "p3": ("proporción de la prima devengada que se destina a siniestros retenidos",
        "tarifas posiblemente insuficientes o alta frecuencia/severidad",
        "revisar tarifas, selección de riesgos, deducibles y control de siniestros"),
 "p4": ("resultado técnico global: >100% implica pérdida de suscripción",
        "la prima no cubre siniestros ni costos; depende del producto financiero para generar utilidad",
        "atacar el componente más alto (siniestralidad, adquisición u operación) y ajustar primas"),
 "r1": ("proporción de la prima transferida a reaseguradores",
        "alta dependencia del reaseguro y de la solvencia de los reaseguradores",
        "evaluar retener más en ramos rentables y diversificar reaseguradores"),
 "r2": ("proporción de la prima que la compañía conserva",
        "baja retención reduce el ingreso propio; alta retención aumenta riesgo",
        "calibrar retención según capital y apetito de riesgo"),
 "r3": ("compensación que recibe la compañía por ceder negocio",
        "comisiones bajas frente a la prima cedida",
        "renegociar condiciones de los contratos de reaseguro"),
 "u1": ("rendimiento de la utilidad neta sobre el capital contable (ROE)",
        "rentabilidad baja para el capital invertido",
        "mejorar resultado técnico, rendimiento de inversiones y eficiencia operativa"),
 "u2": ("retorno sobre el capital efectivamente aportado",
        "los accionistas obtienen un retorno bajo",
        "revisar la rentabilidad por ramo y la política de dividendos"),
 "u3": ("retorno sobre capital pagado más reservas de capital",
        "retorno bajo sobre el capital ordinario acumulado",
        "fortalecer utilidades y evaluar la asignación de capital"),
 "u4": ("rentabilidad sobre el capital de trabajo (activo − pasivo circulante)",
        "uso poco productivo de los recursos de corto plazo",
        "optimizar la administración del capital de trabajo"),
}


def tendencia(rid, serie):
    """serie: lista [(periodo, valor)] ordenada. Devuelve texto de tendencia."""
    s = [(p, v) for p, v in serie if v is not None]
    if len(s) < 2:
        return ""
    (p0, v0), (p1, v1) = s[0], s[-1]
    dif = v1 - v0
    if abs(dif) < 1e-9:
        return f"Se mantuvo estable entre {p0} y {p1}."
    mejora = (dif > 0) == (META[rid]["dir"] == "up")
    f = META[rid]["fmt"]
    txt = f"Pasó de {fmt(v0, f)} ({p0}) a {fmt(v1, f)} ({p1}): " + ("**mejora**" if mejora else "**deterioro**") + "."
    mx = max(s, key=lambda x: x[1]); mn = min(s, key=lambda x: x[1])
    return txt + f" Máximo en {mx[0]} ({fmt(mx[1], f)}) y mínimo en {mn[0]} ({fmt(mn[1], f)})."


def interpretar(rid, serie):
    p, v = serie[-1]
    n = nivel(rid, v)
    mide, riesgo, reco = T[rid]
    if v is None:
        return n, "No fue posible calcular la razón: faltan cuentas. Complete los datos en el módulo de carga.", "", ""
    if n == "Favorable":
        txt = f"Con {fmt(v, META[rid]['fmt'])} en {p}, el indicador es favorable: mide {mide} y se ubica en un rango sano."
        rec = "Mantener la práctica actual y monitorear periódicamente."
    else:
        txt = f"Con {fmt(v, META[rid]['fmt'])} en {p}, el nivel es {n.lower()}: mide {mide}; existe {riesgo}."
        rec = reco[0].upper() + reco[1:] + "."
    return n, txt, rec, tendencia(rid, serie)
