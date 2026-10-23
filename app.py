"""APP_RF Análisis financiero para aseguradoras mediante razones financieras."""
import io
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from extractor import CUENTAS, extraer
from ratios import R, META, CATEGORIAS, ICONO, calcular, nivel, fmt, base
from interpretaciones import interpretar

st.set_page_config(page_title="APP_RF", page_icon="elemen_graf/analitica.png", layout="wide")
st.title("SISTEMA ANALISIS FINANCIERO")

if "periodos" not in st.session_state:
    st.session_state.periodos = {}  # etiqueta -> {"orden": "YYYY-MM", "valores": {...}}

# ------------------------- Configuración lateral -------------------------
with st.sidebar:
    st.header("⚙️ Configuración")
    unidad = st.selectbox("Unidad de los PDFs", ["Pesos", "Miles de pesos", "Millones de pesos"])
    mult = {"Pesos": 1, "Miles de pesos": 1e3, "Millones de pesos": 1e6}[unidad]
    columna = st.radio("Columna a leer en el PDF", ["Primera (periodo actual)", "Segunda (periodo anterior)"])
    col_idx = 0 if columna.startswith("Primera") else 1
    anualizar = st.checkbox("Anualizar rentabilidad (resultados acumulados)", False,
                            help="Multiplica la utilidad neta por 12/mes del periodo.")
    if st.button("🗑️ Borrar todos los periodos"):
        st.session_state.periodos = {}
        st.rerun()
    st.caption("Periodos guardados: " + (", ".join(sorted(st.session_state.periodos)) or "ninguno"))

tab1, tab2, tab3 = st.tabs(["📥 CARGA DE DATOS", "📈 DASHBOARD", "🧠 INTERPRETACION"])


@st.cache_data(show_spinner="Leyendo PDF…")
def leer(pdf_bytes, col):
    return extraer(pdf_bytes, col)


# ------------------------------ Módulo 1: carga ------------------------------
with tab1:
    c1, c2, c3 = st.columns(3)
    period = c1.selectbox("Periodo de la información", ["Mensual", "Trimestral", "Semestral", "Anual"])
    n = c2.number_input("Cantidad de periodos a cargar", 1, 60, 1)
    y0 = c3.number_input("Año inicial", 1990, 2100, 2025)
    paso = {"Mensual": 1, "Trimestral": 3, "Semestral": 6, "Anual": 12}[period]

    for i in range(int(n)):
        tot = paso * (i + 1)
        y_def, m_def = int(y0) + (tot - 1) // 12, (tot - 1) % 12 + 1
        with st.expander(f"Periodo {i+1} de {int(n)}", expanded=(i == 0)):
            f = st.file_uploader("Sube el PDF (estados financieros)", type="pdf", key=f"f{i}")
            if not f:
                continue
            hall, det, hay_texto = leer(f.getvalue(), col_idx)
            if not hay_texto:
                st.error("El PDF no contiene texto (¿escaneado?). Se requiere OCR o captura manual.")
            y_det, m_det = det if det else (y_def, m_def)
            a, b = st.columns(2)
            y = a.number_input("Año", 1990, 2100, y_det, key=f"y{i}{f.name}")
            m = b.number_input("Mes de cierre", 1, 12, m_det, key=f"m{i}{f.name}")
            st.caption(f"Cuentas detectadas: {len(hall)} de {len(CUENTAS)}. Revisa y corrige los valores si es necesario.")
            df = pd.DataFrame([{"id": k, "Cuenta": v, "Valor": hall.get(k, (None, ""))[0],
                                "Origen en PDF": hall.get(k, (None, ""))[1]} for k, v in CUENTAS.items()])
            ed = st.data_editor(df, key=f"e{i}{f.name}", hide_index=True, use_container_width=True,
                                disabled=["Cuenta", "Origen en PDF"], column_order=["Cuenta", "Valor", "Origen en PDF"])
            if st.button("💾 Guardar periodo", key=f"s{i}{f.name}", type="primary"):
                vals = {r["id"]: (None if pd.isna(r["Valor"]) else float(r["Valor"]) * mult) for _, r in ed.iterrows()}
                et = f"{int(y)}-{int(m):02d}" if period != "Anual" else f"{int(y)}"
                st.session_state.periodos[et] = {"orden": f"{int(y)}-{int(m):02d}", "m": int(m), "valores": vals}
                st.success(f"Periodo {et} guardado.")

# --------------------------- Cálculo compartido ---------------------------
per = dict(sorted(st.session_state.periodos.items(), key=lambda kv: kv[1]["orden"]))
tabla = {}
for et, d in per.items():
    k = 12 / d["m"] if anualizar else 1.0
    tabla[et] = calcular(d["valores"], k)


def serie(rid):
    return [(et, tabla[et][rid]) for et in tabla]


def disp(rid, v):
    return None if v is None else (v * 100 if META[rid]["fmt"] == "%" else v)


# ------------------------------ Módulo 2: dashboard ------------------------------
COLOR = {"Favorable": "#2e9e5b", "Aceptable": "#f0b429", "Crítico": "#d64545", "Sin calcular": "#9aa0a6"}
PUNTOS = {"Favorable": 100, "Aceptable": 50, "Crítico": 0}


def nv(rid, v):
    return nivel(rid, v) or "Sin calcular"


def mm(x):
    """Pesos -> millones de pesos (None -> 0)."""
    return 0.0 if x is None else x / 1e6


def puntaje_categoria(et, cat):
    p = [PUNTOS[nivel(r[0], tabla[et][r[0]])] for r in R
         if r[1] == cat and nivel(r[0], tabla[et][r[0]]) is not None]
    return sum(p) / len(p) if p else 0


def cumplimiento(rid, v):
    """% de avance contra el umbral 'favorable' (100% = justo en el umbral)."""
    m = META[rid]
    if v is None:
        return None
    if m["dir"] == "up":
        return v / m["bueno"] * 100 if m["bueno"] else None
    return (m["bueno"] / v * 100) if v > 0 else 200.0


def gauge(rid, v):
    m = META[rid]
    esc = 100 if m["fmt"] == "%" else 1
    val, bueno, ok = v * esc, m["bueno"] * esc, m["ok"] * esc
    mx = max(ok * 2, val * 1.2)
    if m["dir"] == "up":
        pasos = [(0, ok, COLOR["Crítico"]), (ok, bueno, COLOR["Aceptable"]), (bueno, mx, COLOR["Favorable"])]
    else:
        pasos = [(0, bueno, COLOR["Favorable"]), (bueno, ok, COLOR["Aceptable"]), (ok, mx, COLOR["Crítico"])]
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=val,
        number={"suffix": "%" if m["fmt"] == "%" else "x", "valueformat": ".2f"},
        title={"text": m["nombre"][:38], "font": {"size": 13}},
        gauge={"axis": {"range": [0, mx]}, "bar": {"color": "#1f2937", "thickness": 0.25},
               "steps": [{"range": [a, b], "color": c} for a, b, c in pasos]}))
    fig.update_layout(height=230, margin=dict(l=20, r=20, t=50, b=10))
    return fig


with tab2:
    if not per:
        st.info("Carga y guarda al menos un periodo en el módulo de carga.")
    else:
        ult = list(tabla)[-1]
        ant = list(tabla)[-2] if len(tabla) > 1 else None
        t_ind, t_res, t_bal, t_evo = st.tabs(
            ["📊 Indicadores", "🎯 Resumen visual", "🏦 Balance y reaseguro", "📈 Evolución"])

        # ---------- Indicadores (original) ----------
        with t_ind:
            st.subheader(f"Indicadores al periodo {ult}")
            for cat in CATEGORIAS:
                st.markdown(f"### {cat}")
                ids = [r[0] for r in R if r[1] == cat]
                cols = st.columns(min(len(ids), 4))
                for j, rid in enumerate(ids):
                    v = tabla[ult][rid]
                    delta = None
                    if ant and v is not None and tabla[ant][rid] is not None:
                        dv = disp(rid, v) - disp(rid, tabla[ant][rid])
                        delta = f"{dv:+.2f}" + (" pp" if META[rid]["fmt"] == "%" else "")
                    inv = "inverse" if META[rid]["dir"] == "down" else "normal"
                    with cols[j % len(cols)]:
                        st.metric(f"{ICONO[nivel(rid, v)]} {META[rid]['nombre'][:60]}", fmt(v, META[rid]["fmt"]),
                                  delta, delta_color=inv, help=META[rid]["nombre"])
                long = pd.DataFrame([{"Periodo": et, "Razón": META[rid]["nombre"][:45], "Valor": disp(rid, tabla[et][rid])}
                                     for rid in ids for et in tabla]).dropna()
                if not long.empty:
                    if len(tabla) == 1:
                        fig = px.bar(long, x="Razón", y="Valor", text_auto=".2f")
                    else:
                        fig = px.line(long, x="Periodo", y="Valor", color="Razón", markers=True)
                    fig.update_layout(height=360, margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", y=-0.3))
                    st.plotly_chart(fig, use_container_width=True, key=f"cat_{cat}")

            st.subheader("Tabla completa de razones")
            filas = [{"Categoría": META[r[0]]["cat"], "Razón": META[r[0]]["nombre"],
                      **{et: fmt(tabla[et][r[0]], META[r[0]]["fmt"]) for et in tabla},
                      "Estado": ICONO[nivel(r[0], tabla[ult][r[0]])]} for r in R]
            dft = pd.DataFrame(filas)
            st.dataframe(dft, use_container_width=True, hide_index=True)
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                dft.to_excel(w, index=False, sheet_name="Razones")
            st.download_button("⬇️ Descargar Excel", buf.getvalue(), "APP_RF_razones.xlsx")

        # ---------- Resumen visual ----------
        with t_res:
            sel = st.selectbox("Periodo a visualizar", list(tabla)[::-1], key="sel_res")
            ids_all = [r[0] for r in R]

            c1, c2 = st.columns(2)
            # Dona de semáforo
            cuenta = pd.Series([nv(rid, tabla[sel][rid]) for rid in ids_all]).value_counts().reset_index()
            cuenta.columns = ["Nivel", "Razones"]
            fig = px.pie(cuenta, names="Nivel", values="Razones", hole=0.55, color="Nivel",
                         color_discrete_map=COLOR, title=f"Semáforo general ({sel})")
            fig.update_traces(textinfo="value+percent")
            fig.update_layout(height=380, margin=dict(l=0, r=0, t=50, b=0))
            c1.plotly_chart(fig, use_container_width=True, key="dona")

            # Radar por categoría
            cats = CATEGORIAS
            radar = go.Figure()
            radar.add_trace(go.Scatterpolar(r=[puntaje_categoria(sel, c) for c in cats] + [puntaje_categoria(sel, cats[0])],
                                            theta=cats + [cats[0]], fill="toself", name=sel))
            idx = list(tabla).index(sel)
            if idx > 0:
                p_ant = list(tabla)[idx - 1]
                radar.add_trace(go.Scatterpolar(r=[puntaje_categoria(p_ant, c) for c in cats] + [puntaje_categoria(p_ant, cats[0])],
                                                theta=cats + [cats[0]], fill="toself", name=p_ant, opacity=0.45))
            radar.update_layout(polar=dict(radialaxis=dict(range=[0, 100])), height=380,
                                title="Salud por categoría (0 = crítico, 100 = favorable)",
                                margin=dict(l=40, r=40, t=50, b=20), legend=dict(orientation="h", y=-0.1))
            c2.plotly_chart(radar, use_container_width=True, key="radar")

            # Medidores de razones clave
            st.markdown("#### Razones clave")
            claves = [k for k in ("l1", "s5", "p4", "u1") if tabla[sel][k] is not None]
            if claves:
                gc = st.columns(len(claves))
                for col, rid in zip(gc, claves):
                    col.plotly_chart(gauge(rid, tabla[sel][rid]), use_container_width=True, key=f"g_{rid}")
            else:
                st.caption("No hay datos suficientes para los medidores.")

            # Cumplimiento vs umbral
            rows = [{"Razón": META[rid]["nombre"][:50], "Cumplimiento": min(cumplimiento(rid, tabla[sel][rid]), 200),
                     "Nivel": nv(rid, tabla[sel][rid]), "Categoría": META[rid]["cat"]}
                    for rid in ids_all if tabla[sel][rid] is not None]
            if rows:
                dfc = pd.DataFrame(rows)
                fig = px.bar(dfc, x="Cumplimiento", y="Razón", orientation="h", color="Nivel",
                             color_discrete_map=COLOR, hover_data=["Categoría"],
                             title="Cumplimiento frente al umbral favorable (100% = en el umbral)")
                fig.add_vline(x=100, line_dash="dash", line_color="black")
                fig.update_layout(height=max(380, 26 * len(rows)), margin=dict(l=0, r=0, t=50, b=0),
                                  yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig, use_container_width=True, key="cumpl")

            # Mapa de calor (si hay varios periodos)
            if len(tabla) > 1:
                z = [[PUNTOS.get(nivel(rid, tabla[et][rid]), None) for et in tabla] for rid in ids_all]
                fig = px.imshow(z, x=list(tabla), y=[META[rid]["nombre"][:50] for rid in ids_all],
                                color_continuous_scale=[COLOR["Crítico"], COLOR["Aceptable"], COLOR["Favorable"]],
                                zmin=0, zmax=100, aspect="auto", title="Mapa de calor de semáforos por periodo")
                fig.update_layout(height=max(420, 24 * len(ids_all)), margin=dict(l=0, r=0, t=50, b=0),
                                  coloraxis_showscale=False)
                st.plotly_chart(fig, use_container_width=True, key="heat")

        # ---------- Balance y reaseguro ----------
        with t_bal:
            sel_b = st.selectbox("Periodo a visualizar", list(tabla)[::-1], key="sel_bal")
            d = base(per[sel_b]["valores"])
            st.caption("Cifras en millones de pesos.")

            c1, c2 = st.columns(2)
            # Estructura del balance (barras apiladas)
            ac, af, at = mm(d["ac"]), mm(d["activo_fijo"]), mm(d["activo_total"])
            otros_a = max(at - ac - af, 0)
            rt = mm(d["reservas_tecnicas"])
            pas_otro = max(mm(d["pasivo_total"]) - rt, 0)
            cap = mm(d["capital_contable"])
            comp = [("Activo circulante", "Activo", ac), ("Activo fijo", "Activo", af), ("Otros activos", "Activo", otros_a),
                    ("Reservas técnicas", "Pasivo + Capital", rt), ("Otros pasivos", "Pasivo + Capital", pas_otro),
                    ("Capital contable", "Pasivo + Capital", cap)]
            dfb = pd.DataFrame(comp, columns=["Componente", "Lado", "Monto"])
            dfb = dfb[dfb["Monto"] > 0]
            if not dfb.empty:
                fig = px.bar(dfb, x="Lado", y="Monto", color="Componente", text_auto=",.1f",
                             title="Estructura del balance")
                fig.update_layout(height=420, margin=dict(l=0, r=0, t=50, b=0), xaxis_title=None)
                c1.plotly_chart(fig, use_container_width=True, key="bal")

                fig = px.treemap(dfb, path=["Lado", "Componente"], values="Monto", title="Peso de cada componente")
                fig.update_layout(height=420, margin=dict(l=0, r=0, t=50, b=0))
                c2.plotly_chart(fig, use_container_width=True, key="tree")
            else:
                c1.info("Sin datos de balance suficientes.")

            # Cascada de reaseguro
            pem, ced, ret = mm(d["pem"]), mm(d["prima_cedida"]), mm(d["pret"])
            if pem > 0:
                fig = go.Figure(go.Waterfall(
                    x=["Prima emitida", "Prima cedida", "Prima retenida"],
                    measure=["absolute", "relative", "total"], y=[pem, -ced, 0],
                    text=[f"{pem:,.1f}", f"-{ced:,.1f}", f"{ret:,.1f}"], textposition="outside",
                    decreasing={"marker": {"color": COLOR["Crítico"]}},
                    totals={"marker": {"color": COLOR["Favorable"]}}))
                fig.update_layout(title="Flujo de la prima: emitida → cedida → retenida", height=380,
                                  margin=dict(l=0, r=0, t=50, b=0), showlegend=False)
                st.plotly_chart(fig, use_container_width=True, key="rea")

            # Índice combinado por periodo (apilado)
            comb = pd.DataFrame([{"Periodo": et, "Componente": n, "Valor": tabla[et][k] * 100}
                                 for et in tabla for k, n in (("p1", "Operación"), ("p2", "Adquisición"), ("p3", "Siniestralidad"))
                                 if tabla[et][k] is not None])
            if not comb.empty:
                fig = px.bar(comb, x="Periodo", y="Valor", color="Componente", text_auto=".1f",
                             title="Índice combinado: composición por periodo (%)")
                fig.add_hline(y=100, line_dash="dash", line_color="red",
                              annotation_text="100% = punto de equilibrio técnico")
                fig.update_layout(height=400, margin=dict(l=0, r=0, t=50, b=0), legend=dict(orientation="h", y=-0.25))
                st.plotly_chart(fig, use_container_width=True, key="comb")

        # ---------- Evolución ----------
        with t_evo:
            cuentas = {"activo_total": "Activo total", "pasivo_total": "Pasivo total",
                       "capital_contable": "Capital contable", "pem": "Prima emitida", "un": "Utilidad neta",
                       "reservas_tecnicas": "Reservas técnicas"}
            bases = {et: base(per[et]["valores"], 12 / per[et]["m"] if anualizar else 1.0) for et in per}
            evo = pd.DataFrame([{"Periodo": et, "Cuenta": n, "Millones": bases[et][k] / 1e6}
                                for et in bases for k, n in cuentas.items() if bases[et].get(k) is not None])
            if evo.empty:
                st.info("Sin cuentas suficientes para graficar.")
            else:
                if len(tabla) == 1:
                    fig = px.bar(evo, x="Cuenta", y="Millones", text_auto=",.1f", title="Cuentas principales (millones de pesos)")
                else:
                    fig = px.line(evo, x="Periodo", y="Millones", color="Cuenta", markers=True,
                                  title="Evolución de cuentas principales (millones de pesos)")
                fig.update_layout(height=400, margin=dict(l=0, r=0, t=50, b=0), legend=dict(orientation="h", y=-0.25))
                st.plotly_chart(fig, use_container_width=True, key="evo")

                ev2 = evo[evo["Cuenta"].isin(["Utilidad neta", "Capital contable"])]
                if not ev2.empty:
                    fig = px.bar(ev2, x="Periodo", y="Millones", color="Cuenta", barmode="group",
                                 text_auto=",.1f", title="Utilidad neta vs capital contable")
                    fig.update_layout(height=360, margin=dict(l=0, r=0, t=50, b=0))
                    st.plotly_chart(fig, use_container_width=True, key="util")

            # Dispersión: apalancamiento vs rentabilidad
            pts = pd.DataFrame([{"Periodo": et, "Apalancamiento (Pasivo/Capital)": tabla[et]["s5"],
                                 "ROE (%)": tabla[et]["u1"] * 100,
                                 "Prima retenida (M)": max(mm(bases[et]["pret"]), 0.01)}
                                for et in tabla if tabla[et]["s5"] is not None and tabla[et]["u1"] is not None])
            if not pts.empty:
                fig = px.scatter(pts, x="Apalancamiento (Pasivo/Capital)", y="ROE (%)", text="Periodo",
                                 size="Prima retenida (M)", title="Apalancamiento vs rentabilidad (tamaño = prima retenida)")
                fig.update_traces(textposition="top center")
                fig.update_layout(height=400, margin=dict(l=0, r=0, t=50, b=0))
                st.plotly_chart(fig, use_container_width=True, key="disp")

# ------------------------------ Módulo 3: interpretación ------------------------------
with tab3:
    if not per:
        st.info("Carga y guarda al menos un periodo para ver las interpretaciones.")
    else:
        niveles = [nivel(r[0], tabla[list(tabla)[-1]][r[0]]) for r in R]
        st.success(f"Resumen: {niveles.count('Favorable')} favorables · {niveles.count('Aceptable')} aceptables · "
                   f"{niveles.count('Crítico')} críticas · {niveles.count(None)} sin calcular "
                   f"(periodos analizados: {len(tabla)}).")
        for cat in CATEGORIAS:
            st.markdown(f"## {cat}")
            for r in [x for x in R if x[1] == cat]:
                n_, txt, rec, tend = interpretar(r[0], serie(r[0]))
                with st.expander(f"{ICONO[n_]} {META[r[0]]['nombre']}"):
                    st.markdown(f"**Interpretación:** {txt}")
                    if tend:
                        st.markdown(f"**Tendencia:** {tend}")
                    if rec:
                        st.markdown(f"**Recomendación:** {rec}")
        st.caption("Los umbrales son referenciales y pueden ajustarse en ratios.py según el criterio de la compañía/regulador.")

from extractor import COMPUESTAS
with st.expander("🔍 Depurar cuentas compuestas"):
    for et, d in per.items():
        b = base(d["valores"])
        st.markdown(f"**Periodo {et}**")
        for cuenta, comps in COMPUESTAS.items():
            st.write(f"{cuenta} = {b.get(cuenta)}")
            st.write({c: b.get(c) for c in comps})
        st.write({"ac usado en razones": b["ac"], "pc usado en razones": b["pc"]})