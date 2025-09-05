import streamlit as st
import pandas as pd
import json
import time

from selenium import webdriver 
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

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

def run_sunat_scrape(ruc: str, usr: str, psw: str, mes_valor: str, anio_texto: str, headless: bool = True):
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1680,1280")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0 Safari/537.36"
    )

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Ocultar webdriver (algunas protecciones básicas)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"
    })

    wait = WebDriverWait(driver, 15)
    try:
        driver.get(URL_START)

        # Login
        wait.until(EC.presence_of_element_located((By.XPATH, XPATHS["ruc"]))).send_keys(ruc)
        driver.find_element(By.XPATH, XPATHS["usuario"]).send_keys(usr)
        driver.find_element(By.XPATH, XPATHS["clave"]).send_keys(psw)
        driver.find_element(By.XPATH, XPATHS["btn_ingresar"]).click()
        time.sleep(1)

        # Navegación “Mis declaraciones”
        driver.find_element(By.XPATH, XPATHS["btn_declaraciones1"]).click()
        time.sleep(1)
        driver.find_element(By.XPATH, XPATHS["btn_declaraciones2"]).click()
        time.sleep(1)
        driver.find_element(By.XPATH, XPATHS["btn_declaraciones3"]).click()

        # Cambiar al iframe de la aplicación
        WebDriverWait(driver, 15).until(
            EC.frame_to_be_available_and_switch_to_it((By.ID, "iframeApplication"))
        )
        time.sleep(3)

        # Selección de periodos
        Select(driver.find_element(By.ID, "periodo_tributario_1")).select_by_value(mes_valor)
        Select(driver.find_element(By.XPATH, '//select[@ng-model="consultaBean.rangoPeriodoTributarioInicioAnio"]')).select_by_visible_text(anio_texto)

        Select(driver.find_element(By.ID, "periodo_tributario_2")).select_by_value(mes_valor)
        Select(driver.find_element(By.XPATH, '//select[@ng-model="consultaBean.rangoPeriodoTributarioFinAnio"]')).select_by_visible_text(anio_texto)

        # Buscar
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//button[@ng-click="buscarConstancia()"]'))
        ).click()
        time.sleep(1)

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

        return list(best.values())

    finally:
        driver.quit()


# -------------------------
# STREAMLIT UI
# -------------------------
st.set_page_config(page_title="Consultas SUNAT (Demo)", page_icon="🧾", layout="centered")
st.title("🧾 Consulta de Declaraciones SUNAT (Demo)")

with st.expander("⚠️ Aviso"):
    st.write(
        "Esta herramienta automatiza la navegación en el portal de SUNAT usando Selenium. "
        "Úsala bajo tu responsabilidad y respetando los Términos de Uso del portal. "
        "Las credenciales se usan solo durante la sesión en tu equipo."
    )

with st.form("form_login"):
    st.subheader("Credenciales de Ingreso")
    col1, col2 = st.columns(2)
    with col1:
        ruc = st.text_input("RUC", value="", max_chars=11)
        usuario = st.text_input("Usuario SOL", value="")
    with col2:
        clave = st.text_input("Clave SOL", value="", type="password")

    st.subheader("Periodo")
    col3, col4 = st.columns(2)
    with col3:
        mes_map = {
            "01 - Enero": "01", "02 - Febrero": "02", "03 - Marzo": "03", "04 - Abril": "04",
            "05 - Mayo": "05", "06 - Junio": "06", "07 - Julio": "07", "08 - Agosto": "08",
            "09 - Septiembre": "09", "10 - Octubre": "10", "11 - Noviembre": "11", "12 - Diciembre": "12"
        }
        mes_label = st.selectbox("Mes (inicio/fin)", list(mes_map.keys()), index=2)  # por defecto Marzo
        mes_valor = mes_map[mes_label]
    with col4:
        anio = st.text_input("Año (ej. 2025)", value="2025", max_chars=4)

    headless = st.checkbox("Ejecutar en segundo plano (headless)", value=True)

    submitted = st.form_submit_button("Consultar")

if submitted:
    if not (ruc and usuario and clave and anio and anio.isdigit()):
        st.warning("Completa todos los campos correctamente.")
    else:
        with st.spinner("Consultando en SUNAT..."):
            try:
                data = run_sunat_scrape(
                    ruc=ruc,
                    usr=usuario,
                    psw=clave,
                    mes_valor=mes_valor,
                    anio_texto=anio,
                    headless=headless
                )
                if not data:
                    st.info("No se encontraron resultados para el periodo seleccionado.")
                else:
                    st.success(f"Se encontraron {len(data)} registros.")
                    df = pd.DataFrame(data)
                    st.dataframe(df, use_container_width=True)

                    # Descargas
                    colA, colB = st.columns(2)
                    with colA:
                        st.download_button(
                            "⬇️ Descargar JSON",
                            data=json.dumps(data, ensure_ascii=False, indent=2),
                            file_name=f"sunat_{ruc}_{anio}{mes_valor}.json",
                            mime="application/json"
                        )
                    with colB:
                        st.download_button(
                            "⬇️ Descargar CSV",
                            data=df.to_csv(index=False),
                            file_name=f"sunat_{ruc}_{anio}{mes_valor}.csv",
                            mime="text/csv"
                        )

                    # Opcional: ver JSON crudo
                    with st.expander("Ver JSON crudo"):
                        st.code(json.dumps(data, ensure_ascii=False, indent=2), language="json")

            except Exception as e:
                st.error(f"Ocurrió un error durante la consulta: {e}")
