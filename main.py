from typing import Optional
import asyncio
import re
import logging
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

from markets.client_manager import client_manager
from utils.logger_setup import setup_logging
from utils.converter import get_rates
from utils.config import (
    BOT_TOKEN,
    TONNEL_URL,
    PORTALS_URL,
    MRKT_URL,
    CHANNEL_NAME,
    CHANNEL_URL,
)
from utils.session_manager import session_manager
from core.gift_parser import parse_gift_page
from core.market_aggregator import fetch_all_market_prices

from utils.changes_api import get_changes_emojis, get_backdrop_emoji_id
from core.message_formatter import (
    format_message_like_screenshot,
    build_market_sections,
    EMOJI_TONNEL,
    EMOJI_PORTALS,
    EMOJI_MRKT,
)

setup_logging()
log = logging.getLogger(__name__)

TONNEL_PRICE_ADJUSTMENT = 1.06
# دیکشنری برای نگهداری زمان آخرین درخواست هر کاربر
user_cooldowns = {}


def create_reply_markup(bot_username: str) -> InlineKeyboardMarkup:
    # فقط دکمه Add to group نگه‌داشته شد
    keyboard = [
        [InlineKeyboardButton("Add to group", url=f"https://t.me/{bot_username}?startgroup=new")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def fetch_gift_data(link: str) -> tuple[Optional[str], Optional[dict]]:
    session = await session_manager.get_session()
    link_task = session.get(link, timeout=15)
    rates_task = get_rates()

    try:
        link_resp, rates_data = await asyncio.gather(link_task, rates_task)

        if not link_resp.ok:
            log.warning("Failed to fetch gift link %s. Status: %d", link, link_resp.status)
            return None, None

        html = link_resp.text
        return html, rates_data
    except Exception as e:
        log.error("Error fetching gift data: %s", e)
        return None, None


def build_price_message(
    link: str,
    gift_details: dict,
    market_prices: dict,
    ton_to_usd_rate: Optional[float],
    usdt_to_irr_rate: Optional[float],
    *,
    collection_emoji_id: Optional[str],
    model_emoji_id: Optional[str],
    backdrop_emoji_id: Optional[str],
    symbol_emoji_id: Optional[str],
) -> str:
    sections = []

    # Tonnel
    sections += build_market_sections(
        market_name="Tonnel",
        market_url=TONNEL_URL,
        market_emoji=EMOJI_TONNEL,
        price_simple=market_prices["tonnel"].price_simple,
        error_simple=market_prices["tonnel"].error_simple,
        price_detailed=market_prices["tonnel"].price_detailed,
        error_detailed=market_prices["tonnel"].error_detailed,
        model_name=gift_details.get("model_name"),
        backdrop_name=gift_details.get("backdrop_name"),
        ton_to_usd_rate=ton_to_usd_rate,
        usdt_to_irr_rate=usdt_to_irr_rate,
        adjustment_factor=TONNEL_PRICE_ADJUSTMENT,
        is_nano_ton=False,
    )

    # Portals
    sections += build_market_sections(
        market_name="Portals",
        market_url=PORTALS_URL,
        market_emoji=EMOJI_PORTALS,
        price_simple=market_prices["portals"].price_simple,
        error_simple=market_prices["portals"].error_simple,
        price_detailed=market_prices["portals"].price_detailed,
        error_detailed=market_prices["portals"].error_detailed,
        model_name=gift_details.get("model_name"),
        backdrop_name=gift_details.get("backdrop_name"),
        ton_to_usd_rate=ton_to_usd_rate,
        usdt_to_irr_rate=usdt_to_irr_rate,
        adjustment_factor=1.0,
        is_nano_ton=False,
    )

    # MRKT (nanoTON -> TON)
    sections += build_market_sections(
        market_name="MRKT",
        market_url=MRKT_URL,
        market_emoji=EMOJI_MRKT,
        price_simple=market_prices["mrkt"].price_simple,
        error_simple=market_prices["mrkt"].error_simple,
        price_detailed=market_prices["mrkt"].price_detailed,
        error_detailed=market_prices["mrkt"].error_detailed,
        model_name=gift_details.get("model_name"),
        backdrop_name=gift_details.get("backdrop_name"),
        ton_to_usd_rate=ton_to_usd_rate,
        usdt_to_irr_rate=usdt_to_irr_rate,
        adjustment_factor=1.0,
        is_nano_ton=True,
    )

    gift_title = gift_details.get("title") or "Gift"

    return format_message_like_screenshot(
        gift_title=gift_title,
        gift_link=link,
        collection_emoji_id=collection_emoji_id,
        model_emoji_id=model_emoji_id,
        backdrop_emoji_id=backdrop_emoji_id,
        symbol_emoji_id=symbol_emoji_id,
        model_name=gift_details.get("model_name"),
        model_percent=gift_details.get("model_percent"),
        backdrop_name=gift_details.get("backdrop_name"),
        backdrop_percent=gift_details.get("backdrop_percent"),
        symbol_name=gift_details.get("symbol_name"),
        symbol_percent=gift_details.get("symbol_percent"),
        sections=sections,
    )


async def process_gift_link(link: str, message, bot_username: str) -> None:
    if not link.startswith("http"):
        link = "https://" + link
    log.info("Processing gift link: %s", link)

    try:
        html, rates_data = await fetch_gift_data(link)

        if html is None:
            await message.reply_text("Could not fetch the gift link. It might be invalid or expired.")
            return

        if not rates_data:
            await message.reply_text("Error fetching exchange rates. Please try again.")
            return

        gift_details = parse_gift_page(html, link)

        if not gift_details.get("model_name"):
            log.info("No model details found for link %s. Assuming it's an invalid gift.", link)
            await message.reply_text(
                f"Gift not found! The link may be incorrect or expired:\n{link}",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return

        market_prices = await fetch_all_market_prices(gift_details)

        collection_name = gift_details.get("gift_name_clean") or ""
        changes = await get_changes_emojis(collection_name) if collection_name else {}

        collection_emoji_id = changes.get("collection_emoji_id")

        model_key = (gift_details.get("model_name") or "").strip().lower()
        symbol_key = (gift_details.get("symbol_name") or "").strip().lower()

        model_emoji_id = (changes.get("model_emoji") or {}).get(model_key)
        symbol_emoji_id = (changes.get("symbol_emoji") or {}).get(symbol_key)

        backdrop_emoji_id = get_backdrop_emoji_id(gift_details.get("backdrop_name"))

        output = build_price_message(
            link,
            gift_details,
            market_prices,
            rates_data["ton_to_usd"],
            rates_data["usdt_to_irr"],
            collection_emoji_id=collection_emoji_id,
            model_emoji_id=model_emoji_id,
            backdrop_emoji_id=backdrop_emoji_id,
            symbol_emoji_id=symbol_emoji_id,
        )

        reply_markup = create_reply_markup(bot_username)
        await message.reply_text(
            output,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=reply_markup,
        )

    except Exception as e:
        log.error("Error in process_gift_link: %s", e, exc_info=True)
        await message.reply_text("An unexpected error occurred while processing the gift link.")


def extract_gift_link(text: str) -> Optional[str]:
    match = re.search(r"(https?://)?t\.me/nft/[\w-]+", text)
    return match.group(0) if match else None


async def price_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    text = (message.text or "").strip().lower()
    
    text_to_search = ""
    # اگر کلمه دقیقاً p بود و روی یک پیام ریپلای شده بود
    if text == "p" and message.reply_to_message and message.reply_to_message.text:
        text_to_search = message.reply_to_message.text
    # در صورتی که در متن علامت + بود (مثلا + در کنار لینک NFT)
    elif "+" in text:
        text_to_search = message.text
    else:
        text_to_search = message.text

    link = extract_gift_link(text_to_search)

    if link:
        user_id = update.effective_user.id
        current_time = time.time()
        
        # بررسی محدودیت ۳۰ ثانیه استفاده برای هر کاربر
        if user_id in user_cooldowns and current_time - user_cooldowns[user_id] < 30:
            await message.reply_text(
                '<tg-emoji emoji-id="5440660757194744323">‼️</tg-emoji> <b>محدودیت استفاده هر 30 ثانیه برای هر کاربر است</b>',
                parse_mode="HTML"
            )
            return
        
        user_cooldowns[user_id] = current_time
        
        target_message = message.reply_to_message if message.reply_to_message else message
        await process_gift_link(link, target_message, context.bot.username)


async def send_welcome_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    welcome_text = (
        "Hello!\n"
        "With this bot, you can send Telegram gift links to get their prices across all three markets "
        "(Portals, Tonnel, MRKT). Just send the gift link, and the bot will display the prices.\n"
    )

    reply_markup = create_reply_markup(context.bot.username)
    await update.message.reply_text(
        welcome_text,
        parse_mode="HTML",
        reply_markup=reply_markup,
    )


def main() -> None:
    if not BOT_TOKEN:
        log.error("BOT_TOKEN not found! Please set it in your .env file.")
        return

    async def on_startup(application) -> None:
        log.info("Bot application starting up...")

    async def on_shutdown(application) -> None:
        log.info("Bot application shutting down. Stopping Telethon clients and closing aiohttp session...")
        await client_manager.stop_all()
        await session_manager.close()
        log.info("All resources cleaned up successfully.")

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .connect_timeout(20.0)
        .read_timeout(20.0)
        .build()
    )

    app.add_handler(CommandHandler(["start", "help"], send_welcome_message))
    
    # حساسیت فقط به + درون متن یا ارسال فقط حرف p
    app.add_handler(MessageHandler(filters.Regex(re.compile(r'\+|(?i)^p$')), price_command_handler))

    log.info("Bot is now running. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
