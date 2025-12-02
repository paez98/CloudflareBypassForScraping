import time
import xmltodict
import logging
import os
import json
import re
import sys
import argparse
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
    parser = argparse.ArgumentParser(description="Trodo vehicle extractor")
    parser.add_argument("matricula", help="Matrícula a consultar")
    parser.add_argument("--capture-url", dest="capture_url", default=os.getenv("CAPTURE_URL"))
    parser.add_argument("--capture-match", dest="capture_match", choices=["exact","prefix"], default=os.getenv("CAPTURE_MATCH","exact"))
    parser.add_argument("--capture-regex", dest="capture_regex", default=os.getenv("CAPTURE_REGEX"))
    parser.add_argument("--capture-select", dest="capture_select", default=os.getenv("CAPTURE_SELECT","first"))
    parser.add_argument("--print-body", dest="print_body", action="store_true", default=os.getenv("PRINT_BODY","no").lower() in ("yes","true","1"))
    parser.add_argument("--headless", dest="headless", action="store_true")
    args = parser.parse_args()

    env_headless = os.getenv('HEADLESS', 'true').lower() == 'false'
    is_headless = args.headless or env_headless
    matricula = args.matricula
    capture_url = args.capture_url
    match_mode = args.capture_match
    capture_regex = args.capture_regex
    select_mode = args.capture_select.lower()
    print_body = bool(args.print_body)

    if is_headless:
        logging.info("Running in headless mode.")
    else:
        logging.info("Running in visible mode.")

    win_default = r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
    linux_default = r"/usr/bin/google-chrome"
    browser_path = os.getenv('CHROME_PATH', win_default if os.path.exists(win_default) else linux_default)
    logging.info(f'Chrome Path: {browser_path}, Exists: {os.path.exists(browser_path)}')

    arguments = [
        "-no-first-run",
        # "-force-color-profile=srgb",
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
        logging.info(f'Matrícula: {matricula}')

        driver.get('https://www.trodo.es/')
        time.sleep(1)
        logging.info('Starting Cloudflare bypass.')
        cf_bypasser = CloudflareBypasser(driver)
        cf_bypasser.bypass()

        cookies_map = {c.get("name", ""): c.get("value", "") for c in driver.cookies()}
        if "cf_clearance" not in cookies_map:
            logging.error("No se obtuvo cf_clearance tras el bypass.")
            sys.exit(1)

        capture_js = '''
        window.__captured = [];
        (function(){
          var of = window.fetch;
          window.fetch = function(url, init){
            return of.apply(this, arguments).then(function(r){
              try{
                var u = r.url || '';
                if(u.includes('/rest/V1/partfinder/search/')){
                  var m = (init && init.method) ? String(init.method) : 'GET';
                  var rp = (init && init.referrerPolicy) ? String(init.referrerPolicy) : '';
                  return r.clone().text().then(function(t){
                    window.__captured.push({url:u,method:m,status:String(r.status),ct:(r.headers.get('content-type')||''),rp:rp,body:t});
                    return r;
                  });
                }
              }catch(e){}
              return r;
            });
          };
          var oo = XMLHttpRequest.prototype.open;
          var os = XMLHttpRequest.prototype.send;
          XMLHttpRequest.prototype.open = function(m,u){ this.__u=u; this.__m=m; return oo.apply(this, arguments); };
          XMLHttpRequest.prototype.send = function(b){
            var x=this; x.addEventListener('readystatechange', function(){
              if(x.readyState===4){
                try{
                  var u = x.__u||''; var ct = x.getResponseHeader('content-type')||'';
                  if(u.includes('/rest/V1/partfinder/search/')){
                    window.__captured.push({url:u,method:String(x.__m||'GET'),status:String(x.status),ct:ct,rp:'',body:x.responseText});
                  }
                }catch(e){}
              }
            });
            return os.apply(this, arguments);
          };
        })();
        true;
        '''
        driver.run_js(capture_js)
        api_url = f'https://www.trodo.es/rest/V1/partfinder/search/ES/{matricula}/1'
        logging.info(f'Consultando {api_url} vía UI')
        js_fill_submit = """
        var i = document.querySelector('input[name="reg_number"]');
        if(i){
          i.value = MATRICULA_PLACEHOLDER;
          i.dispatchEvent(new Event('input',{bubbles:true}));
          var b = document.querySelector('button.reg-number-search');
          if(b){ b.click(); }
          else if(i.form){ i.form.dispatchEvent(new Event('submit',{bubbles:true})); }
        }
        true;
        """
        js_fill_submit = js_fill_submit.replace("MATRICULA_PLACEHOLDER", json.dumps(matricula))
        driver.run_js(js_fill_submit)
        max_wait = 6.0
        interval = 0.5
        captured = []
        for _ in range(int(max_wait/interval)):
            captured = driver.run_js("return window.__captured || []") or []
            if any('/rest/V1/partfinder/search/' in (i.get('url') or '') and 'application/json' in (i.get('ct') or '') for i in captured):
                break
            time.sleep(interval)
        logging.info(f'Capturas registradas: {len(captured)}')
        try:
            with open('captured_requests.json','w',encoding='utf-8') as f:
                json.dump(captured, f, ensure_ascii=False, indent=2)
            logging.info('captured_requests.json escrito con éxito')
        except Exception as _:
            logging.warning('No se pudo escribir captured_requests.json')
        capture_url = capture_url or api_url
        def url_matches(u: str) -> bool:
            if capture_regex:
                try:
                    return re.match(capture_regex, u) is not None
                except Exception:
                    return False
            if match_mode == 'prefix':
                return u.startswith(capture_url)
            return u == capture_url
        matches = [i for i in captured if url_matches(i.get('url') or '') and (i.get('method') or 'GET') == 'GET' and 'application/json' in (i.get('ct') or '') and i.get('status')=='200']
        if not matches:
            logging.error('No se capturó respuesta JSON del endpoint con el criterio de URL (exact/prefix/regex) y método GET.')
            sys.exit(1)
        if select_mode.startswith('index:'):
            try:
                idx = int(select_mode.split(':',1)[1])
                target = matches[idx]
            except Exception:
                target = matches[0]
        elif select_mode == 'last':
            target = matches[-1]
        else:
            target = matches[0]
        logging.info(f'Selección: {select_mode}; coincidencias: {len(matches)}; url: {target.get("url")}; method: {target.get("method")}; refPolicy: {target.get("rp", "")}')
        logging.info(f'Longitud del body capturado: {len(target.get("body", ""))}')
        if print_body:
            try:
                print(target.get("body", ""))
            except Exception:
                logging.warning('No se pudo imprimir el body capturado.')
        try:
            parsed_data = json.loads(target.get("body", ""))
        except Exception:
            logging.error('La respuesta capturada no es JSON válido.')
            sys.exit(1)

        def get_data(data, path, default=None):
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
                    return default
                if current is default and default is not None:
                    return default
            return current

        data = parsed_data
        vin_item = None
        brand_item = None
        full_model_item = None
        model_item = None
        variant_item = None
        fuel_item = None
        liters_item = None
        year_item = None
        year_from_item = None
        year_to_item = None
        ccm_item = None
        kw_ps_item = None
        engine_item = None

        if isinstance(data, list) and data:
            root = data[0]
            vin_item = (root.get('attributes', {}) or {}).get('vin')
            rel = root.get('relationships', {}) or {}
            data_list = rel.get('data', []) or []
            values = data_list[0].get('values', []) if data_list else []
            if len(values) > 0:
                brand_item = (values[0].get('label', {}) or {}).get('name')
            if len(values) > 1:
                model_item = (values[1].get('label', {}) or {}).get('name')
            if len(values) > 2:
                full_model_item = values[2].get('url_key') or (values[2].get('label', {}) or {}).get('name')
            spec = (values[-1].get('label', {}) if values else {}) or {}
            variant_item = spec.get('name')
            fuel_item = spec.get('engine_fuel') or spec.get('engine_fuel_default')
            liters_item = spec.get('liters') or spec.get('engine_liters')
            year_item = spec.get('year')
            year_from_item = spec.get('year_from')
            year_to_item = spec.get('year_to')
            ccm_item = spec.get('ccm')
            kw_ps_item = spec.get('kw_ps')
            eng = spec.get('engine')
            if isinstance(eng, list) and eng:
                engine_item = eng[0]
            else:
                engine_item = eng

        car_json = {
            "MATRICULA": matricula,
            "VIN": vin_item,
            "Marca": brand_item,
            "Modelo Completo": full_model_item,
            "Modelo": model_item,
            "Variante": variant_item,
            "Combustible": fuel_item,
            "Litros": liters_item,
            "Año": year_item,
            "Año Desde": year_from_item,
            "Año Hasta": year_to_item,
            "CCM": ccm_item,
            "KW/PS": kw_ps_item,
            "Engine": engine_item
        }

        print(json.dumps(car_json, ensure_ascii=False))

    except Exception as e:
        logging.error(f"A ocurrido un error: {e}")
        raise

    finally:
        logging.info('Closing the browser.')
        driver.quit()


if __name__ == '__main__':
    main()
