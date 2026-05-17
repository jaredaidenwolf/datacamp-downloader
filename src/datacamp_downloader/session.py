import os
import pickle
from pathlib import Path

from webdriver_manager.chrome import ChromeDriverManager

# Prefer top-level undetected_chromedriver (works with Selenium 4); fallback to v2.
try:
    import undetected_chromedriver as uc
except Exception:
    import undetected_chromedriver.v2 as uc

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .constants import HOME_PAGE, SESSION_FILE
from .datacamp_utils import Datacamp
from .json_fetch import JsonFetchError, extract_json_text, parse_json_response


class Session:
    def __init__(self) -> None:
        self.savefile = Path(SESSION_FILE)
        self.datacamp = self.load_datacamp()

    def save(self):
        self.datacamp.session = None
        pickled = pickle.dumps(self.datacamp)
        self.savefile.write_bytes(pickled)

    def load_datacamp(self):
        if self.savefile.exists():
            datacamp = pickle.load(self.savefile.open("rb"))
            datacamp.session = self
            return datacamp
        return Datacamp(self)

    def reset(self):
        try:
            os.remove(SESSION_FILE)
        except OSError:
            pass
        if hasattr(self, "driver"):
            try:
                self.driver.quit()
            except Exception:
                pass
            del self.driver

    def _setup_driver(self, headless=True):
        try:
            options = uc.ChromeOptions()
        except Exception:
            options = ChromeOptions()

        try:
            options.headless = headless
        except Exception:
            if headless:
                options.add_argument("--headless=new")

        options.add_argument("--no-first-run")
        options.add_argument("--no-service-autorun")
        options.add_argument("--password-store=basic")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-browser-side-navigation")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-notifications")
        options.add_argument("--content-shell-hide-toolbar")
        options.add_argument("--top-controls-hide-threshold")
        options.add_argument("--force-app-mode")
        options.add_argument("--hide-scrollbars")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        package_dir = os.path.dirname(os.path.abspath(__file__))
        profile_dir = os.path.join(package_dir, "dc_chrome_profile")
        os.makedirs(profile_dir, exist_ok=True)
        options.add_argument(f"--user-data-dir={profile_dir}")

        service = ChromeService(executable_path=ChromeDriverManager().install())
        try:
            self.driver = uc.Chrome(service=service, options=options)
        except Exception:
            self.driver = webdriver.Chrome(service=service, options=options)

        self.driver.set_script_timeout(60)

    def _ensure_on_datacamp(self):
        if "datacamp.com" not in (self.driver.current_url or ""):
            self.driver.get(HOME_PAGE)
            self.bypass_cloudflare(HOME_PAGE)

    def start(self, headless=False):
        if hasattr(self, "driver"):
            try:
                _ = self.driver.current_url
            except Exception:
                del self.driver
            else:
                if self.datacamp.token:
                    self._ensure_on_datacamp()
                    self.add_token(self.datacamp.token)
                return

        self._setup_driver(headless)
        self.driver.get(HOME_PAGE)
        self.bypass_cloudflare(HOME_PAGE)
        if self.datacamp.token:
            self.add_token(self.datacamp.token)

    def bypass_cloudflare(self, url):
        try:
            self.get_element_by_id("cf-spinner-allow-5-secs")
            self.driver.get(url)
        except Exception:
            pass

    def get(self, url):
        self.start()
        self.driver.get(url)
        self.bypass_cloudflare(url)
        return self.driver.page_source

    def _fetch_via_browser(self, url: str) -> str:
        self.start()
        self._ensure_on_datacamp()

        result = self.driver.execute_async_script(
            """
            const url = arguments[0];
            const done = arguments[arguments.length - 1];
            fetch(url, {
                credentials: 'include',
                headers: { Accept: 'application/json' },
            })
            .then(async (response) => {
                const body = await response.text();
                done({
                    ok: response.ok,
                    status: response.status,
                    contentType: response.headers.get('content-type') || '',
                    body: body,
                });
            })
            .catch((err) => done({ ok: false, status: 0, body: '', error: String(err) }));
            """,
            url,
        )

        if not result:
            raise JsonFetchError("Browser fetch returned no result.", url=url)

        if result.get("error"):
            raise JsonFetchError(
                f"Browser fetch failed: {result['error']}",
                url=url,
            )

        status = result.get("status", 0)
        body = (result.get("body") or "").strip()
        if status >= 400 or not body:
            raise JsonFetchError(
                f"HTTP {status} with empty or error body.",
                url=url,
                preview=body[:500],
            )

        return body

    def get_json(self, url: str):
        """Load JSON from a DataCamp API URL (navigation first, then in-page fetch)."""
        errors = []

        # Navigate in Chrome first so Cloudflare and cookies apply (fetch alone often 403s).
        try:
            page = self.get(url).strip()
            return parse_json_response(extract_json_text(page), url=url)
        except JsonFetchError as exc:
            errors.append(str(exc))

        try:
            return parse_json_response(self._fetch_via_browser(url), url=url)
        except JsonFetchError as exc:
            errors.append(str(exc))

        raise JsonFetchError(
            "Could not load JSON from DataCamp. " + " | ".join(errors),
            url=url,
        )

    def to_json(self, page: str):
        return parse_json_response(page)

    def get_element_by_id(self, id: str) -> WebElement:
        return self.driver.find_element(By.ID, id)

    def get_element_by_xpath(self, xpath: str) -> WebElement:
        return self.driver.find_element(By.XPATH, xpath)

    def click_element(self, id: str):
        self.get_element_by_id(id).click()

    def wait_for_element_by_css_selector(self, *css: str, timeout: int = 10):
        WebDriverWait(self.driver, timeout).until(
            EC.visibility_of_any_elements_located((By.CSS_SELECTOR, ",".join(css)))
        )

    def add_token(self, token: str):
        self._ensure_on_datacamp()
        existing = self.driver.get_cookie("_dct")
        if existing and existing.get("value") == token:
            return self
        cookie = {
            "name": "_dct",
            "value": token,
            "domain": ".datacamp.com",
            "secure": True,
        }
        self.driver.add_cookie(cookie)
        self.driver.refresh()
        return self
