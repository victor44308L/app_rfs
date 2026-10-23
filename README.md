# APP_RF – Razones financieras para aseguradoras

## Ejecutar en Visual Studio / VS Code
1. Abre la carpeta `APP_RF` y una terminal: `python -m venv .venv` → activar → `pip install -r requirements.txt`
2. `streamlit run app.py`
3. PC: http://localhost:8501 · Tablet/iPad/móvil (misma Wi-Fi): http://IP-DE-TU-PC:8501
   (para acceso externo despliega en Streamlit Community Cloud, Azure o similar).

## Estructura
- `app.py` interfaz (carga, dashboard, interpretaciones) · `extractor.py` lectura de PDF y alias de cuentas
- `ratios.py` 21 razones + umbrales · `interpretaciones.py` textos y tendencias

## Notas
- PDFs con texto (no escaneados). Los valores detectados se pueden corregir antes de guardar.
- Si no existen "Activo circulante", "Pasivo circulante" o "Pasivo exigible", se estiman:
  AC = Activo total − fijo; PE = Pasivo total − Reservas técnicas; PC = PE.
- Prima emitida = Prima directa si no se encuentra. Añade sinónimos en `ALIASES` (extractor.py) para tus formatos.
