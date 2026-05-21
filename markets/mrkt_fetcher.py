import asyncio
import logging
from typing import Optional
from curl_cffi.requests import AsyncSession

from .common import get_webapp_init_data

MRKT_API_URL = "https://api.tgmrkt.io/api/v1"
BOT_USERNAME = "mrkt"
BOT_SHORT_NAME = "app"
PLATFORM = "android"
log = logging.getLogger(__name__)

async def get_token(init_data: str) -> Optional[str]:
    try:
        async with AsyncSession() as s:
            response = await s.post(
                f"{MRKT_API_URL}/auth", 
                json={"data": init_data}, 
                impersonate="chrome110",
                timeout=20
            )
            response.raise_for_status()
            data = response.json()
            return data.get("token")
    except Exception as e:
        log.error("Error getting MRKT token: %s", e)
    return None

async def get_mrkt_prices(collection_name: str, model_name: str, backdrop_name: str) -> tuple[Optional[int], Optional[int]] | tuple[str, str]:
    init_data = await get_webapp_init_data(
        session_name="mrkt",
        bot_username=BOT_USERNAME,
        bot_short_name=BOT_SHORT_NAME,
        platform=PLATFORM,
    )
    if not init_data:
        return "ERROR", "ERROR"

    token = await get_token(init_data)
    if not token:
        return "ERROR", "ERROR"

    headers = {
        "Authorization": f"{token}", 
        "Content-Type": "application/json",
        "Referer": "https://cdn.tgmrkt.io/"
    }

    payload_base = {
        "count": 1,
        "cursor": "",
        "collectionNames": [collection_name],
        "modelNames": [model_name],
        "symbolNames": [],
        "ordering": "Price",
        "lowToHigh": True,
    }

    payload_without = {**payload_base, "backdropNames": []}
    payload_with = {**payload_base, "backdropNames": [backdrop_name]}

    async def fetch(payload: dict) -> Optional[int] | str:
        retries = 3
        delay = 4
        async with AsyncSession() as s:
            for attempt in range(retries):
                try:
                    # اصلاح شده: استفاده از MRKT_API_URL به جای MARKET_API_URL
                    response = await s.post(
                        f"{MRKT_API_URL}/gifts/saling", 
                        headers=headers, 
                        json=payload, 
                        impersonate="chrome110", 
                        timeout=15
                    )
                    
                    if response.status_code == 429:
                        log.warning(f"MRKT Rate Limit (429) hit. Waiting {delay}s...")
                        await asyncio.sleep(delay)
                        continue

                    response.raise_for_status()
                    data = response.json()
                    if gifts := data.get("gifts", []):
                        return int(gifts[0].get("salePrice"))
                    return None
                except Exception as e:
                    log.warning(f"MRKT attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(delay)
            return "ERROR"

    return await asyncio.gather(
        fetch(payload_without),
        fetch(payload_with)
    )
