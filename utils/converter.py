import asyncio
import time
from functools import wraps
from typing import Optional, Dict, Any, Callable
import logging
import re
from utils.session_manager import session_manager

log = logging.getLogger(__name__)

def _parse_float(val) -> float:
    """تابع کمکی برای حذف کاما و استخراج دقیق عدد"""
    if not val:
        return 0.0
    try:
        s = str(val).replace(",", "").replace("٬", "").strip()
        s = re.sub(r"[^\d\.]", "", s)
        return float(s) if s else 0.0
    except Exception:
        return 0.0

def async_ttl_cache(ttl: int) -> Callable:
    def decorator(func: Callable) -> Callable:
        cache: Dict[str, Any] = {}
        lock = asyncio.Lock()

        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            now = time.time()
            if "result" in cache and now - cache.get("timestamp", 0) < ttl:
                return cache["result"]

            async with lock:
                now = time.time()
                if "result" in cache and now - cache.get("timestamp", 0) < ttl:
                    return cache["result"]

                result = await func(*args, **kwargs)
                if result is not None:
                    cache["result"] = result
                    cache["timestamp"] = now
                return result

        return wrapper
    return decorator

@async_ttl_cache(ttl=200)
async def get_rates() -> Optional[Dict[str, Optional[float]]]:
    ton_to_usd_rate: Optional[float] = None
    ton_to_irr_rate: Optional[float] = None

    session = await session_manager.get_session()

    # تلاش اول: استفاده از ای‌پی‌آی رسمی نوبیتکس برای جفت ارزهای تون (بسیار دقیق و مستقیم)
    try:
        resp = await session.get("https://apiv2.nobitex.ir/market/stats?srcCurrency=ton", timeout=12)
        # رفع خطای AttributeError با چک کردن امن وضعیت پاسخ
        status_code = getattr(resp, "status_code", getattr(resp, "status", None))
        
        if status_code == 200:
            data = resp.json() or {}
            stats = data.get("stats", {})
            
            # قیمت مستقیم تون به ریال نوبیتکس -> تبدیل به تومان (تقسیم بر ۱۰)
            ton_rls = stats.get("ton-rls", {}).get("latest")
            if ton_rls:
                ton_to_irr_rate = _parse_float(ton_rls) / 10
            
            # قیمت مستقیم تون به تتر (دلار)
            ton_usdt = stats.get("ton-usdt", {}).get("latest")
            if ton_usdt:
                ton_to_usd_rate = _parse_float(ton_usdt)
    except Exception as e:
        log.warning("Nobitex direct TON API failed: %s", e)

    # تلاش دوم (پشتیبان): اگر نوبیتکس مستقیم پاسخ نداد، از ترکیب تون‌اپی و قیمت تتر نوبیتکس استفاده کن
    if ton_to_usd_rate is None or ton_to_irr_rate is None:
        try:
            ton_task = session.get("https://tonapi.io/v2/rates?tokens=ton&currencies=usd", timeout=10)
            usdt_task = session.get("https://apiv2.nobitex.ir/market/stats?srcCurrency=usdt", timeout=10)
            results = await asyncio.gather(ton_task, usdt_task, return_exceptions=True)

            # استخراج قیمت دلار تون از Tonapi
            if not isinstance(results[0], Exception):
                r = results[0]
                r_status = getattr(r, "status_code", getattr(r, "status", None))
                if r_status == 200:
                    t_data = r.json() or {}
                    val = t_data.get("rates", {}).get("TON", {}).get("prices", {}).get("USD")
                    if val:
                        ton_to_usd_rate = _parse_float(val)

            # استخراج قیمت تتر برای تبدیل ضربدری (تون دلار * تتر تومان = تون تومان)
            if not isinstance(results[1], Exception):
                r = results[1]
                r_status = getattr(r, "status_code", getattr(r, "status", None))
                if r_status == 200:
                    n_data = r.json() or {}
                    usdt_rls = n_data.get("stats", {}).get("usdt-rls", {}).get("latest")
                    if usdt_rls and ton_to_usd_rate:
                        usdt_toman = _parse_float(usdt_rls) / 10
                        ton_to_irr_rate = ton_to_usd_rate * usdt_toman

        except Exception as e:
            log.warning("Fallback rates calculation failed: %s", e)

    return {
        "ton_to_usd": ton_to_usd_rate,
        "ton_to_irr": ton_to_irr_rate,
    }

def ton_to_usd(ton: float, ton_usd_rate: float) -> float:
    return round(ton * ton_usd_rate, 2)

def ton_to_irr(ton: float, ton_irr_rate: float) -> int:
    return int(ton * ton_irr_rate)

def format_irr(irr: int) -> str:
    return f"{irr:,}"
