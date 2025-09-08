# app.py
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Consulta 0621 por Periodo", page_icon="🧾", layout="centered")

URL_START = (
    "https://api-seguridad.sunat.gob.pe/v1/clientessol/59d39217-c025-4de5-b342-393b0f4630ab/oauth2/loginMenuSol?lang=es-PE&showDni=true&showLanguages=false&originalUrl=https://e-menu.sunat.gob.pe/cl-ti-itmenu2/AutenticaMenuInternetPlataforma.htm"
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

tz = ZoneInfo("America/Lima")

# -------------------------
# Helpers
# -------------------------
def build_driver(headless: bool = True):
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
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

    # best-effort: ocultar webdriver
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

def scrape_one_month_0621(ruc: str, usr: str, psw: str, year: int, month: int, headless: bool):
    """
    Ejecuta TODO el flujo para un solo periodo (year, month) y retorna:
      {"encontrado": bool, "fila": {...} or None}
    Solo considera Formulario 0621 y elige la fila con mayor NroOrden.
    """
    driver = build_driver(headless=headless)
    wait = WebDriverWait(driver, 25)
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
        time.sleep(0.8)

        # Selects y búsqueda
        sel_mes_ini = wait.until(EC.presence_of_element_located((By.ID, "periodo_tributario_1")))
        sel_anio_ini = wait.until(EC.presence_of_element_located((By.XPATH, '//select[@ng-model="consultaBean.rangoPeriodoTributarioInicioAnio"]')))
        sel_mes_fin = wait.until(EC.presence_of_element_located((By.ID, "periodo_tributario_2")))
        sel_anio_fin = wait.until(EC.presence_of_element_located((By.XPATH, '//select[@ng-model="consultaBean.rangoPeriodoTributarioFinAnio"]')))
        btn_buscar = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[@ng-click="buscarConstancia()"]')))

        Select(sel_anio_ini).select_by_visible_text(str(year))
        Select(sel_anio_fin).select_by_visible_text(str(year))

        mes_valor = f"{month:02d}"
        Select(sel_mes_ini).select_by_value(mes_valor)
        Select(sel_mes_fin).select_by_value(mes_valor)
        btn_buscar.click()
        time.sleep(1.0)

        # Parse tabla
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

        return {"encontrado": best_row is not None, "fila": best_row}

    except Exception as e:
        save_artifacts(driver, prefix=f"sunat_error_{year}{month:02d}")
        return {"encontrado": False, "fila": None, "error": f"{type(e).__name__}: {e}"}
    finally:
        try: driver.quit()
        except Exception: pass

# -------------------------
# UI
# -------------------------
st.title("🧾 Consulta Formulario 0621 por Periodo")
with st.expander("⚠️ Aviso importante"):
    st.write("Esta app automatiza el portal de SUNAT con Selenium. Úsala bajo tu responsabilidad. Las credenciales no se almacenan.")

# Defaults opcionales desde secrets
ruc_default = st.secrets.get("RUC_DEFAULT", "")
usr_default = st.secrets.get("USR_DEFAULT", "")
razon_default = st.secrets.get("RAZON_DEFAULT", "")

now = datetime.now(tz)
anio_actual = now.year
mes_actual = now.month

with st.form("form"):
    st.subheader("Credenciales")
    c1, c2 = st.columns(2)
    with c1:
        ruc = st.text_input("RUC", value=ruc_default, max_chars=11)
        usuario = st.text_input("Usuario SOL", value=usr_default)
    with c2:
        clave = st.text_input("Clave SOL", type="password")
        razon = st.text_input("Razón social (opcional)", value=razon_default)

    st.subheader("Periodo a consultar")
    c3, c4, c5 = st.columns([1, 1, 1.2])
    with c3:
        meses = [
            ("01 - Enero", 1), ("02 - Febrero", 2), ("03 - Marzo", 3), ("04 - Abril", 4),
            ("05 - Mayo", 5), ("06 - Junio", 6), ("07 - Julio", 7), ("08 - Agosto", 8),
            ("09 - Septiembre", 9), ("10 - Octubre", 10), ("11 - Noviembre", 11), ("12 - Diciembre", 12),
        ]
        mes_label = st.selectbox("Mes", [m[0] for m in meses], index=mes_actual-1)
        mes_value = dict(meses)[mes_label]
    with c4:
        anio = st.number_input("Año", min_value=2005, max_value=anio_actual, value=anio_actual, step=1)
    with c5:
        show_browser = st.checkbox("Mostrar navegador (desactivar headless)", value=False)
        st.caption("En servidores sin entorno gráfico, puede que no se muestre.")

    submitted = st.form_submit_button("Consultar")

if submitted:
    if not (ruc and usuario and clave):
        st.warning("Completa RUC, Usuario y Clave.")
    else:
        headless = not show_browser
        periodo_fmt = f"{int(anio)}/{int(mes_value):02d}"
        with st.spinner(f"Consultando 0621 para {periodo_fmt}…"):
            res = scrape_one_month_0621(ruc, usuario, clave, int(anio), int(mes_value), headless=headless)

        # Preparar tabla final (una fila)
        estado = "Declarado" if res.get("encontrado") else "No declarado"
        fila = res.get("fila") or {}
        df = pd.DataFrame([{
            "RUC": ruc,
            "Razón social": razon or "—",
            "Periodo tributario": periodo_fmt,
            "Estado": estado,
            "Fecha presentación": fila.get("FechaPresentacion", "—") if estado == "Declarado" else "—",
            "NroOrden": fila.get("NroOrden", "—") if estado == "Declarado" else "—",
            "Importe": fila.get("Importe", "—") if estado == "Declarado" else "—",
            "Banco": fila.get("Banco", "—") if estado == "Declarado" else "—",
            "Descripción": fila.get("Descripcion", "—") if estado == "Declarado" else "—",
        }])

        st.success(f"Resultado para {periodo_fmt}: {estado}")
        st.dataframe(df, use_container_width=True)
