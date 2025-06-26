import time
import xmltodict
import logging
import os
from CloudflareBypasser import CloudflareBypasser
from DrissionPage import ChromiumPage, ChromiumOptions


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('cloudflare_bypass.log', mode='w')
    ]
)


def get_chromium_options(browser_path: str, arguments: list, is_headless: bool) -> ChromiumOptions:
    """
    Configures and returns Chromium options.

    :param browser_path: Path to the Chromium browser executable.
    :param arguments: List of arguments for the Chromium browser.
    :param is_headless: Boolean to indicate if the browser should run in headless mode.
    :return: Configured ChromiumOptions instance.
    """
    options = ChromiumOptions().auto_port()
    options.set_paths(browser_path=browser_path)

    if is_headless:
        options.set_argument('--headless=new')
    for argument in arguments:
        options.set_argument(argument)
    return options


def main():
    # Establece is_headless a True para modo headless, False para modo visible
    is_headless = os.getenv('HEADLESS', 'true').lower() == 'false'
    if is_headless:
        logging.info("Running in headless mode.")
    else:
        logging.info("Running in visible mode.")

    browser_path = os.getenv('CHROME_PATH', r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    logging.info(f'Chrome Path: {browser_path}, Exists: {os.path.exists(browser_path)}')

    arguments = [
        "-no-first-run",
        #"-force-color-profile=srgb",
        "-metrics-recording-only",
        "-password-store=basic",
        "-use-mock-keychain",
        "-export-tagged-pdf",
        "-no-default-browser-check",
        "-disable-background-mode",
        "-enable-features=NetworkService,NetworkServiceInProcess,LoadCryptoTokenExtension,PermuteTLSExtensions",
        "-disable-features=FlashDeprecationWarning,EnablePasswordsAccountStorage",
        "-deny-permission-prompts",
        # "-disable-gpu", # Considera quitar esto si tienes problemas de renderizado o CAPTCHA
        "-accept-lang=en-US",
    ]

    options = get_chromium_options(browser_path, arguments, is_headless)
    driver = ChromiumPage(addr_or_opts=options)
    try:
        logging.info('Navigating to trodo.es.')
        # Acedemos al API de TRODO

        matricula= input('Ingresa la matricula: ')
        driver.get(f'https://www.trodo.es/rest/V1/partfinder/search/ES/{matricula}/1')

        #driver.get(f'https://www.trodo.es/rest/V1/partfinder/search/ES/2482GZG/1')
        #driver.get(f'https://www.trodo.es/')
        #driver.get('https://www.carter-cash.es/')


        # --- Parte 1: Bypass Cloudflare  ---
        logging.info('Starting Cloudflare bypass.')
        time.sleep(5)
        cf_bypasser = CloudflareBypasser(driver)
        cf_bypasser.bypass()

        # --- Parte 2: Extraemos los datos obtenidos del requests ---

        xml_data = driver.html

        parsed_data = xmltodict.parse(xml_data)

        def get_data(data, path, default=None):
            """
            Función auxiliar para obtener un valor anidado de forma segura.
            La ruta es una lista de claves/índices.
            """
            current = data
            for p in path:
                if isinstance(current, dict):
                    current = current.get(p, default)
                elif isinstance(current, list) and isinstance(p, int):
                    try:
                        current = current[p]
                    except IndexError:
                        return default
                else:
                    return default  # El tipo no coincide o la clave/índice no es válida para el tipo actual
                if current is default and default is not None:  # Si ya regresamos al default, no sigas
                    return default
            return current


        vin_path = ['html', 'body', 'div', 0, 'response', 'item','attributes','vin']
        brand_path = ['html', 'body', 'div', 0, 'response', 'item','relationships','data','item','values','item', 5, 'label', 'name', 'MagentoFrameworkPhrasetext']
        full_model_path = ['html', 'body', 'div', 0, 'response', 'item','relationships','data','item','values','item', 4, 'url_key']
        model_path = ['html', 'body', 'div', 0, 'response', 'item','relationships','data','item','values','item', 4, 'label', 'name']
        variant_path = ['html', 'body', 'div', 0, 'response', 'item','relationships','data','item','values','item', 2, 'label', 'name', 'MagentoFrameworkPhrasetext']
        fuel_path = ['html', 'body', 'div', 0, 'response', 'item','relationships','data','item','values','item', 2, 'label', 'engine_fuel', 'MagentoFrameworkPhrasetext']
        liters_path = ['html', 'body', 'div', 0, 'response', 'item','relationships','data','item','values','item', 2, 'label', 'liters']
        year_path = ['html', 'body', 'div', 0, 'response', 'item','relationships','data','item','values','item', 2, 'label', 'year']
        year_from_path = ['html', 'body', 'div', 0, 'response', 'item','relationships','data','item','values','item', 2, 'label', 'year_from']
        year_to_path = ['html', 'body', 'div', 0, 'response', 'item','relationships','data','item','values','item', 2, 'label', 'year_to']
        ccm_path = ['html', 'body', 'div', 0, 'response', 'item','relationships','data','item','values','item', 2, 'label', 'ccm']
        kw_ps_path = ['html', 'body', 'div', 0, 'response', 'item','relationships','data','item','values','item', 2, 'label', 'kw_ps']
        engine_path = ['html', 'body', 'div', 0, 'response', 'item','relationships','data','item','values','item', 2, 'label', 'engine', 'item']



        model_item = get_data(parsed_data, model_path, {})
        full_model_item = get_data(parsed_data, full_model_path, {})
        brand_item = get_data(parsed_data, brand_path, {})
        vin_item = get_data(parsed_data,vin_path, {})
        variant_item = get_data(parsed_data, variant_path, {})
        fuel_item = get_data(parsed_data, fuel_path, {})
        liters_item = get_data(parsed_data, liters_path, {})
        year_item = get_data(parsed_data, year_path, {})
        year_from_item = get_data(parsed_data, year_from_path, {})
        year_to_item = get_data(parsed_data, year_to_path, {})
        ccm_item = get_data(parsed_data, ccm_path, {})
        kw_ps_item = get_data(parsed_data, kw_ps_path, {})
        engine_item = get_data(parsed_data, engine_path, {})

        car_json = {
            'MATRICULA': matricula ,
            'VIN': vin_item,
            'Marca': brand_item,
            'Modelo Completo': full_model_item,
            'Modelo':  model_item,
            'Variante':  variant_item,
            'Combustible': fuel_item,
            'Litros': liters_item,
            'Año': year_item,
            'Año Desde':  year_from_item,
            'Año Hasta':  year_to_item,
            'CCM':  ccm_item,
            'KW/PS':  kw_ps_item,
            'Engine': engine_item
        }

        for key, value in car_json.items():
            if isinstance(value, dict):
                first_item = next(iter(value.values()), None)
                car_json[key] = first_item




        print(car_json)



    except Exception as e:
        logging.error(f"A ocurrido un error: {e}")
        raise

    finally:
        logging.info('Closing the browser.')
        driver.quit()


if __name__ == '__main__':
    main()