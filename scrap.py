# app.py
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


# =========================
# Config & Constantes
# =========================
st.set_page_config(page_title="Matriz de Cumplimiento 0621", page_icon="🧾", layout="wide")

URL_START = (
    "https://api-seguridad.sunat.gob.pe/v1/clientessol/59d39217-c025-4de5-b342-393b0f4630ab/"
    "oauth2/loginMenuSol?lang=es-PE&showDni=true&showLanguages=false&"
    "originalUrl=https://e-menu.sunat.gob.pe/cl-ti-itmenu2/AutenticaMenuInternetPlataforma.htm"
)

XPATHS = {
    "ruc": '//*[@id="txtRuc"]',
    "usuario": '//*[@id="txtUsuario"]',
    "clave": '//*[@id="txtContrasena"]',
    "btn_ingresar": '//*[@id="btnAceptar"]',
    "btn_declaraciones1": '//*[@id="nivel2_55_2"]',
    "btn_declaraciones2": '//*[@id="nivel3_55_2_1"]',
    "btn_declaraciones3": '//*[@id="nivel4_55_2_1_1_1"]',
}


# =========================
# Estilos (look & feel)
# =========================
st.markdown("""
<style>
[data-testid="stSidebar"] {min-width: 280px; max-width: 280px;}
.sidebar-wrap .name {font-size:1.1rem;font-weight:800;}
.sidebar-wrap .sub {color:#6B7280;margin-bottom:18px;}
.menu {margin-top:10px;}
.menu .item {
  display:flex; align-items:center; gap:10px;
  padding:10px 12px; border-radius:12px; margin-bottom:6px;
  font-weight:600; color:#111827;
}
.menu .item.active { background:#1118270D; border:1px solid #E5E7EB; }
.menu .icon {width:20px; text-align:center}

.h-page {font-size:1.6rem; font-weight:800; margin-bottom:2px;}
.h-sub  {color:#6B7280; margin-bottom:18px;}
.card {
  background:#fff; border:1px solid #E5E7EB; border-radius:16px;
  padding:16px 16px 8px 16px; box-shadow:0 1px 2px rgba(0,0,0,0.02);
}
.card h3 {font-size:1.05rem; font-weight:800; margin:0 0 10px 0;}
.table {width:100%; border-collapse:separate; border-spacing:0 8px;}
.table thead th {
  color:#6B7280; font-weight:700; font-size:0.9rem; text-align:left; padding:10px 12px;
}
.table tbody tr {background:#F9FAFB; border:1px solid #E5E7EB;}
.table tbody td {padding:12px; font-size:0.95rem;}
.table tbody tr {border-radius:12px;}
.table tbody tr td:first-child {border-top-left-radius:12px; border-bottom-left-radius:12px;}
.table tbody tr td:last-child  {border-top-right-radius:12px; border-bottom-right-radius:12px;}

.badge {
  display:inline-block; padding:6px 10px; border-radius:10px; font-weight:700; font-size:0.8rem;
  border:1px solid;
}
.badge.ok { color:#065F46; background:#ECFDF5; border-color:#A7F3D0; }
.badge.no { color:#374151; background:#F3F4F6; border-color:#E5E7EB; }

.panel {background:#fff; border:1px solid #E5E7EB; border-radius:16px; padding:16px;}
.block-container {padding-top: 1.2rem;}
</style>
""", unsafe_allow_html=True)


# =========================
# Sidebar (visual)
# =========================
with st.sidebar:
    st.markdown("<div class='sidebar-wrap'>", unsafe_allow_html=True)
    st.markdown("<div class='name'>Hola<br>Javier Pérez</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub'>Panel de cumplimiento tributario</div>", unsafe_allow_html=True)
    st.markdown("<div class='menu'>", unsafe_allow_html=True)
    st.markdown("<div class='item active'><div class='icon'>🏠</div>Inicio</div>", unsafe_allow_html=True)
    st.markdown("<div class='item'><div class='icon'>🧾</div>Comprobante electro..</div>", unsafe_allow_html=True)
    st.markdown("<div class='item'><div class='icon'>📥</div>Buzón electrónico</div>", unsafe_allow_html=True)
    st.markdown("<div class='item'><div class='icon'>🧩</div>Extensiones</div>", unsafe_allow_html=True)
    st.markdown("<div class='item'><div class='icon'>📊</div>Reportes</div>", unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)
    st.caption("Barra ilustrativa, no interactiva.")


# =========================
# Selenium helpers
# =========================
def build_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # SIEMPRE headless
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1680,1280")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
    )
    chromium_bin = os.environ.get("GOOGLE_CHROME_BIN") or "/usr/bin/chromium"
    chromedriver_bin = os.environ.get("CHROMEDRIVER_PATH") or "/usr/bin/chromedriver"
    if os.path.exists(chromium_bin) and os.path.exists(chromedriver_bin):
        chrome_options.binary_location = chromium_bin
        service = Service(chromedriver_bin)
    else:
        service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"
        })
    except Exception:
        pass
    return driver


def save_artifacts(driver, prefix="sunat_error"):
    outdir = os.path.abspath(".")
    png = os.path.join(outdir, f"{prefix}.png")
    html = os.path.join(outdir, f"{prefix}.html")
    try: driver.save_screenshot(png)
    except Exception: pass
    try:
        with open(html, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
    except Exception: pass
    return png, html


def _nro_to_int(s: str) -> int:
    s = (s or "").strip()
    digits = "".join(ch for ch in s if ch.isdigit())
    return int(digits) if digits else -1


# =========================
# Scraping: enero → mes actual (año actual) / 12 meses (años pasados)
# =========================
def scrape_year_status(ruc: str, usr: str, psw: str, year: int, now_dt: datetime) -> dict:
    """
    Retorna { 'YYYYMM': {'encontrado': bool, 'fila': {...} or None} }.
    Solo considera Formulario == '0621'. Para cada mes toma la fila con mayor NroOrden.
    Enero→mes actual si year == ahora.year; de lo contrario 12 meses.
    """
    driver = build_driver()
    wait = WebDriverWait(driver, 25)
    result = {}

    try:
        driver.get(URL_START)
        # Login
        wait.until(EC.presence_of_element_located((By.XPATH, XPATHS["ruc"]))).send_keys(ruc)
        driver.find_element(By.XPATH, XPATHS["usuario"]).send_keys(usr)
        driver.find_element(By.XPATH, XPATHS["clave"]).send_keys(psw)
        driver.find_element(By.XPATH, XPATHS["btn_ingresar"]).click()
        time.sleep(1.0)

        # Menú
        for key in ("btn_declaraciones1", "btn_declaraciones2", "btn_declaraciones3"):
            wait.until(EC.element_to_be_clickable((By.XPATH, XPATHS[key]))).click()
            time.sleep(0.7)

        # Iframe
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "iframeApplication")))
        time.sleep(1.0)

        # Selects reutilizables
        sel_mes_ini = wait.until(EC.presence_of_element_located((By.ID, "periodo_tributario_1")))
        sel_anio_ini = wait.until(EC.presence_of_element_located((By.XPATH, '//select[@ng-model="consultaBean.rangoPeriodoTributarioInicioAnio"]')))
        sel_mes_fin = wait.until(EC.presence_of_element_located((By.ID, "periodo_tributario_2")))
        sel_anio_fin = wait.until(EC.presence_of_element_located((By.XPATH, '//select[@ng-model="consultaBean.rangoPeriodoTributarioFinAnio"]')))
        btn_buscar = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[@ng-click="buscarConstancia()"]')))

        # Año fijo
        Select(sel_anio_ini).select_by_visible_text(str(year))
        Select(sel_anio_fin).select_by_visible_text(str(year))

        # Rango de meses
        month_end = now_dt.month if year == now_dt.year else 12
        for m in range(1, month_end + 1):
            mes_valor = f"{m:02d}"
            periodo_key = f"{year}{mes_valor}"

            Select(sel_mes_ini).select_by_value(mes_valor)
            Select(sel_mes_fin).select_by_value(mes_valor)
            btn_buscar.click()
            time.sleep(0.9)

            rows = driver.find_elements(By.XPATH, '//table[contains(@class,"table")]/tbody/tr')
            best_row = None
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, 'td')
                if not cols or len(cols) < 9 or not cols[0].text.strip().isdigit():
                    continue

                fila = {
                    "ID": cols[0].text.strip(),
                    "Periodo": cols[1].text.strip(),
                    "Formulario": cols[2].text.strip(),
                    "Descripcion": cols[3].text.strip(),
                    "NroOrden": cols[4].text.strip(),
                    "FechaPresentacion": cols[5].text.strip(),
                    "Banco": cols[6].text.strip(),
                    "Importe": cols[7].text.strip(),
                }

                # Solo 0621
                if fila["Formulario"].strip() != "0621":
                    continue

                if (best_row is None) or (_nro_to_int(fila["NroOrden"]) > _nro_to_int(best_row["NroOrden"])):
                    best_row = fila

            result[periodo_key] = {"encontrado": best_row is not None, "fila": best_row}

        return result

    except Exception as e:
        png, html = save_artifacts(driver)
        raise RuntimeError(f"{type(e).__name__}: {e}. Capturas: {os.path.basename(png)}, {os.path.basename(html)}") from e
    finally:
        driver.quit()


# =========================
# UI principal
# =========================
st.markdown("<div class='h-page'>Inicio</div>", unsafe_allow_html=True)
st.markdown("<div class='h-sub'>Visualiza la matriz de cumplimiento tributario y un resumen del estado mensual (Formulario 0621).</div>", unsafe_allow_html=True)

with st.expander("⚠️ Aviso importante"):
    st.write("Esta app automatiza el portal de SUNAT con Selenium. Úsala bajo tu responsabilidad. Las credenciales no se almacenan.")

# Defaults por secrets
ruc_default = st.secrets.get("RUC_DEFAULT", "")
usr_default = st.secrets.get("USR_DEFAULT", "")
razon_default = st.secrets.get("RAZON_DEFAULT", "")

tz = ZoneInfo("America/Lima")
now = datetime.now(tz)
anio_actual = now.year

with st.form("form_login"):
    c1, c2, c3 = st.columns([1.2, 1.2, 0.8])
    with c1:
        ruc = st.text_input("RUC", value=ruc_default, max_chars=11)
        usuario = st.text_input("Usuario SOL", value=usr_default)
    with c2:
        clave = st.text_input("Clave SOL", type="password")
        razon = st.text_input("Razón social (opcional)", value=razon_default)
    with c3:
        anio = st.number_input("Año", min_value=2005, max_value=anio_actual, value=anio_actual, step=1)
        st.caption(f"Se consulta de enero a {now.month:02d}/{int(anio)} si es el año actual; de lo contrario 12 meses.")
    submitted = st.form_submit_button("Consultar")

if submitted:
    if not (ruc and usuario and clave):
        st.warning("Completa RUC, Usuario y Clave.")
    else:
        with st.spinner(f"Consultando SUNAT para el año {int(anio)} (Formulario 0621)…"):
            try:
                resumen = scrape_year_status(ruc, usuario, clave, int(anio), now)

                # Construir matriz con Periodo formateado YYYY/MM y orden por mes
                registros = []
                for periodo_key, info in resumen.items():
                    year_i = int(periodo_key[:4])
                    month_i = int(periodo_key[4:])
                    periodo_fmt = f"{year_i}/{month_i:02d}"  # YYYY/MM
                    estado = "Declarado" if info["encontrado"] else "No declarado"
                    registros.append({
                        "PeriodoNum": year_i * 100 + month_i,
                        "RUC": ruc,
                        "Razon": razon or "—",
                        "Periodo": periodo_fmt,
                        "Vencimiento": "—",
                        "Perfil": "—",
                        "Estado": estado
                    })

                df = pd.DataFrame(registros).sort_values("PeriodoNum").reset_index(drop=True)

                left, right = st.columns([2.8, 1.2])

                # -------- Tabla HTML estilizada
                with left:
                    st.markdown("<div class='card'><h3>Matriz de Cumplimiento Tributario</h3>", unsafe_allow_html=True)
                    header = """
                    <table class="table">
                      <thead>
                        <tr>
                          <th>RUC</th>
                          <th>Razón social</th>
                          <th>Periodo tributario</th>
                          <th>Vencimiento</th>
                          <th>Perfil de cumplimiento</th>
                          <th>Estado</th>
                        </tr>
                      </thead>
                      <tbody>
                    """
                    rows_html = []
                    for _, row in df.iterrows():
                        badge_class = "ok" if row["Estado"] == "Declarado" else "no"
                        badge_text = "Declarado" if row["Estado"] == "Declarado" else "No declarado"
                        rows_html.append(f"""
                          <tr>
                            <td>{row['RUC']}</td>
                            <td>{row['Razon']}</td>
                            <td>{row['Periodo']}</td>
                            <td>{row['Vencimiento']}</td>
                            <td>{row['Perfil']}</td>
                            <td><span class="badge {badge_class}">{badge_text}</span></td>
                          </tr>
                        """)
                    footer = "</tbody></table></div>"
                    st.markdown(header + "\n".join(rows_html) + footer, unsafe_allow_html=True)

                # -------- Panel de seguimiento (donut Presentados vs No presentados)
                with right:
                    st.markdown("<div class='panel'><h3>Panel de seguimiento</h3>", unsafe_allow_html=True)
                    total = len(df)
                    presentados = int((df["Estado"] == "Declarado").sum())
                    no_presentados = total - presentados

                    try:
                        import plotly.express as px
                        donut_df = pd.DataFrame(
                            {"Estado": ["Presentados", "No presentados"],
                             "Valor": [presentados, no_presentados]}
                        )
                        fig = px.pie(donut_df, names="Estado", values="Valor", hole=0.6)
                        fig.update_traces(textposition="inside", textinfo="percent+label")
                        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=300)
                        st.plotly_chart(fig, use_container_width=True)
                    except Exception:
                        st.metric("Presentados", f"{presentados}/{total}")
                        st.metric("No presentados", f"{no_presentados}/{total}")

                    st.caption("Basado en meses con Formulario 0621 presentados vs no presentados.")
                    st.markdown("</div>", unsafe_allow_html=True)

            except Exception as e:
                st.error(str(e))
                st.info("Se generaron 'sunat_error.png' y 'sunat_error.html' en el servidor para diagnóstico.")
