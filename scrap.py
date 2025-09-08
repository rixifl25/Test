import os
import time
import json
import pandas as pd
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# -------------------------
# Constantes de la app
# -------------------------
URL_START = "https://api-seguridad.sunat.gob.pe/v1/clientessol/59d39217-c025-4de5-b342-393b0f4630ab/oauth2/loginMenuSol?lang=es-PE&showDni=true&showLanguages=false&originalUrl=https://e-menu.sunat.gob.pe/cl-ti-itmenu2/AutenticaMenuInternetPlataforma.htm&state=rO0ABXQA701GcmNEbDZPZ28xODJOWWQ4aTNPT2krWUcrM0pTODAzTEJHTmtLRE1IT2pBQ2l2eW84em5lWjByM3RGY1BLT0tyQjEvdTBRaHNNUW8KWDJRQ0h3WmZJQWZyV0JBaGtTT0hWajVMZEg0Mm5ZdHlrQlFVaDFwMzF1eVl1V2tLS3ozUnVoZ1ovZisrQkZndGdSVzg1TXdRTmRhbAp1ek5OaXdFbG80TkNSK0E2NjZHeG0zNkNaM0NZL0RXa1FZOGNJOWZsYjB5ZXc3MVNaTUpxWURmNGF3dVlDK3pMUHdveHI2cnNIaWc1CkI3SkxDSnc9"

XPATHS = {
    "ruc": '//*[@id="txtRuc"]',
    "usuario": '//*[@id="txtUsuario"]',
    "clave": '//*[@id="txtContrasena"]',
    "btn_ingresar": '//*[@id="btnAceptar"]',
    "btn_declaraciones1": '//*[@id="nivel2_55_2"]',
    "btn_declaraciones2": '//*[@id="nivel3_55_2_1"]',
    "btn_declaraciones3": '//*[@id="nivel4_55_2_1_1_1"]',
}

# -------------------------
# Utilidades Selenium
# -------------------------
def build_driver(headless: bool = True):
    """
    Crea un driver de Chrome/Chromium que funciona:
      - En Streamlit Cloud: usa /usr/bin/chromium y /usr/bin/chromedriver (instalados con packages.txt)
      - En local: usa webdriver-manager para descargar un driver compatible
    """
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

    # Intento 1: binarios del contenedor (Streamlit Cloud)
    chromium_bin = os.environ.get("GOOGLE_CHROME_BIN") or "/usr/bin/chromium"
    chromedriver_bin = os.environ.get("CHROMEDRIVER_PATH") or "/usr/bin/chromedriver"

    if os.path.exists(chromium_bin) and os.path.exists(chromedriver_bin):
        chrome_options.binary_location = chromium_bin
        service = Service(chromedriver_bin)
    else:
        # Intento 2: entorno local con webdriver-manager
        service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Ocultar webdriver (best-effort)
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"
        })
    except Exception:
        pass

    return driver

def save_artifacts(driver, prefix="sunat_error"):
    """Guarda screenshot y HTML de la página actual para diagnóstico."""
    outdir = os.path.abspath(".")
    png = os.path.join(outdir, f"{prefix}.png")
    html = os.path.join(outdir, f"{prefix}.html")
    try:
        driver.save_screenshot(png)
    except Exception:
        pass
    try:
        with open(html, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
    except Exception:
        pass
    return png, html

def run_sunat_scrape(ruc: str, usr: str, psw: str, mes_valor: str, anio_texto: str, headless: bool = True):
    driver = build_driver(headless=headless)
    wait = WebDriverWait(driver, 25)

    try:
        driver.get(URL_START)

        # Login
        wait.until(EC.presence_of_element_located((By.XPATH, XPATHS["ruc"]))).send_keys(ruc)
        driver.find_element(By.XPATH, XPATHS["usuario"]).send_keys(usr)
        driver.find_element(By.XPATH, XPATHS["clave"]).send_keys(psw)
        driver.find_element(By.XPATH, XPATHS["btn_ingresar"]).click()
        time.sleep(1.5)

        # Navegación “Mis declaraciones”
        for key in ("btn_declaraciones1", "btn_declaraciones2", "btn_declaraciones3"):
            wait.until(EC.element_to_be_clickable((By.XPATH, XPATHS[key]))).click()
            time.sleep(1.0)

        # Cambiar al iframe
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "iframeApplication")))
        time.sleep(2.5)

        # Selección de periodos
        Select(wait.until(EC.presence_of_element_located((By.ID, "periodo_tributario_1")))).select_by_value(mes_valor)
        Select(wait.until(EC.presence_of_element_located((By.XPATH, '//select[@ng-model="consultaBean.rangoPeriodoTributarioInicioAnio"]')))).select_by_visible_text(anio_texto)

        Select(wait.until(EC.presence_of_element_located((By.ID, "periodo_tributario_2")))).select_by_value(mes_valor)
        Select(wait.until(EC.presence_of_element_located((By.XPATH, '//select[@ng-model="consultaBean.rangoPeriodoTributarioFinAnio"]')))).select_by_visible_text(anio_texto)

        # Buscar
        wait.until(EC.element_to_be_clickable((By.XPATH, '//button[@ng-click="buscarConstancia()"]'))).click()
        time.sleep(1.2)

        rows = driver.find_elements(By.XPATH, '//table[contains(@class,"table")]/tbody/tr')

        def _nro_to_int(s: str) -> int:
            s = s.strip()
            digits = "".join(ch for ch in s if ch.isdigit())
            return int(digits) if digits else -1

        best = {}  # (Periodo, Formulario) -> fila con mayor NroOrden
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, 'td')
            if not cols or len(cols) < 9:
                continue
            if not cols[0].text.strip().isdigit():
                continue

            try:
                cols[8].find_element(By.TAG_NAME, 'a')
                estado = "pagado"
            except NoSuchElementException:
                estado = "sin pagar"

            fila = {
                "ID": cols[0].text.strip(),
                "Periodo": cols[1].text.strip(),
                "Formulario": cols[2].text.strip(),
                "Descripcion": cols[3].text.strip(),
                "NroOrden": cols[4].text.strip(),
                "FechaPresentacion": cols[5].text.strip(),
                "Banco": cols[6].text.strip(),
                "Importe": cols[7].text.strip(),
                "Estado": estado
            }

            key = (fila["Periodo"], fila["Formulario"])
            if key not in best or _nro_to_int(fila["NroOrden"]) > _nro_to_int(best[key]["NroOrden"]):
                best[key] = fila

        # Filtrar solo Formulario 0621
        result = [fila for fila in best.values() if fila.get("Formulario") == "0621"]
        return result

    except Exception as e:
        png, html = save_artifacts(driver)
        raise RuntimeError(f"{type(e).__name__}: {e}. Capturas guardadas: {os.path.basename(png)}, {os.path.basename(html)}") from e
    finally:
        driver.quit()

# -------------------------
# STREAMLIT UI
# -------------------------
st.set_page_config(page_title="🧾 Declaraciones SUNAT", page_icon="🧾", layout="centered")
st.title("🧾 Consulta de Declaraciones SUNAT")

with st.expander("⚠️ Aviso importante"):
    st.write(
        "Esta app automatiza el portal de SUNAT con Selenium. Úsala bajo tu responsabilidad y cumpliendo los Términos de Uso. "
        "Las credenciales se usan solo durante la ejecución de tu consulta."
    )

# Valores por defecto desde Secrets (opcional; no guardes claves)
ruc_default = st.secrets.get("RUC_DEFAULT", "")
usr_default = st.secrets.get("USR_DEFAULT", "")

# --- Cálculo de mes/año por defecto = mes anterior (America/Lima) ---
now_lima = datetime.now(ZoneInfo("America/Lima"))
if now_lima.month == 1:
    default_month_num = 12
    default_year_str = str(now_lima.year - 1)
else:
    default_month_num = now_lima.month - 1
    default_year_str = str(now_lima.year)

# Mapas de meses
mes_map = {
    "01 - Enero": "01", "02 - Febrero": "02", "03 - Marzo": "03", "04 - Abril": "04",
    "05 - Mayo": "05", "06 - Junio": "06", "07 - Julio": "07", "08 - Agosto": "08",
    "09 - Septiembre": "09", "10 - Octubre": "10", "11 - Noviembre": "11", "12 - Diciembre": "12"
}
month_labels_in_order = [
    "01 - Enero","02 - Febrero","03 - Marzo","04 - Abril","05 - Mayo","06 - Junio",
    "07 - Julio","08 - Agosto","09 - Septiembre","10 - Octubre","11 - Noviembre","12 - Diciembre"
]
default_label = f"{default_month_num:02d} - " + [
    "Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"
][default_month_num-1]
default_index = month_labels_in_order.index(default_label)

with st.form("form_login"):
    st.subheader("Credenciales")
    c1, c2 = st.columns(2)
    with c1:
        ruc = st.text_input("RUC", value=ruc_default, max_chars=11)
        usuario = st.text_input("Usuario SOL", value=usr_default)
    with c2:
        clave = st.text_input("Clave SOL", value="", type="password")

    st.subheader("Periodo")
    c3, c4 = st.columns(2)
    with c3:
        mes_label = st.selectbox("Mes (inicio/fin)", month_labels_in_order, index=default_index)
        mes_valor = mes_map[mes_label]
    with c4:
        anio = st.text_input("Año (ej. 2025)", value=default_year_str, max_chars=4)

    headless = st.checkbox("Ejecutar en headless (recomendado en la nube)", value=True)
    submitted = st.form_submit_button("Consultar")

if submitted:
    if not (ruc and usuario and clave and anio.isdigit()):
        st.warning("Completa todos los campos correctamente.")
    else:
        with st.spinner("Consultando en SUNAT..."):
            try:
                data = run_sunat_scrape(
                    ruc=ruc, usr=usuario, psw=clave,
                    mes_valor=mes_valor, anio_texto=anio, headless=headless
                )
                # data ya está filtrado por Formulario == "0621"
                if not data:
                    st.info("No se encontraron resultados del Formulario 0621 para el periodo seleccionado.")
                else:
                    df = pd.DataFrame(data)
                    st.success(f"Se encontraron {len(df)} registros del Formulario 0621.")
                    st.dataframe(df, use_container_width=True)

                    # ÚNICA descarga permitida: CSV
                    st.download_button(
                        "⬇️ Descargar CSV",
                        data=df.to_csv(index=False),
                        file_name=f"sunat_{ruc}_{anio}{mes_valor}_0621.csv",
                        mime="text/csv"
                    )

            except Exception as e:
                st.error(str(e))
                st.info("Revisa los archivos 'sunat_error.png' y 'sunat_error.html' generados en el directorio de la app para diagnóstico.")
