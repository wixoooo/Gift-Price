from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List

from utils.converter import ton_to_usd, usd_to_irr, format_irr
from utils.config import SHOW_IRR

# Fixed emoji IDs
EMOJI_TONNEL = "5294315493249809756"
EMOJI_MRKT = "5294334528544863781"
EMOJI_PORTALS = "5291911389600841627"
EMOJI_TON = "5814303180866985097"
EMOJI_TOMAN = "5834836998602365732"


def tg_emoji(emoji_id: Optional[str]) -> str:
    if not emoji_id:
        return ""
    return f'<tg-emoji emoji-id="{emoji_id}">🎁</tg-emoji>'


def b(s: str) -> str:
    return f"<b>{s}</b>"


def fmt_ton(x: float) -> str:
    return f"{x:.2f}"


def fmt_toman(x: float) -> str:
    try:
        return format_irr(x).replace(" IRR", "")
    except Exception:
        return f"{x:,.0f}"


@dataclass
class Section:
    ton_sort: float
    title: str
    ton_line: str
    toman_line: Optional[str]


def _price_lines(
    ton_amount: float,
    ton_to_usd_rate: Optional[float],
    usdt_to_irr_rate: Optional[float],
) -> tuple[str, Optional[str]]:
    ton_line = f" └ {tg_emoji(EMOJI_TON)} {fmt_ton(ton_amount)} <b>TON</b>"
    toman_line = None

    if SHOW_IRR and ton_to_usd_rate and usdt_to_irr_rate:
        usd = ton_to_usd(ton_amount, ton_to_usd_rate)
        irr = usd_to_irr(usd, usdt_to_irr_rate)
        toman = irr / 10
        toman_line = f" └ {tg_emoji(EMOJI_TOMAN)} {fmt_toman(toman)} <b>T</b>"

    return ton_line, toman_line


def _market_title_only_name_linked(
    market_name: str,
    extra_suffix: str,
    market_url: Optional[str],
    market_emoji: str,
) -> str:
    # only the market name is a link (suffix is plain text)
    if market_url:
        return f'{tg_emoji(market_emoji)} <a href="{market_url}">{b(market_name)}</a>{extra_suffix}'
    return f"{tg_emoji(market_emoji)} {b(market_name)}{extra_suffix}"


def build_market_sections(
    *,
    market_name: str,
    market_url: Optional[str],
    market_emoji: str,
    price_simple: Optional[float],
    error_simple: bool,
    price_detailed: Optional[float],
    error_detailed: bool,
    model_name: Optional[str],
    backdrop_name: Optional[str],
    ton_to_usd_rate: Optional[float],
    usdt_to_irr_rate: Optional[float],
    adjustment_factor: float = 1.0,
    is_nano_ton: bool = False,
) -> List[Section]:
    """
    New behavior (per your latest message):
    - DO NOT add sections for errors.
    - Add section only if price exists (not None).
    - Add detailed section only if detailed price exists.
    """
    out: List[Section] = []

    def to_ton(raw: float) -> float:
        base = raw / 1_000_000_000 if is_nano_ton else raw
        return round(base * adjustment_factor, 4)

    # SIMPLE
    if (not error_simple) and (price_simple is not None):
        ton_amt = to_ton(price_simple)
        ton_line, toman_line = _price_lines(ton_amt, ton_to_usd_rate, usdt_to_irr_rate)
        out.append(
            Section(
                ton_sort=ton_amt,
                title=_market_title_only_name_linked(
                    market_name=market_name,
                    extra_suffix="",
                    market_url=market_url,
                    market_emoji=market_emoji,
                ),
                ton_line=ton_line,
                toman_line=toman_line,
            )
        )

    # DETAILED (separate block)
    if (not error_detailed) and (price_detailed is not None):
        ton_amt = to_ton(price_detailed)
        suffix = ""
        if model_name and backdrop_name:
            suffix = f" ({model_name} + {backdrop_name})"
        ton_line, toman_line = _price_lines(ton_amt, ton_to_usd_rate, usdt_to_irr_rate)
        out.append(
            Section(
                ton_sort=ton_amt,
                title=_market_title_only_name_linked(
                    market_name=market_name,
                    extra_suffix=suffix,
                    market_url=market_url,
                    market_emoji=market_emoji,
                ),
                ton_line=ton_line,
                toman_line=toman_line,
            )
        )

    return out


def format_message_like_screenshot(
    *,
    gift_title: str,
    gift_link: str,
    collection_emoji_id: Optional[str],
    model_emoji_id: Optional[str],
    backdrop_emoji_id: Optional[str],
    symbol_emoji_id: Optional[str],
    model_name: Optional[str],
    model_percent: Optional[str],
    backdrop_name: Optional[str],
    backdrop_percent: Optional[str],
    symbol_name: Optional[str],
    symbol_percent: Optional[str],
    sections: List[Section],
) -> str:
    header = f'{tg_emoji(collection_emoji_id)} <a href="{gift_link}">{b(gift_title)}</a>'

    lines: List[str] = [header, ""]

    if model_name:
        pct = f" ({model_percent})" if model_percent else ""
        lines.append(f'{tg_emoji(model_emoji_id)} {b("Model:")} {model_name}{pct}')

    if backdrop_name:
        pct = f" ({backdrop_percent})" if backdrop_percent else ""
        lines.append(f'{tg_emoji(backdrop_emoji_id)} {b("Backdrop:")} {backdrop_name}{pct}')

    if symbol_name:
        pct = f" ({symbol_percent})" if symbol_percent else ""
        lines.append(f'{tg_emoji(symbol_emoji_id)} {b("Symbol:")} {symbol_name}{pct}')

    # If no prices, we keep it clean (per your style)
    if not sections:
        return "\n".join(lines)

    for sec in sorted(sections, key=lambda s: s.ton_sort):
        lines.append("")
        lines.append(sec.title)
        lines.append(sec.ton_line)
        if sec.toman_line:
            lines.append(sec.toman_line)

    return "\n".join(lines)
