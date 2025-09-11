import os
import time
import pandas as pd
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# -------------------------
# Constantes
# -------------------------
URL_START_FLOW1 = (
    "https://api-seguridad.sunat.gob.pe/v1/clientessol/59d39217-c025-4de5-b342-393b0f4630ab/oauth2/loginMenuSol?lang=es-PE&showDni=true&showLanguages=false&originalUrl=https://e-menu.sunat.gob.pe/cl-ti-itmenu2/AutenticaMenuInternetPlataforma.htm&state=rO0ABXQA701GcmNEbDZPZ28xODJOWWQ4aTNPT2krWUcrM0pTODAzTEJHTmtLRE1IT2pBQ2l2eW84em5lWjByM3RGY1BLT0tyQjEvdTBRaHNNUW8KWDJRQ0h3WmZJQWZyV0JBaGtTT0hWajVMZEg0Mm5ZdHlrQlFVaDFwMzF1eVl1V2tLS3ozUnVoZ1ovZisrQkZndGdSVzg1TXdRTmRhbHV6Tk5pd0VsbzROQ1IrQTY2Nkd4bTM2Q1ozQ1kvRFdrUVk4Y0k5ZmxiMHlleDcxU1pNSnFZRGY0YXd1WUMrekxQd295cjZyc0hpZzVCN0pMQ0p3PQ=="
)

URL_START_FLOW2 = (
    "https://api-seguridad.sunat.gob.pe/v1/clientessol/4f3b88b3-d9d6-402a-b85d-6a0bc857746a/oauth2/loginMenuSol?lang=es-PE&showDni=true&showLanguages=false&originalUrl=https://e-menu.sunat.gob.pe/cl-ti-itmenu/AutenticaMenuInternet.htm&state=rO0ABXNyABFqYXZhLnV0aWwuSGFzaE1hcAUH2sHDFmDRAwACRgAKbG9hZEZhY3RvckkACXRocmVzaG9sZHhwP0AAAAAAAAx3CAAAABAAAAADdAAEZXhlY3B0AAZwYXJhbXN0AEsqJiomL2NsLXRpLWl0bWVudS9NZW51SW50ZXJuZXQuaHRtJmI2NGQyNmE4YjVhZjA5MTkyM2IyM2I2NDA3YTFjMWRiNDFlNzMzYTZ0AANleGVweA=="
)

XPATHS_COMMON_LOGIN = {
    "ruc": '//*[@id="txtRuc"]',
    "usuario": '//*[@id="txtUsuario"]',
    "clave": '//*[@id="txtContrasena"]',
    "btn_ingresar": '//*[@id="btnAceptar"]',
}

XPATHS_FLOW1 = {
    "btn_declaraciones1": '//*[@id="nivel2_55_2"]',
    "btn_declaraciones2": '//*[@id="nivel3_55_2_1"]',
    "btn_declaraciones3": '//*[@id="nivel4_55_2_1_1_1"]',
    "iframe_app": "iframeApplication",
    "mes_ini": "periodo_tributario_1",
    "anio_ini_xpath": '//select[@ng-model="consultaBean.rangoPeriodoTributarioInicioAnio"]',
    "mes_fin": "periodo_tributario_2",
    "anio_fin_xpath": '//select[@ng-model="consultaBean.rangoPeriodoTributarioFinAnio"]',
    "btn_buscar_xpath": '//button[@ng-click="buscarConstancia()"]',
    "tabla_rows_xpath": '//table[contains(@class,"table")]/tbody/tr',
}

# -------------------------
# Utilidades
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

def vencimiento_por_ruc(ruc: str) -> str:
    if not ruc or not ruc[-1].isdigit():
        return ""
    d = int(ruc[-1])
    if d == 0: return "15/09/25"
    if d == 1: return "16/09/25"
    if d in (2, 3): return "17/09/25"
    if d in (4, 5): return "18/09/25"
    if d in (6, 7): return "19/09/25"
    return "22/09/25"  # 8 o 9

def _login(wait: WebDriverWait, ruc: str, usr: str, psw: str):
    wait.until(EC.presence_of_element_located((By.XPATH, XPATHS_COMMON_LOGIN["ruc"]))).send_keys(ruc)
    wait.until(EC.presence_of_element_located((By.XPATH, XPATHS_COMMON_LOGIN["usuario"]))).send_keys(usr)
    wait.until(EC.presence_of_element_located((By.XPATH, XPATHS_COMMON_LOGIN["clave"]))).send_keys(psw)
    wait.until(EC.element_to_be_clickable((By.XPATH, XPATHS_COMMON_LOGIN["btn_ingresar"]))).click()
    time.sleep(1.5)

def _safe_click(wait: WebDriverWait, driver: webdriver.Chrome, by, sel, pause=1.0):
    try:
        el = wait.until(EC.element_to_be_clickable((by, sel)))
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        except Exception:
            pass
        try:
            el.click()
        except Exception:
            driver.execute_script("arguments[0].click();", el)
        time.sleep(pause)
        return True
    except TimeoutException:
        return False

# -------------------------
# Flujo 1: Declaraciones (0621)
# -------------------------
def run_sunat_scrape_flow1(ruc: str, usr: str, psw: str, mes_valor: str, anio_texto: str, headless: bool = True):
    driver = build_driver(headless=headless)
    wait = WebDriverWait(driver, 25)
    try:
        driver.get(URL_START_FLOW1)
        _login(wait, ruc, usr, psw)

        for key in ("btn_declaraciones1", "btn_declaraciones2", "btn_declaraciones3"):
            wait.until(EC.element_to_be_clickable((By.XPATH, XPATHS_FLOW1[key]))).click()
            time.sleep(1.0)

        wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, XPATHS_FLOW1["iframe_app"])))
        time.sleep(2.0)

        Select(wait.until(EC.presence_of_element_located((By.ID, XPATHS_FLOW1["mes_ini"])))).select_by_value(mes_valor)
        Select(wait.until(EC.presence_of_element_located((By.XPATH, XPATHS_FLOW1["anio_ini_xpath"])))).select_by_visible_text(anio_texto)

        Select(wait.until(EC.presence_of_element_located((By.ID, XPATHS_FLOW1["mes_fin"])))).select_by_value(mes_valor)
        Select(wait.until(EC.presence_of_element_located((By.XPATH, XPATHS_FLOW1["anio_fin_xpath"])))).select_by_visible_text(anio_texto)

        wait.until(EC.element_to_be_clickable((By.XPATH, XPATHS_FLOW1["btn_buscar_xpath"]))).click()
        time.sleep(1.2)

        rows = driver.find_elements(By.XPATH, XPATHS_FLOW1["tabla_rows_xpath"])

        def _nro_to_int(s: str) -> int:
            digits = "".join(ch for ch in s if ch.isdigit())
            return int(digits) if digits else -1

        best = {}
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, 'td')
            if not cols or len(cols) < 9:
                continue
            if not cols[0].text.strip().isdigit():
                continue

            try:
                cols[8].find_element(By.TAG_NAME, 'a')
                estado_pago = "pagado"
            except NoSuchElementException:
                estado_pago = "sin pagar"

            fila = {
                "Periodo": cols[1].text.strip(),
                "Formulario": cols[2].text.strip(),
                "NroOrden": cols[4].text.strip(),
                "EstadoPago": estado_pago
            }
            key = (fila["Periodo"], fila["Formulario"])
            if key not in best or _nro_to_int(fila["NroOrden"]) > _nro_to_int(best[key]["NroOrden"]):
                best[key] = fila

        result = [fila for fila in best.values() if fila.get("Formulario") == "0621"]
        return {"hay_0621": bool(result)}

    except Exception as e:
        png, html = save_artifacts(driver, prefix="sunat_flow1_error")
        raise RuntimeError(f"[Flow1] {type(e).__name__}: {e}. Capturas: {os.path.basename(png)}, {os.path.basename(html)}") from e
    finally:
        driver.quit()

# -------------------------
# Flujo 2: Datos (Razón social y Perfil)
# -------------------------
def run_sunat_scrape_flow2_extract(ruc: str, usr: str, psw: str, headless: bool = True):
    """
    Secuencia:
      - Login en URL_START_FLOW2
      - Click: divOpcionServicio2 -> nivel1_84 -> nivel2_84_1 -> nivel3_84_1_1 -> nivel4_84_1_1_1_1
      - Cambia iframe 'iframeApplication'
      - Toma el PRIMER '.card-body'
      - Dentro, recoge los 7 '.list-inline'. De cada uno toma el 2do '.list-inline-item'.
      - Devuelve líneas 2 y 3 (índices 1 y 2): (razon_social, perfil_cumplimiento)
    """
    driver = build_driver(headless=headless)
    wait = WebDriverWait(driver, 25)

    try:
        driver.get(URL_START_FLOW2)
        _login(wait, ruc, usr, psw)

        # Orden de clics (según tus instrucciones)
        _safe_click(wait, driver, By.ID, "divOpcionServicio2")
        _safe_click(wait, driver, By.ID, "nivel1_84")
        _safe_click(wait, driver, By.ID, "nivel2_84_1")
        _safe_click(wait, driver, By.ID, "nivel3_84_1_1")
        _safe_click(wait, driver, By.ID, "nivel4_84_1_1_1_1")

        # Cambiar a iframe
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "iframeApplication")))
        time.sleep(1.0)

        # Tomar el primer .card-body
        card_bodies = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".card-body")))
        card = card_bodies[0] if card_bodies else None

        razon_social, perfil_cumpl = None, None
        if card:
            # Buscar los 7 list-inline dentro del card
            list_inlines = card.find_elements(By.CSS_SELECTOR, ".list-inline")
            # Para cada list-inline, tomar el segundo .list-inline-item
            valores = []
            for ul in list_inlines:
                items = ul.find_elements(By.CSS_SELECTOR, ".list-inline-item")
                if len(items) >= 2:
                    try:
                        txt = items[1].text.strip()
                        if not txt:
                            txt = items[1].get_attribute("innerText").strip()
                    except StaleElementReferenceException:
                        txt = (items[1].get_attribute("innerText") or "").strip()
                    valores.append(txt)
                else:
                    valores.append("")

            # Líneas 2 y 3 (índices 1 y 2)
            if len(valores) >= 3:
                razon_social = valores[1] or None
                perfil_cumpl = valores[2] or None

        return {
            "razon_social": razon_social,
            "perfil_cumplimiento": perfil_cumpl
        }

    except Exception as e:
        png, html = save_artifacts(driver, prefix="sunat_flow2_error")
        raise RuntimeError(f"[Flow2] {type(e).__name__}: {e}. Capturas: {os.path.basename(png)}, {os.path.basename(html)}") from e
    finally:
        driver.quit()

# -------------------------
# Helpers salida
# -------------------------
def armar_salida_final(ruc: str, razon_social: str, perfil_cumpl: str, hay_0621: bool, mes_valor: str, anio_texto: str) -> pd.DataFrame:
    estado = "Declarado" if hay_0621 else "No declarado"
    periodo_tributario = f"{anio_texto}{mes_valor}"
    vencimiento = vencimiento_por_ruc(ruc)
    return pd.DataFrame([{
        "RUC": ruc,
        "Razón social": razon_social,
        "Periodo tributario": periodo_tributario,
        "Vencimiento": vencimiento,
        "Perfil de cumplimiento": perfil_cumpl,
        "Estado": estado
    }])

# -------------------------
# STREAMLIT UI
# -------------------------
st.set_page_config(page_title="🧾 Declaraciones SUNAT (Integrado)", page_icon="🧾", layout="centered")
st.title("🧾 Consulta integrada SUNAT (Flujo 1 + Flujo 2)")

with st.expander("⚠️ Aviso importante"):
    st.write(
        "Esta app automatiza el portal de SUNAT con Selenium. Úsala bajo tu responsabilidad y cumpliendo los Términos de Uso. "
        "Las credenciales se usan solo durante la ejecución de tu consulta."
    )

# Defaults (opcional)
ruc_default = st.secrets.get("RUC_DEFAULT", "")
usr_default = st.secrets.get("USR_DEFAULT", "")

# Mes/año por defecto = mes anterior (America/Lima)
now_lima = datetime.now(ZoneInfo("America/Lima"))
if now_lima.month == 1:
    default_month_num = 12
    default_year_str = str(now_lima.year - 1)
else:
    default_month_num = now_lima.month - 1
    default_year_str = str(now_lima.year)

mes_map = {
    "01 - Enero": "01", "02 - Febrero": "02", "03 - Marzo": "03", "04 - Abril": "04",
    "05 - Mayo": "05", "06 - Junio": "06", "07 - Julio": "07", "08 - Agosto": "08",
    "09 - Septiembre": "09", "10 - Octubre": "10", "11 - Noviembre": "11", "12 - Diciembre": "12"
}
month_labels_in_order = list(mes_map.keys())
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
        # --------- FLUJO 1: 0621 ---------
        with st.spinner("Consultando Declaraciones (Flujo 1)..."):
            try:
                r1 = run_sunat_scrape_flow1(
                    ruc=ruc, usr=usuario, psw=clave,
                    mes_valor=mes_valor, anio_texto=anio, headless=headless
                )
                hay_0621 = r1.get("hay_0621", False)
                st.success(f"Flujo 1 OK · 0621: {'Sí' if hay_0621 else 'No'}")
            except Exception as e:
                st.error(str(e))
                st.stop()

        # --------- FLUJO 2: Razón social y Perfil ---------
        with st.spinner("Obteniendo Razón social y Perfil (Flujo 2)..."):
            razon_social, perfil_cumpl = "MerkiCont", ""  # defaults por si algo falla
            try:
                r2 = run_sunat_scrape_flow2_extract(
                    ruc=ruc, usr=usuario, psw=clave, headless=headless
                )
                razon_social = r2.get("razon_social") or razon_social
                perfil_cumpl = r2.get("perfil_cumplimiento") or perfil_cumpl
                st.success("Flujo 2 OK · Datos extraídos")
            except Exception as e:
                st.warning(f"No se pudo extraer datos de Flujo 2. Uso de valores por defecto. Detalle: {e}")

        # --------- SALIDA INTEGRADA ---------
        df_out = armar_salida_final(
            ruc=ruc,
            razon_social=razon_social,
            perfil_cumpl=perfil_cumpl,
            hay_0621=hay_0621,
            mes_valor=mes_valor,
            anio_texto=anio
        )

        st.subheader("Resultado (Integrado)")
        st.table(df_out)
        st.download_button(
            "⬇️ Descargar CSV (resultado integrado)",
            data=df_out.to_csv(index=False),
            file_name=f"sunat_integrado_{ruc}_{anio}{mes_valor}.csv",
            mime="text/csv"
        )
