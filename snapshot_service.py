import os
import sys
import json
import time
import base64
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger("snapshot_service")

# Bộ nhớ đệm tạm thời để tránh spam trình duyệt liên tục gây đầy RAM
_SNAPSHOT_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 8  # Cache 8 giây nếu bấm liên tiếp

BOT_META = {
    "bot3": {
        "id": "bot3",
        "aliases": ["bot3", "iuh"],
        "name": "Bot 3 - IUH (Yuki 3 ĐRL)",
        "school": "Trường ĐH Công nghiệp TP.HCM (IUH)",
        "portal_name": "Cổng Tra cứu ĐRL Sinh viên IUH",
        "portal_url": "https://doantn.iuh.edu.vn/doanvien.html",
        "config_file": "config_iuh.json"
    },
    "bot4": {
        "id": "bot4",
        "aliases": ["bot4", "ufm"],
        "name": "Bot 4 - UFM (Yuki 4 ĐRL)",
        "school": "Trường ĐH Tài chính - Marketing (UFM)",
        "portal_name": "Cổng Hoạt động & Đăng ký Sự kiện UFM",
        "portal_url": "https://hoatdong.ufm.edu.vn/DangKy",
        "config_file": "config_ufm.json"
    },
    "bot5": {
        "id": "bot5",
        "aliases": ["bot5", "ou"],
        "name": "Bot 5 - OU (Yuki 5 ĐRL)",
        "school": "Trường ĐH Mở TP.HCM (OU)",
        "portal_name": "Cổng Điểm rèn luyện OU",
        "portal_url": "https://renluyensv.ou.edu.vn/20261/diemrl/dangkysukien",
        "config_file": "config_ou.json"
    }
}

def resolve_bot_key(bot_query: str) -> Optional[str]:
    q = str(bot_query).lower().strip()
    for key, meta in BOT_META.items():
        if q in meta["aliases"]:
            return key
    return None

def get_snapshot_dir(base_dir: str = None) -> str:
    if not base_dir:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    snap_dir = os.path.join(base_dir, "static", "snapshots")
    os.makedirs(snap_dir, exist_ok=True)
    return snap_dir

def capture_portal_view(bot_query: str, base_dir: str = None, force: bool = False) -> Dict[str, Any]:
    """
    Chụp ảnh màn hình góc nhìn thực tế (POV) của bot bên trong cổng web ĐRL.
    Hỗ trợ: 'bot3' / 'iuh', 'bot4' / 'ufm', 'bot5' / 'ou'
    """
    bot_key = resolve_bot_key(bot_query)
    if not bot_key:
        return {
            "status": "error",
            "message": f"Mã bot '{bot_query}' không hợp lệ. Chỉ hỗ trợ bot3 (IUH), bot4 (UFM), bot5 (OU)."
        }

    now_ts = time.time()
    if not force and bot_key in _SNAPSHOT_CACHE:
        cached = _SNAPSHOT_CACHE[bot_key]
        if now_ts - cached.get("_cached_at", 0) < CACHE_TTL_SECONDS:
            logger.info(f"Returning cached snapshot for {bot_key}")
            return cached["data"]

    meta = BOT_META[bot_key]
    snap_dir = get_snapshot_dir(base_dir)
    out_filename = f"{bot_key}_latest.png"
    out_path = os.path.join(snap_dir, out_filename)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "status": "error",
            "message": "Môi trường thiếu thư viện playwright. Cần: pip install playwright && playwright install chromium"
        }

    result = None
    if bot_key == "bot3":
        result = _capture_iuh(meta, out_path, base_dir)
    elif bot_key == "bot4":
        result = _capture_ufm(meta, out_path, base_dir)
    elif bot_key == "bot5":
        result = _capture_ou(meta, out_path, base_dir)

    if result and result.get("status") == "success":
        if os.path.exists(out_path):
            with open(out_path, "rb") as f:
                img_bytes = f.read()
            result["screenshot_base64"] = base64.b64encode(img_bytes).decode("utf-8")
            result["file_size_bytes"] = len(img_bytes)
            result["image_url"] = f"/static/snapshots/{out_filename}?t={int(now_ts)}"

        _SNAPSHOT_CACHE[bot_key] = {
            "_cached_at": now_ts,
            "data": result
        }

    return result

def _capture_iuh(meta: dict, out_path: str, base_dir: str = None) -> dict:
    from playwright.sync_api import sync_playwright
    if not base_dir:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    cfg_file = os.path.join(base_dir, meta["config_file"])
    
    phpsessid = ""
    username = ""
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                cdata = json.load(f)
            portal = cdata.get("portal", {})
            phpsessid = portal.get("phpsessid", "")
            username = portal.get("username", "")
        except Exception as e:
            logger.warning(f"IUH read config error: {e}")

    try:
        from iuh_scraper import IUHPortalScraper
        scraper = IUHPortalScraper(phpsessid, username=username, config_path=cfg_file)
        if phpsessid:
            scraper.session.cookies.set("PHPSESSID", phpsessid, domain="doantn.iuh.edu.vn")
    except Exception as e:
        logger.warning(f"IUH scraper init warning: {e}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        try:
            context = browser.new_context(viewport={"width": 1280, "height": 800}, ignore_https_errors=True)
            if phpsessid:
                context.add_cookies([{
                    "name": "PHPSESSID",
                    "value": phpsessid,
                    "domain": "doantn.iuh.edu.vn",
                    "path": "/"
                }])
            page = context.new_page()
            page.goto(meta["portal_url"], timeout=30000, wait_until="networkidle")
            page.wait_for_timeout(1500)
            
            title = page.title()
            text_snippet = page.inner_text("body")[:250] if page.locator("body").count() > 0 else ""
            page.screenshot(path=out_path)
            
            return {
                "status": "success",
                "bot_id": meta["id"],
                "bot_name": meta["name"],
                "school": meta["school"],
                "portal_name": meta["portal_name"],
                "portal_url": meta["portal_url"],
                "page_title": title,
                "text_snippet": text_snippet,
                "captured_at": datetime.now(timezone(timedelta(hours=7))).strftime("%d/%m/%Y %H:%M:%S"),
                "account_info": f"MSSV: {username}" if username else "Đang dùng cookie phiên"
            }
        finally:
            browser.close()

def _capture_ufm(meta: dict, out_path: str, base_dir: str = None) -> dict:
    from playwright.sync_api import sync_playwright
    if not base_dir:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    cfg_file = os.path.join(base_dir, meta["config_file"])
    
    cookies_dict = {}
    username = ""
    password = ""
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                cdata = json.load(f)
            pcfg = cdata.get("ufm_portal", {})
            cookies_dict = pcfg.get("cookies", {})
            username = pcfg.get("username", "")
            password = pcfg.get("password", "")
        except Exception as e:
            logger.warning(f"UFM read config error: {e}")

    try:
        from ufm_scraper import UFMPortalScraper
        scraper = UFMPortalScraper(cookies_dict, username, password, config_path=cfg_file)
        scraper.ensure_authenticated()
        for c in scraper.session.cookies:
            cookies_dict[c.name] = c.value
    except Exception as e:
        logger.warning(f"UFM scraper ensure_auth warning: {e}")

    cookie_list = []
    for k, v in cookies_dict.items():
        cookie_list.append({
            "name": k,
            "value": v,
            "domain": "hoatdong.ufm.edu.vn",
            "path": "/"
        })

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        try:
            context = browser.new_context(viewport={"width": 1280, "height": 800}, ignore_https_errors=True)
            if cookie_list:
                context.add_cookies(cookie_list)
            page = context.new_page()
            page.goto(meta["portal_url"], timeout=30000, wait_until="networkidle")
            page.wait_for_timeout(1500)
            
            title = page.title()
            text_snippet = page.inner_text("body")[:250] if page.locator("body").count() > 0 else ""
            page.screenshot(path=out_path)
            
            return {
                "status": "success",
                "bot_id": meta["id"],
                "bot_name": meta["name"],
                "school": meta["school"],
                "portal_name": meta["portal_name"],
                "portal_url": meta["portal_url"],
                "page_title": title,
                "text_snippet": text_snippet,
                "captured_at": datetime.now(timezone(timedelta(hours=7))).strftime("%d/%m/%Y %H:%M:%S"),
                "account_info": f"Tài khoản UFM: {username}" if username else "Đang dùng cookie phiên"
            }
        finally:
            browser.close()

def _capture_ou(meta: dict, out_path: str, base_dir: str = None) -> dict:
    from playwright.sync_api import sync_playwright
    if not base_dir:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    cfg_file = os.path.join(base_dir, meta["config_file"])
    
    cookies_dict = {}
    username = ""
    password = ""
    student_name = ""
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                cdata = json.load(f)
            pcfg = cdata.get("ou_portal", {})
            cookies_dict = pcfg.get("cookies", {})
            username = pcfg.get("username", "")
            password = pcfg.get("password", "")
            student_name = pcfg.get("student_name", "")
        except Exception as e:
            logger.warning(f"OU read config error: {e}")

    cookie_list = []
    try:
        from ou_scraper import OUPortalScraper
        scraper = OUPortalScraper(username=username, password=password, cookies=cookies_dict, config_path=cfg_file)
        ok, _ = scraper.keep_alive()
        if not ok:
            scraper.auto_login()
        for c in scraper.session.cookies:
            cookie_list.append({
                "name": c.name,
                "value": c.value,
                "domain": c.domain or "renluyensv.ou.edu.vn",
                "path": c.path or "/"
            })
    except Exception as e:
        logger.warning(f"OU scraper keep_alive warning: {e}")
        for k, v in cookies_dict.items():
            cookie_list.append({
                "name": k,
                "value": v,
                "domain": "renluyensv.ou.edu.vn",
                "path": "/"
            })

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        try:
            context = browser.new_context(viewport={"width": 1280, "height": 800}, ignore_https_errors=True)
            if cookie_list:
                context.add_cookies(cookie_list)
            page = context.new_page()
            page.goto(meta["portal_url"], timeout=30000, wait_until="load")
            try:
                page.wait_for_selector("div#app, body", timeout=10000)
            except Exception:
                pass
            page.wait_for_timeout(4000)
            
            final_title = page.title() or "Hệ thống Điểm rèn luyện 2026"
            text_snippet = page.inner_text("body")[:250] if page.locator("body").count() > 0 else ""
            page.screenshot(path=out_path)
            
            return {
                "status": "success",
                "bot_id": meta["id"],
                "bot_name": meta["name"],
                "school": meta["school"],
                "portal_name": meta["portal_name"],
                "portal_url": meta["portal_url"],
                "page_title": final_title,
                "text_snippet": text_snippet,
                "captured_at": datetime.now(timezone(timedelta(hours=7))).strftime("%d/%m/%Y %H:%M:%S"),
                "account_info": f"Sinh viên: {student_name} ({username})" if student_name else f"MSSV: {username}"
            }
        finally:
            browser.close()
