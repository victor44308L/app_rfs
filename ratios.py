"""Cálculo de las 21 razones financieras y su semaforización."""
import math
from extractor import CUENTAS, COMPUESTAS


def _d(a, b):
    if a is None or b is None or b == 0 or math.isnan(a) or math.isnan(b):
        return None
    return a / b


def _r(a, b):
    return None if a is None or b is None else a - b


def _s(*x):
    return None if any(i is None for i in x) else sum(x)


def base(v, k=1.0):
    g = lambda c: (None if v.get(c) is None or (isinstance(v[c], float) and math.isnan(v[c])) else v[c])
    d = {c: g(c) for c in CUENTAS}
    for cuenta, comps in COMPUESTAS.items():
        if d.get(cuenta) is None:
            vals = [d[c] for c in comps if d.get(c) is not None]
            if vals:
                d[cuenta] = sum(vals)
    d["pe"] = d["pasivo_exigible"] if d["pasivo_exigible"] is not None else _r(d["pasivo_total"], d["reservas_tecnicas"])
    d["pc"] = d["pasivo_circulante"] if d["pasivo_circulante"] is not None else d["pe"]
    d["ac"] = d["activo_circulante"] if d["activo_circulante"] is not None else _r(d["activo_total"], d["activo_fijo"])
    d["pd"] = d["prima_directa"] if d["prima_directa"] is not None else d["prima_emitida"]
    d["pem"] = d["prima_emitida"] if d["prima_emitida"] is not None else d["pd"]
    d["pret"] = d["prima_retenida"] if d["prima_retenida"] is not None else _r(d["pem"], d["prima_cedida"])
    d["ct"] = d["capital_trabajo"] if d["capital_trabajo"] is not None else _r(d["ac"], d["pc"])
    d["un"] = None if d["utilidad_neta"] is None else d["utilidad_neta"] * k
    return d


# id, categoría, nombre, fórmula, formato, dirección, bueno, aceptable, función
R = [
 ("l1", "Liquidez", "Activo circulante / Pasivo circulante", "x", "up", 1.5, 1.0, lambda d: _d(d["ac"], d["pc"])),
 ("l2", "Liquidez", "Activo disponible / Pasivo exigible", "x", "up", .15, .05, lambda d: _d(d["activo_disponible"], d["pe"])),
 ("l3", "Liquidez", "Activo circulante / Pasivo exigible", "x", "up", 1.5, 1.0, lambda d: _d(d["ac"], d["pe"])),
 ("l4", "Liquidez", "Activo circulante / Reservas técnicas", "x", "up", 1.1, 1.0, lambda d: _d(d["ac"], d["reservas_tecnicas"])),
 ("s1", "Solvencia y apalancamiento", "Activo total / Pasivo total", "x", "up", 1.3, 1.1, lambda d: _d(d["activo_total"], d["pasivo_total"])),
 ("s3", "Solvencia y apalancamiento", "Prima retenida / (Capital contable + Rva. previsión)", "x", "down", 3, 5,
  lambda d: _d(d["pret"], _s(d["capital_contable"], d["rva_prevision"]))),
 ("s5", "Solvencia y apalancamiento", "Pasivo total / Capital contable", "x", "down", 4, 7, lambda d: _d(d["pasivo_total"], d["capital_contable"])),
 ("s6", "Solvencia y apalancamiento", "Reservas técnicas / Capital contable", "x", "down", 3, 6, lambda d: _d(d["reservas_tecnicas"], d["capital_contable"])),
 ("p1", "Suficiencia de la prima", "Costo medio de operación = Costo operación / Prima directa", "%", "down", .15, .25, lambda d: _d(d["costo_operacion"], d["pd"])),
 ("p2", "Suficiencia de la prima", "Costo medio de adquisición = Costo neto adquisición / Prima retenida", "%", "down", .20, .30, lambda d: _d(d["costo_adq"], d["pret"])),
 ("p3", "Suficiencia de la prima", "Costo medio de siniestralidad = Siniestro retención / Prima devengada retención", "%", "down", .60, .70,
  lambda d: _d(d["siniestro_ret"], d["prima_dev_ret"])),
 ("p4", "Suficiencia de la prima", "Índice combinado (Op. + Adq. + Sin.)", "%", "down", .95, 1.0, None),
 ("r1", "Reaseguro", "Prima cedida / Prima emitida", "%", "down", .40, .60, lambda d: _d(d["prima_cedida"], d["pem"])),
 ("r2", "Reaseguro", "Prima retenida / Prima emitida", "%", "up", .60, .40, lambda d: _d(d["pret"], d["pem"])),
 ("r3", "Reaseguro", "Comisión de reaseguro cedido / Prima cedida", "%", "up", .20, .10, lambda d: _d(d["comision_rea"], d["prima_cedida"])),
 ("u1", "Rentabilidad", "Utilidad neta / Capital contable", "%", "up", .12, .05, lambda d: _d(d["un"], d["capital_contable"])),
 ("u2", "Rentabilidad", "Utilidad neta / Capital pagado", "%", "up", .12, .05, lambda d: _d(d["un"], d["capital_pagado"])),
 ("u3", "Rentabilidad", "Utilidad neta / (Capital pagado + Rva. de capital)", "%", "up", .10, .04,
  lambda d: _d(d["un"], _s(d["capital_pagado"], d["reserva_capital"]))),
 ("u4", "Rentabilidad", "Utilidad neta / Capital de trabajo", "%", "up", .10, .04, lambda d: _d(d["un"], d["ct"])),
]
META = {r[0]: dict(id=r[0], cat=r[1], nombre=r[2], fmt=r[3], dir=r[4], bueno=r[5], ok=r[6]) for r in R}
CATEGORIAS = list(dict.fromkeys(r[1] for r in R))


def calcular(valores, k=1.0):
    d = base(valores, k)
    out = {r[0]: (r[7](d) if r[7] else None) for r in R}
    if None not in (out["p1"], out["p2"], out["p3"]):
        out["p4"] = out["p1"] + out["p2"] + out["p3"]
    return out


def nivel(rid, val):
    if val is None:
        return None
    m = META[rid]
    if m["dir"] == "up":
        return "Favorable" if val >= m["bueno"] else "Aceptable" if val >= m["ok"] else "Crítico"
    return "Favorable" if val <= m["bueno"] else "Aceptable" if val <= m["ok"] else "Crítico"


ICONO = {"Favorable": "🟢", "Aceptable": "🟡", "Crítico": "🔴", None: "⚪"}


def fmt(val, f):
    if val is None:
        return "—"
    return f"{val*100:,.2f}%" if f == "%" else f"{val:,.2f}x"
