import requests
import mwparserfromhell
import json
import re
import time
import os
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import unquote, quote
from typing import Optional

# Selenium imports
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.edge.service import Service as EdgeService
    from selenium.webdriver.edge.options import Options as EdgeOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.microsoft import EdgeChromiumDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("警告: 未安装 selenium 或 webdriver-manager,将无法绕过 JavaScript 验证")

BASE_URL = "https://lanota.fandom.com"
API_URL = f"{BASE_URL}/api.php"

FANDOM_COOKIES_PATH = Path("Data") / "fandom_cookies.json"

_CHROMEDRIVER_PATH = None
_EDGEDRIVER_PATH = None


def _detect_chrome_binary() -> Optional[str]:
    """尝试定位 Chrome/Chromium 浏览器可执行文件路径。

    优先使用环境变量：LANOTA_CHROME_BINARY / CHROME_BINARY。
    若未设置，则尝试常见安装路径。
    """
    env_path = (os.environ.get("LANOTA_CHROME_BINARY") or os.environ.get("CHROME_BINARY") or "").strip().strip('"')
    if env_path:
        p = Path(env_path)
        if p.exists():
            return str(p)

    candidates: list[str] = []
    if os.name == "nt":
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        candidates.extend(
            [
                rf"{program_files}\Google\Chrome\Application\chrome.exe",
                rf"{program_files_x86}\Google\Chrome\Application\chrome.exe",
                rf"{local_app_data}\Google\Chrome\Application\chrome.exe" if local_app_data else "",
                rf"{program_files}\Chromium\Application\chrome.exe",
                rf"{program_files_x86}\Chromium\Application\chrome.exe",
            ]
        )
    else:
        candidates.extend(
            [
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",
                "/usr/bin/chromium",
                "/usr/bin/chromium-browser",
                "/snap/bin/chromium",
            ]
        )

    for c in candidates:
        if not c:
            continue
        p = Path(c)
        if p.exists():
            return str(p)
    return None


def _detect_edge_binary() -> Optional[str]:
    """尝试定位 Microsoft Edge (Chromium) 浏览器可执行文件路径。

    优先使用环境变量：LANOTA_EDGE_BINARY / EDGE_BINARY。
    若未设置，则尝试常见安装路径。
    """
    env_path = (os.environ.get("LANOTA_EDGE_BINARY") or os.environ.get("EDGE_BINARY") or "").strip().strip('"')
    if env_path:
        p = Path(env_path)
        if p.exists():
            return str(p)

    candidates: list[str] = []
    if os.name == "nt":
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        candidates.extend(
            [
                rf"{program_files_x86}\Microsoft\Edge\Application\msedge.exe",
                rf"{program_files}\Microsoft\Edge\Application\msedge.exe",
                rf"{local_app_data}\Microsoft\Edge\Application\msedge.exe" if local_app_data else "",
            ]
        )
    else:
        candidates.extend(
            [
                "/usr/bin/microsoft-edge",
                "/usr/bin/microsoft-edge-stable",
                "/opt/microsoft/msedge/msedge",
            ]
        )

    for c in candidates:
        if not c:
            continue
        p = Path(c)
        if p.exists():
            return str(p)
    return None


def _get_chromedriver_path() -> str:
    global _CHROMEDRIVER_PATH
    if _CHROMEDRIVER_PATH:
        return _CHROMEDRIVER_PATH
    _CHROMEDRIVER_PATH = ChromeDriverManager().install()
    return _CHROMEDRIVER_PATH


def _get_edgedriver_path() -> str:
    global _EDGEDRIVER_PATH
    if _EDGEDRIVER_PATH:
        return _EDGEDRIVER_PATH
    _EDGEDRIVER_PATH = EdgeChromiumDriverManager().install()
    return _EDGEDRIVER_PATH


def _is_client_challenge(text: str) -> bool:
    if not text:
        return False
    # Fandom/Wikia 的挑战页一般会包含这些关键词/资源标识
    lowered = text.lower()
    return (
        "client challenge" in lowered
        or "_fs-ch-" in lowered
        or "fandom" in lowered and "challenge" in lowered
    )


def _load_cookies_to_session(session: requests.Session, cookies_path: Path = FANDOM_COOKIES_PATH) -> bool:
    try:
        if not cookies_path.exists():
            return False
        with open(cookies_path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        if not isinstance(cookies, list):
            return False
        for c in cookies:
            name = c.get("name")
            value = c.get("value")
            if not name:
                continue
            session.cookies.set(
                name,
                value,
                domain=c.get("domain"),
                path=c.get("path", "/"),
            )
        return True
    except Exception:
        return False


def _save_cookies_from_driver(driver, cookies_path: Path = FANDOM_COOKIES_PATH) -> None:
    try:
        cookies_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cookies_path, "w", encoding="utf-8") as f:
            json.dump(driver.get_cookies(), f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _save_driver_cookies_to_session(driver, session: requests.Session) -> None:
    try:
        for c in driver.get_cookies():
            name = c.get("name")
            value = c.get("value")
            if not name:
                continue
            session.cookies.set(
                name,
                value,
                domain=c.get("domain"),
                path=c.get("path", "/"),
            )
    except Exception:
        pass
def get_output_path():
    # 获取上层文件夹的config.py中的lanota_full_path
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.py')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"找不到config.py文件: {config_path}")
    
    # 动态导入config模块
    import importlib.util
    spec = importlib.util.spec_from_file_location("config", config_path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    
    if not hasattr(config, 'lanota_full_path'):
        raise AttributeError("config.py中没有定义lanota_full_path")
    
    SONGS_JSON = config.lanota_full_path
    
    return SONGS_JSON

# ---------- Selenium 辅助函数 ----------

def _env_flag(name: str):
    v = os.environ.get(name)
    if v is None:
        return None
    v = str(v).strip().lower()
    if v in ("1", "true", "yes", "y", "on"):
        return True
    if v in ("0", "false", "no", "n", "off"):
        return False
    return None


def _env_str(name: str) -> Optional[str]:
    v = os.environ.get(name)
    if v is None:
        return None
    v = str(v).strip()
    return v or None


def get_page_with_selenium(url, wait_time=30, *, headless=None, save_cookies=True, debug_name="fandom", session=None):
    """使用 Selenium 获取页面内容。

    headless:
      - None: 先 headless，失败则自动切换为有界面模式（便于手动通过挑战）
      - True/False: 强制模式
    """
    if not SELENIUM_AVAILABLE:
        raise ImportError("需要安装 selenium 和 webdriver-manager: pip install selenium webdriver-manager")
    
    print(f"使用 Selenium 获取页面: {url}")

    # 选择浏览器：chrome / edge
    browser = (os.environ.get("LANOTA_SELENIUM_BROWSER") or "chrome").strip().lower()
    if browser not in ("chrome", "edge"):
        print(f"警告: 未知浏览器 '{browser}'，将使用 chrome")
        browser = "chrome"

    # 驱动来源：auto(默认) / selenium-manager / wdm
    driver_source = (os.environ.get("LANOTA_DRIVER_SOURCE") or "auto").strip().lower()
    if driver_source not in ("auto", "selenium-manager", "wdm"):
        print(f"警告: 未知 LANOTA_DRIVER_SOURCE='{driver_source}'，将使用 auto")
        driver_source = "auto"
    
    # 允许用环境变量覆盖模式
    headless_env = _env_flag("LANOTA_SELENIUM_HEADLESS")
    if headless_env is not None:
        headless = headless_env

    interactive_env = _env_flag("LANOTA_SELENIUM_INTERACTIVE")
    if interactive_env is True:
        headless = False

    if headless is None:
        headless_candidates = [True, False]
    else:
        headless_candidates = [bool(headless)]

    profile_dir = Path("Data") / "selenium_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    last_exc = None
    for run_headless in headless_candidates:
        driver = None
        try:
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

            if browser == "edge":
                edge_options = EdgeOptions()
                edge_binary = _detect_edge_binary()
                if edge_binary:
                    edge_options.binary_location = edge_binary
                if run_headless:
                    edge_options.add_argument("--headless=new")
                edge_options.add_argument("--no-sandbox")
                edge_options.add_argument("--disable-dev-shm-usage")
                edge_options.add_argument("--disable-gpu")
                edge_options.add_argument("--disable-blink-features=AutomationControlled")
                edge_options.add_argument(f"user-agent={ua}")
                edge_options.add_argument(f"--user-data-dir={profile_dir.resolve()}")
                edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                edge_options.add_experimental_option("useAutomationExtension", False)

                edge_options.page_load_strategy = "eager"

                def _create_edge_with_source(source: str):
                    if source == "selenium-manager":
                        return webdriver.Edge(options=edge_options)
                    service = EdgeService(_get_edgedriver_path())
                    return webdriver.Edge(service=service, options=edge_options)

                try:
                    if driver_source == "auto":
                        try:
                            driver = _create_edge_with_source("selenium-manager")
                        except Exception:
                            driver = _create_edge_with_source("wdm")
                    else:
                        driver = _create_edge_with_source(driver_source)
                except Exception as e:
                    msg = str(e)
                    if ("cannot find" in msg.lower() and "binary" in msg.lower()) and not edge_binary:
                        raise RuntimeError(
                            "未找到 Microsoft Edge 浏览器可执行文件。\n"
                            "请在服务器安装 Edge，或设置环境变量 LANOTA_EDGE_BINARY 指向 msedge.exe 路径。\n"
                            "例如：C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
                        ) from e
                    raise
            else:
                chrome_options = Options()

                chrome_binary = _detect_chrome_binary()
                if chrome_binary:
                    chrome_options.binary_location = chrome_binary
                if run_headless:
                    chrome_options.add_argument("--headless=new")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--disable-blink-features=AutomationControlled")
                chrome_options.add_argument(f"user-agent={ua}")
                chrome_options.add_argument(f"--user-data-dir={profile_dir.resolve()}")
                chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                chrome_options.add_experimental_option("useAutomationExtension", False)

                # 不等待所有资源加载完，避免卡死在 driver.get
                chrome_options.page_load_strategy = "eager"

                def _create_chrome_with_source(source: str):
                    if source == "selenium-manager":
                        return webdriver.Chrome(options=chrome_options)
                    service = Service(_get_chromedriver_path())
                    return webdriver.Chrome(service=service, options=chrome_options)

                try:
                    if driver_source == "auto":
                        try:
                            driver = _create_chrome_with_source("selenium-manager")
                        except Exception:
                            driver = _create_chrome_with_source("wdm")
                    else:
                        driver = _create_chrome_with_source(driver_source)
                except Exception as e:
                    # 服务器常见问题：找不到 Chrome/Chromium 或驱动版本不匹配
                    msg = str(e)
                    low = msg.lower()
                    if "cannot find chrome binary" in low and not chrome_binary:
                        raise RuntimeError(
                            "未找到 Chrome/Chromium 浏览器可执行文件。\n"
                            "请在服务器安装 Chrome/Chromium，或设置环境变量 LANOTA_CHROME_BINARY 指向浏览器路径。\n"
                            "例如：C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
                        ) from e
                    if "only supports chrome version" in low or "session not created" in low:
                        raise RuntimeError(
                            "ChromeDriver 与 Chrome 版本不匹配。\n"
                            "建议：升级 selenium(>=4.6) 并使用 Selenium Manager（设置 LANOTA_DRIVER_SOURCE=selenium-manager 或默认 auto）。\n"
                            "或清理 webdriver-manager 缓存后重试（删除 ~/.wdm 或 %USERPROFILE%\\.wdm）。"
                        ) from e
                    raise
            driver.set_page_load_timeout(30)

            mode_label = "headless" if run_headless else "interactive"
            print(f"正在加载页面... ({mode_label})")
            try:
                driver.get(url)
            except Exception:
                # 页面资源卡住时，尝试停止继续加载，保留已加载的 DOM
                try:
                    driver.execute_script("window.stop();")
                except Exception:
                    pass

            # 让 JS 有机会跑一下
            time.sleep(2)

            # 等待关键元素出现（尽量宽松）
            selectors = [
                "table.wikitable",
                "table.sortable",
                "#mw-content-text table",
                "table",
            ]
            end_time = time.time() + wait_time
            found = False
            while time.time() < end_time:
                for sel in selectors:
                    if driver.find_elements(By.CSS_SELECTOR, sel):
                        found = True
                        break
                if found:
                    break
                time.sleep(0.5)

            if session is not None:
                _save_driver_cookies_to_session(driver, session)
            if save_cookies:
                _save_cookies_from_driver(driver)

            page_source = driver.page_source
            print(f"成功获取页面内容 (长度: {len(page_source)})")

            if not found:
                # 仍然返回源码，交给后续解析；同时落盘便于排查
                dump_path = Path("Data") / f"{debug_name}_last.html"
                try:
                    dump_path.parent.mkdir(parents=True, exist_ok=True)
                    dump_path.write_text(page_source, encoding="utf-8")
                    print(f"未检测到目标表格，已保存页面源码: {dump_path}")
                except Exception:
                    pass

            return page_source

        except Exception as e:
            last_exc = e
            print(f"Selenium 获取页面失败: {e}")
            if driver:
                try:
                    shot = Path("Data") / f"{debug_name}_error.png"
                    driver.save_screenshot(str(shot))
                    print(f"已保存错误截图: {shot}")
                except Exception:
                    pass
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

    raise last_exc


def fetch_wikitext(session: requests.Session, page_name: str) -> str:
    """获取页面 wikitext：API(query revisions) -> API(parse) -> action=raw -> action=edit -> Selenium 兜底。"""
    debug = True

    # 清理 page_name（避免带上 ?/# 造成 API 查不到）
    page_name = (page_name or "").split("#", 1)[0].split("?", 1)[0].strip()
    if not page_name:
        return ""

    # 用于 /wiki/{title} 路径的标题必须 URL 编码（尤其是包含 '/' 的页面名）
    # 同时把空格转为 '_' 更贴近 MediaWiki 默认形式
    page_name_path = quote(page_name.replace(" ", "_"), safe=":()'!-._~")

    def _looks_like_html(text: str) -> bool:
        if not text:
            return False
        t = text.lstrip().lower()
        return t.startswith("<!doctype") or t.startswith("<html") or t.startswith("<div")

    def _sanitize_wikitext(text: str) -> str:
        if not text:
            return ""
        # 避免把挑战页/HTML 当成 wikitext
        if _is_client_challenge(text) or _looks_like_html(text):
            return ""
        return text

    # 1) API: action=query + revisions（通常比 parse 更稳）
    try:
        params = {
            "action": "query",
            "prop": "revisions",
            "titles": page_name,
            "rvprop": "content",
            "rvslots": "main",
            "redirects": 1,
            "format": "json",
            "formatversion": 2,
        }
        r = session.get(API_URL, params=params, timeout=15)
        if r.status_code == 200:
            try:
                json_data = r.json()
                pages = (json_data.get("query") or {}).get("pages") or []
                if pages and isinstance(pages, list):
                    revs = pages[0].get("revisions") or []
                    if revs and isinstance(revs, list):
                        slots = (revs[0].get("slots") or {}).get("main") or {}
                        content = slots.get("content")
                        content = _sanitize_wikitext(content or "")
                        if content:
                            if debug:
                                print(f"  [wikitext] query+revisions OK: {page_name}")
                            return content
            except json.JSONDecodeError:
                pass
    except requests.exceptions.RequestException:
        pass

    # 2) API: action=parse
    try:
        params = {"action": "parse", "page": page_name, "prop": "wikitext", "redirects": 1, "format": "json"}
        r = session.get(API_URL, params=params, timeout=15)
        if r.status_code == 200:
            try:
                json_data = r.json()
                wikitext = json_data.get("parse", {}).get("wikitext", {}).get("*", "")
                wikitext = _sanitize_wikitext(wikitext)
                if wikitext:
                    if debug:
                        print(f"  [wikitext] parse OK: {page_name}")
                    return wikitext
            except json.JSONDecodeError:
                pass
    except requests.exceptions.RequestException:
        pass

    # 3) action=raw
    raw_url = f"{BASE_URL}/wiki/{page_name_path}?action=raw"
    try:
        r = session.get(raw_url, timeout=15)
        txt = _sanitize_wikitext(r.text or "")
        if r.status_code == 200 and txt:
            if debug:
                print(f"  [wikitext] raw OK: {page_name}")
            return txt
    except requests.exceptions.RequestException:
        pass

    # 4) action=edit：从 textarea 里抠源码（页面本身是 HTML，但源码在 textarea 中）
    edit_url = f"{BASE_URL}/wiki/{page_name_path}?action=edit"
    try:
        r = session.get(edit_url, timeout=15)
        if r.status_code == 200 and r.text and not _is_client_challenge(r.text):
            soup = BeautifulSoup(r.text, "html.parser")
            ta = soup.find("textarea", {"name": "wpTextbox1"}) or soup.find("textarea", {"id": "wpTextbox1"})
            if ta is not None:
                content = _sanitize_wikitext(ta.get_text("", strip=False) or "")
                if content:
                    if debug:
                        print(f"  [wikitext] edit OK: {page_name}")
                    return content
    except requests.exceptions.RequestException:
        pass

    # 5) Selenium 兜底（通常需要先用交互模式通过挑战）
    use_selenium = _env_flag("LANOTA_WIKITEXT_USE_SELENIUM")
    if use_selenium is None:
        use_selenium = True  # 默认启用 Selenium 兜底
    if SELENIUM_AVAILABLE and use_selenium:
        if debug:
            print(f"  [wikitext] selenium fallback: {page_name}")
        # 优先抓 edit 页面里的 textarea (强制交互模式让用户手动过验证)
        html = get_page_with_selenium(edit_url, wait_time=10, debug_name="fandom_edit", session=session, headless=False)
        soup = BeautifulSoup(html, "html.parser")
        ta = soup.find("textarea", {"name": "wpTextbox1"}) or soup.find("textarea", {"id": "wpTextbox1"})
        if ta is not None:
            content = _sanitize_wikitext(ta.get_text("", strip=False) or "")
            if content:
                return content

        # 再退回 raw 页面（有时会把内容渲染进 <pre>）
        html = get_page_with_selenium(raw_url, wait_time=10, debug_name="fandom_raw", session=session)
        soup = BeautifulSoup(html, "html.parser")
        pre = soup.find("pre")
        if pre and pre.get_text(strip=False):
            content = _sanitize_wikitext(pre.get_text(strip=False) or "")
            if content:
                return content

        # 最后兜底：纯文本（不保证是 wikitext）
        return ""

    if debug:
        print(f"  [wikitext] failed: {page_name}")

    return ""

# ---------- 工具函数 ----------

def clean_ref(text):
    return re.sub(r"<ref.*?>.*?<\/ref>", "", text or "", flags=re.DOTALL)

def clean_wiki_links(text):
    if not text:
        return ""
    text = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    return text.strip()

def replace_br(text):
    return re.sub(r"<br\s*/?>", " | ", text or "")

def classify(chap_left):
    left = chap_left.lower()
    if left in ('time limited', 'event'):
        return 'event'
    if left in ('∞', 'inf'):
        return 'subscription'
    if left.isdigit():
        return 'main'
    # 仅 SS+数字 归为 side；其它 字母+数字 归为 expansion
    if re.match(r'^ss\d+$', left):
        return 'side'
    if re.match(r'^[A-Za-z]+\d+$', chap_left):
        return 'expansion'
    if re.match(r'^[A-Za-z]+$', chap_left):
        return 'expansion'
    return 'other'

def get_final_url(session, url, max_retries=3):
    for _ in range(max_retries):
        try:
            resp = session.get(url, allow_redirects=True, timeout=10)
            return resp.url
        except requests.exceptions.RequestException:
            time.sleep(1)
    return url

def check_missing_fields(song):
    """检查歌曲的缺失字段，返回缺失字段列表"""
    missing = []
    
    # 检查 bpm
    if not song.get('bpm') or song.get('bpm', '').strip() == '':
        missing.append('bpm')
    
    # 检查 time
    if not song.get('time') or song.get('time', '').strip() == '':
        missing.append('time')
    
    # 检查 notes（各个难度）
    notes = song.get('notes', {})
    notes_missing = []
    for difficulty in ['whisper', 'acoustic', 'ultra', 'master']:
        if not notes.get(difficulty) or notes.get(difficulty, '').strip() == '':
            notes_missing.append(difficulty)
    
    if notes_missing:
        missing.append(f"notes({','.join(notes_missing)})")
    
    # 检查 Legacy 中的 notes（只有当 Legacy 存在且非空时才检查）
    if 'Legacy' in song and isinstance(song['Legacy'], dict) and song['Legacy']:
        legacy = song['Legacy']
        legacy_notes_missing = []
        for field in ['MaxWhisper', 'MaxAcoustic', 'MaxUltra', 'MaxMaster']:
            if not legacy.get(field) or legacy.get(field, '').strip() == '':
                legacy_notes_missing.append(field)
        
        if legacy_notes_missing:
            missing.append(f"legacy_notes({','.join(legacy_notes_missing)})")
    
    return missing

def update_song_from_wiki(session, song):
    """从 wiki 全量更新歌曲信息"""
    if 'source_url' not in song:
        return None, []
    
    try:
        final_url = get_final_url(session, song['source_url'])
        raw_page = final_url.rsplit('/wiki/', 1)[-1]
        page_name = unquote(raw_page)

        wikitext = fetch_wikitext(session, page_name)
        if not wikitext:
            print("  无法获取 wikitext（可能被挑战页拦截），跳过")
            return None, []
        wikicode = mwparserfromhell.parse(wikitext)
        tmpl = next((t for t in wikicode.filter_templates() if t.name.strip().lower() == 'song'), None)

        def get_field(field):
            if not tmpl or not tmpl.has(field):
                return ''
            val = str(tmpl.get(field).value)
            val = clean_ref(val)
            val = clean_wiki_links(val)
            return replace_br(val).strip()

        # 记录原始的关键字段状态
        original_bpm_missing = not song.get('bpm') or song.get('bpm', '').strip() == ''
        original_time_missing = not song.get('time') or song.get('time', '').strip() == ''
        original_notes_missing = []
        for difficulty in ['whisper', 'acoustic', 'ultra', 'master']:
            if not song.get('notes', {}).get(difficulty) or song.get('notes', {}).get(difficulty, '').strip() == '':
                original_notes_missing.append(difficulty)
        
        # === 全量更新所有字段 ===
        
        # 更新基本信息
        new_bpm = get_field('BPM')
        if new_bpm:
            song['bpm'] = new_bpm
        
        new_time = get_field('Time')
        if new_time:
            song['time'] = new_time
        
        # 更新其他基本字段
        new_artist = get_field('Artist')
        if new_artist:
            song['artist'] = new_artist
        
        new_version = get_field('Version')
        if new_version:
            song['version'] = new_version
        
        new_area = get_field('Area')
        if new_area:
            song['area'] = new_area
        
        new_genre = get_field('Genre')
        if new_genre:
            song['genre'] = new_genre
        
        new_vocals = get_field('Vocals')
        if new_vocals:
            song['vocals'] = new_vocals
        
        new_cover_art = get_field('Cover Art')
        if new_cover_art:
            song['cover_art'] = new_cover_art
        
        # 处理谱师：SYM -> 空
        chart_design = get_field('Chart Design')
        if chart_design:
            if chart_design.strip().upper() == 'SYM':
                song['chart_design'] = ''
            # 注释掉因为fandom的不准，用我手动加上的
            # else:
            #     song['chart_design'] = chart_design
        
        # 更新难度
        if 'difficulty' not in song:
            song['difficulty'] = {}
        for difficulty, field_name in [('whisper', 'DiffWhisper'), ('acoustic', 'DiffAcoustic'),
                                       ('ultra', 'DiffUltra'), ('master', 'DiffMaster')]:
            new_value = get_field(field_name)
            if new_value:
                song['difficulty'][difficulty] = new_value
        
        # 更新 notes
        if 'notes' not in song:
            song['notes'] = {}
        
        for difficulty, field_name in [('whisper', 'MaxWhisper'), ('acoustic', 'MaxAcoustic'), 
                                       ('ultra', 'MaxUltra'), ('master', 'MaxMaster')]:
            new_value = get_field(field_name)
            if new_value:
                song['notes'][difficulty] = new_value
        
        # 更新 Trivia
        if '==Trivia==' in wikitext:
            trivia = [clean_wiki_links(clean_ref(item.strip())) for item in re.findall(r"\*([^\n]+)", wikitext.split('==Trivia==')[1])]
            if trivia:
                song['Trivia'] = trivia
        
        # 更新 Legacy（只有当 Legacy 存在且非空时才更新）
        if 'Legacy' in song and isinstance(song['Legacy'], dict) and song['Legacy']:
            for t in wikicode.filter_templates():
                if t.name.strip().lower() == 'legacytable':
                    for param in t.params:
                        key = clean_wiki_links(str(param.name).strip())
                        val = replace_br(clean_ref(str(param.value).strip()))
                        if val:
                            song['Legacy'][key] = val
        
        # === 只返回关键字段的更新状态 ===
        updated_fields = []
        
        # 检查 bpm 是否被更新
        if original_bpm_missing and new_bpm:
            updated_fields.append('bpm')
        
        # 检查 time 是否被更新
        if original_time_missing and new_time:
            updated_fields.append('time')
        
        # 检查 notes 是否被更新
        notes_updated = []
        for difficulty in original_notes_missing:
            field_name_map = {'whisper': 'MaxWhisper', 'acoustic': 'MaxAcoustic', 
                            'ultra': 'MaxUltra', 'master': 'MaxMaster'}
            new_value = get_field(field_name_map[difficulty])
            if new_value:
                notes_updated.append(difficulty)
        
        if notes_updated:
            updated_fields.append(f"notes({','.join(notes_updated)})")
        
        # 检查 legacy notes 是否被更新（只报告关键字段）
        if 'Legacy' in song and isinstance(song['Legacy'], dict) and song['Legacy']:
            legacy_notes_missing = []
            for field in ['MaxWhisper', 'MaxAcoustic', 'MaxUltra', 'MaxMaster']:
                if not song['Legacy'].get(field) or song['Legacy'].get(field, '').strip() == '':
                    legacy_notes_missing.append(field)
            
            if legacy_notes_missing:
                # 检查这些字段是否在更新后有值了
                legacy_updated = []
                for t in wikicode.filter_templates():
                    if t.name.strip().lower() == 'legacytable':
                        for field in legacy_notes_missing:
                            if t.has(field):
                                new_value = replace_br(clean_ref(str(t.get(field).value).strip()))
                                if new_value:
                                    legacy_updated.append(field)
                
                if legacy_updated:
                    updated_fields.append(f"legacy_notes({','.join(legacy_updated)})")
        
        return song, updated_fields
    
    except Exception as e:
        print(f"  更新失败: {e}")
        return None, []

# ---------- 主程序 ----------

def main():
    SONGS_JSON = get_output_path()
    SONGS_JSON.parent.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    })
    if _load_cookies_to_session(session):
        print(f"已加载 Fandom cookies: {FANDOM_COOKIES_PATH}")

    # 读取已处理数据
    try:
        with open(SONGS_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = []

    # 记录原始数据长度
    original_count = len(data)
    
    print("=" * 60)
    print("开始检查和更新乐曲数据")
    print("=" * 60)
    
    # 检查现有歌曲的缺失信息
    songs_with_missing = []
    for song in data:
        missing = check_missing_fields(song)
        if missing:
            songs_with_missing.append({
                'song': song,
                'missing': missing,
                'chapter': song['chapter']
            })
    
    if songs_with_missing:
        print(f"\n发现 {len(songs_with_missing)} 首歌曲存在缺失信息：")
        for item in songs_with_missing:
            print(f"  - {item['song']['title']} (章节: {item['chapter']})")
            print(f"    缺失: {', '.join(item['missing'])}")
    else:
        print("\n✓ 所有现有歌曲信息完整")

    # 构建去重集合：真实标题和外部标题
    existing_titles = {item['title'].lower() for item in data}
    existing_outside = {item.get('title_outside', '').lower() for item in data if item.get('title_outside')}
    existing_chapters_lower = {item['chapter'].lower() for item in data}

    print("\n正在搜索乐曲列表……")
    
    # 尝试使用 Selenium 获取页面(因为 Fandom 现在可能需要 JavaScript)
    try:
        if SELENIUM_AVAILABLE:
            # 先用 action=render，通常更轻量、也更容易出现表格
            page_html = get_page_with_selenium(
                f"{BASE_URL}/wiki/Songs?action=render",
                debug_name="songs",
                session=session,
            )
            if _is_client_challenge(page_html) or "<table" not in page_html.lower():
                page_html = get_page_with_selenium(
                    f"{BASE_URL}/wiki/Songs",
                    debug_name="songs",
                    session=session,
                )
            # selenium 可能刚写入 cookies（同一轮运行也要立刻加载到 session）
            _load_cookies_to_session(session)
            soup = BeautifulSoup(page_html, 'html.parser')
        else:
            # 回退到普通请求(可能会失败)
            print("警告: 未安装 selenium,尝试使用普通请求(可能失败)...")
            resp = session.get(f"{BASE_URL}/wiki/Songs?action=render", timeout=30)
            resp.raise_for_status()
            if _is_client_challenge(resp.text):
                resp = session.get(f"{BASE_URL}/wiki/Songs", timeout=30)
                resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
    except Exception as e:
        raise Exception(f"无法访问 Fandom Wiki: {e}")
    
    # 检查是否找到了乐曲表格（尝试多种方式查找）
    wikitable = soup.find('table', {'class': 'wikitable'})
    
    # 如果找不到 wikitable class，尝试查找包含 sortable 的表格
    if wikitable is None:
        wikitable = soup.find('table', {'class': 'sortable'})
    
    # 尝试查找 class 包含 wikitable 的表格（部分匹配）
    if wikitable is None:
        wikitable = soup.find('table', class_=lambda x: x and 'wikitable' in x)
    
    # 尝试查找 article-table
    if wikitable is None:
        wikitable = soup.find('table', {'class': 'article-table'})
    
    # 尝试查找任何 class 包含 table 的表格
    if wikitable is None:
        wikitable = soup.find('table', class_=lambda x: x and 'table' in x.lower())
    
    # 最后尝试：查找页面中第一个包含 "Dream goes on" 的表格（第一首歌）
    if wikitable is None:
        for table in soup.find_all('table'):
            if table.find(string=re.compile(r'Dream goes on', re.IGNORECASE)):
                wikitable = table
                break
    
    if wikitable is None:
        # 调试信息：打印页面中找到的所有表格的 class
        all_tables = soup.find_all('table')
        table_classes = [str(t.get('class', [])) for t in all_tables]
        raise Exception(f"无法找到乐曲列表表格。页面中找到 {len(all_tables)} 个表格，class: {table_classes[:5]}")

    # 收集页面上的所有乐曲链接及初步标题
    songs_info = []
    wiki_link_re = re.compile(r"^(?:/wiki/|https?://lanota\.fandom\.com/wiki/).+")
    ns_block = re.compile(
        r"^(?:/wiki/|https?://lanota\.fandom\.com/wiki/)(File:|Category:|Template:|Help:|Special:|User:|User_talk:|Talk:|Portal:)")
    for row in wikitable.find_all('tr'):
        first_td = row.find('td')
        link = None
        if first_td:
            link = first_td.find('a', href=wiki_link_re)
        if not link:
            link = row.find('a', href=wiki_link_re)
        if not link or not link.get('href'):
            continue
        href = link['href']
        if ns_block.match(href):
            continue
        if href.startswith('/wiki/Songs') or '/wiki/Songs' in href:
            continue
        abs_href = f"{BASE_URL}{href}" if href.startswith('/wiki/') else href
        display_title = (link.get('title') or link.get_text(strip=True) or '').strip()
        if not display_title:
            continue
        songs_info.append({'href': abs_href, 'display_title': display_title})

    # 去重（保持顺序）
    seen = set()
    songs_info_dedup = []
    for it in songs_info:
        key = (it['href'], it['display_title'].lower())
        if key in seen:
            continue
        seen.add(key)
        songs_info_dedup.append(it)
    songs_info = songs_info_dedup

    print(f"共找到 {len(songs_info)} 首乐曲")

    # 第一轮：按 title 初步匹配，包括外部title
    candidates = [info for info in songs_info
                  if info['display_title'].lower() not in existing_titles
                  and info['display_title'].lower() not in existing_outside]
    skipped = len(songs_info) - len(candidates)
    print(f"{skipped} 首已通过初步匹配，跳过；剩余 {len(candidates)} 首待进一步核对")

    if _env_flag("LANOTA_ONLY_SONG_LIST") is True:
        print("已设置 LANOTA_ONLY_SONG_LIST=1：仅抓取 Songs 列表，提前退出")
        return {
            'before': original_count,
            'missing_songs': len(songs_with_missing),
            'missing_updated': 0,
            'missing_results': [],
            'added': 0,
            'added_titles': [],
            'total': len(data)
        }

    # 收集所有需要处理的任务：缺失信息的歌曲 + 新歌曲候选
    print(f"\n准备处理：")
    print(f"  - 缺失信息更新: {len(songs_with_missing)} 首")
    print(f"  - 新歌曲候选: {len(candidates)} 首")
    
    update_results = []  # 缺失信息更新结果
    new_count = 0        # 新增歌曲计数
    new_titles = []      # 新增歌曲标题
    
    # ========== 处理缺失信息的歌曲 ==========
    if songs_with_missing:
        print("\n" + "-" * 60)
        print("开始更新缺失信息...")
        print("-" * 60)
        
        for idx, item in enumerate(songs_with_missing, 1):
            song = item['song']
            missing = item['missing']
            print(f"\n[更新 {idx}/{len(songs_with_missing)}] {song['title']}")
            print(f"  缺失项: {', '.join(missing)}")
            
            updated_song, updated_fields = update_song_from_wiki(session, song)
            
            if updated_song and updated_fields:
                # 在原数据中找到并更新
                for i, s in enumerate(data):
                    if s['chapter'] == song['chapter']:
                        data[i] = updated_song
                        break
                
                update_results.append({
                    'title': song['title'],
                    'chapter': song['chapter'],
                    'missing': missing,
                    'updated': updated_fields,
                    'success': True
                })
                print(f"  ✓ 成功更新: {', '.join(updated_fields)}")
            else:
                update_results.append({
                    'title': song['title'],
                    'chapter': song['chapter'],
                    'missing': missing,
                    'updated': [],
                    'success': False
                })
                print(f"  ✗ 更新失败或无新数据")
            
            time.sleep(0.5)
    
    # ========== 处理新歌曲候选 ==========
    if candidates:
        print("\n" + "-" * 60)
        print("开始处理新歌曲候选...")
        print("-" * 60)

    for info in candidates:
        final_url = get_final_url(session, info['href'])
        raw_page = final_url.rsplit('/wiki/', 1)[-1]
        page_name = unquote(raw_page)

        wikitext = fetch_wikitext(session, page_name)
        if not wikitext:
            print(f"  无法获取 wikitext ({page_name})，跳过")
            continue
        wikicode = mwparserfromhell.parse(wikitext)
        tmpl = next((t for t in wikicode.filter_templates() if t.name.strip().lower() == 'song'), None)

        def get_field(field):
            if not tmpl or not tmpl.has(field):
                return ''
            val = str(tmpl.get(field).value)
            val = clean_ref(val)
            val = clean_wiki_links(val)
            return replace_br(val).strip()

        # 处理章节：time limited 转 Event
        raw_chap_left = get_field('Chapter')
        left_standard = raw_chap_left.replace('∞', 'Inf')
        chap_left_clean = 'Event' if left_standard.lower() == 'time limited' else left_standard
        chap_right = get_field('Id')
        real_chapter = f"{chap_left_clean}-{chap_right}"
        
        # 处理谱师：SYM -> 空字符串
        chart_design = get_field('Chart Design')
        if chart_design.strip().upper() == 'SYM':
            chart_design = ''

        # 深度匹配：按章节小写匹配
        if real_chapter.lower() in existing_chapters_lower:
            print(f"  已存在章节 '{real_chapter}'，跳过")
            # 记录外部标题以免下次再深度匹配
            # 在已存在条目里找到对应章节，添加title_outside字段
            for item in data:
                if item['chapter'].lower() == real_chapter.lower():
                    if 'title_outside' not in item:
                        item['title_outside'] = info['display_title']
                    break
            continue

        # 解析标题：取更长的那个
        field_title = get_field('Song') or ''
        display_title = info['display_title'] or ''
        real_title = field_title if len(field_title) >= len(display_title) else display_title

        category = 'event' if chap_left_clean == 'Event' else classify(chap_left_clean)

        new_count += 1
        new_titles.append(real_title)
        print(f"\n[新增 {new_count}] {real_title} (章节 {real_chapter})")

        song = {
            'id': len(data) + 1,
            'title': real_title,
            'title_outside': info['display_title'],
            'artist': get_field('Artist'),
            'chapter': real_chapter,
            'category': category,
            'difficulty': {
                'whisper': get_field('DiffWhisper'),
                'acoustic': get_field('DiffAcoustic'),
                'ultra': get_field('DiffUltra'),
                'master': get_field('DiffMaster')
            },
            'time': get_field('Time'),
            'bpm': get_field('BPM'),
            'version': get_field('Version'),
            'area': get_field('Area'),
            'genre': get_field('Genre'),
            'vocals': get_field('Vocals'),
            'chart_design': chart_design,
            'cover_art': get_field('Cover Art'),
            'notes': {
                'whisper': get_field('MaxWhisper'),
                'acoustic': get_field('MaxAcoustic'),
                'ultra': get_field('MaxUltra'),
                'master': get_field('MaxMaster')
            },
            'source_url': final_url
        }

        # 附加 Trivia
        if '==Trivia==' in wikitext:
            trivia = [clean_wiki_links(clean_ref(item.strip())) for item in re.findall(r"\*([^\n]+)", wikitext.split('==Trivia==')[1])]
            song['Trivia'] = trivia

        # 附加 Legacy Table
        legacy = {}
        for t in wikicode.filter_templates():
            if t.name.strip().lower() == 'legacytable':
                for param in t.params:
                    key = clean_wiki_links(str(param.name).strip())
                    val = replace_br(clean_ref(str(param.value).strip()))
                    legacy[key] = val
        song['Legacy'] = legacy

        # 写入并更新去重集合
        data.append(song)
        existing_chapters_lower.add(real_chapter.lower())
        existing_titles.add(real_title.lower())
        existing_outside.add(info['display_title'].lower())
        
        time.sleep(0.5)

    # 统一保存所有更新
    with open(SONGS_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # ========== 输出最终报告 ==========
    print("\n" + "=" * 60)
    print("处理完成总结")
    print("=" * 60)
    print(f"原有歌曲数: {original_count}")
    
    # 缺失信息更新报告
    if songs_with_missing:
        success_count = sum(1 for r in update_results if r['success'])
        print(f"\n【缺失信息更新】")
        print(f"  待更新: {len(songs_with_missing)} 首")
        print(f"  成功更新: {success_count} 首")
        
        if update_results:
            print(f"\n  详细结果:")
            for result in update_results:
                status = "✓ 成功" if result['success'] else "✗ 失败"
                print(f"    {status} | {result['title']} (章节: {result['chapter']})")
                print(f"      原缺失: {', '.join(result['missing'])}")
                if result['updated']:
                    print(f"      已更新: {', '.join(result['updated'])}")
                else:
                    print(f"      已更新: 无")
    else:
        success_count = 0
        print(f"\n【缺失信息更新】")
        print(f"  ✓ 所有歌曲信息完整")
    
    # 新增歌曲报告
    print(f"\n【新增乐曲】")
    print(f"  新增: {new_count} 首")
    
    print(f"\n【总计】")
    print(f"  当前总数: {len(data)} 首")
    print("=" * 60)
    
    return {
        'before': original_count,
        'missing_songs': len(songs_with_missing),
        'missing_updated': success_count,
        'missing_results': update_results,
        'added': new_count,
        'added_titles': new_titles,
        'total': len(data)
    }


if __name__ == '__main__':
    main()
