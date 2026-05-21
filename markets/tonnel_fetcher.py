import json
import logging
import asyncio
from typing import Optional
from curl_cffi import requests

log = logging.getLogger(__name__)

def fetch_sync(payload: dict) -> Optional[float]:
    # تنظیم هدرها و اثر انگشت دقیق برای شبیه‌سازی آیفون جهت عبور از کلودفلر
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://market.tonnel.network",
        "Referer": "https://market.tonnel.network/",
        "X-Requested-With": "org.telegram.messenger",
        "Accept-Language": "en-US,en;q=0.9"
    }
    try:
        # استفاده از impersonate سافاری
        res = requests.post(
            "https://gifts3.tonnel.network/api/pageGifts", 
            headers=headers, 
            json=payload, 
            impersonate="safari15_5", 
            timeout=12
        )
        
        if res.status_code != 200:
            log.warning(f"Tonnel Failed! Status: {res.status_code} - Response: {res.text[:150]}")
            return None
            
        data = res.json()
        
        if isinstance(data, list):
            if not data:
                return None
            return min(item.get("price", float("inf")) for item in data)
        else:
            return None
            
    except Exception as e:
        log.warning(f"Tonnel sync fetch error: {e}")
        return None

async def get_tonnel_prices(gift_name: str, model: str, backdrop: str) -> tuple:
    base_filter = {
        "price": {"$exists": True}, 
        "buyer": {"$exists": False}, 
        "gift_name": gift_name, 
        "model": model, 
        "asset": "TON"
    }
    
    base_payload = {
        "page": 1, 
        "limit": 30, 
        "sort": "{\"price\":1,\"gift_id\":-1}", 
        "ref": 0, 
        "price_range": None, 
        "user_auth": ""
    }
    
    payload_without = {**base_payload, "filter": json.dumps(base_filter)}
    
    filter_with_backdrop = {**base_filter, "backdrop": {"$in": [backdrop]}}
    payload_with = {**base_payload, "filter": json.dumps(filter_with_backdrop)}

    try:
        # اجرای ایمن در ترد جداگانه برای جلوگیری از قفل شدن ربات
        r1, r2 = await asyncio.gather(
            asyncio.to_thread(fetch_sync, payload_without),
            asyncio.to_thread(fetch_sync, payload_with)
        )
        return r1, r2
    except Exception as e:
        log.error(f"Unexpected error in thread executor: {e}")
        return "ERROR", "ERROR"
