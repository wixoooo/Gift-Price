import re
from typing import Optional, Dict, Any

from utils.session_manager import session_manager

# -------------------------
# Backdrop override mapping (YOUR LIST)
# Case-insensitive matching by normalized name.
# -------------------------
_BACKDROP_EMOJI_MAP = {
    "silver blue": "5352944841972023295",
    "onyx black": "5350352000280203609",
    "desert sand": "5352981727151162098",
    "pistachio": "5353003747448489956",
    "coral red": "5350447013546722716",
    "dark lilac": "5350562329123654168",
    "cobalt blue": "5350317430088436881",
    "turquoise": "5352788152975132922",
    "old gold": "5350591113994471902",
    "french violet": "5352587569412473923",
    "celtic blue": "5353048372158692055",
    "fire engine": "5350287206403575532",
    "feldgrau": "5352761322314433585",
    "deep cyan": "5350293180703082432",
    "malachite": "5350703414504360445",
    "cappuccino": "5352777982492577690",
    "mint green": "5350514444533268718",
    "aquamarine": "5352810186157359790",
    "azure blue": "5350331934192994313",
    "electric indigo": "5352674503845511544",
    "pacific green": "5350624576084673910",
    "electric purple": "5350492454300713987",
    "ranger green": "5352956962369732209",
    "rifle green": "5350593265773085158",
    "ivory white": "5350762955635985201",
    "camo green": "5352564565567632822",
    "mustard": "5352854626183973952",
    "amber": "5350754782313220773",
    "seal brown": "5350311846630950036",
    "shamrock green": "5352572567091706848",
    "jade green": "5350561783662808359",
    "copper": "5350646342978929451",
    "sapphire": "5352678064373399100",
    "grape": "5352566283554553892",
    "khaki green": "5350539230789535022",
    "battleship grey": "5352761322314433585",
    "pacific cyan": "5352810186157359790",
    "black": "5350385797377855605",
    "cyberpunk": "5350437818021741889",
    "chestnut": "5350332891970701000",
    "mexican pink": "5350645724503641793",
    "tomato": "5352654996104054366",
    "carmine": "5352579701032388024",
    "burnt sienna": "5353028233057047523",
    "lavender": "5350418829971327885",
    "mystic pearl": "5353067536302768431",
    "navy blue": "5350393412354868172",
    "hunter green": "5353003747448489956",
    "gunmetal": "5350769453921502282",
    "english violet": "5350562329123654168",
    "fandango": "5350716904996635872",
    "emerald": "5350514444533268718",
    "chocolate": "5353084956690120006",
    "neon blue": "5350390822489591261",
    "dark green": "5352915730683691417",
    "gunship green": "5350563398570512863",
    "tactical pine": "5352640827006943370",
    "marine blue": "5350319036406204406",
    "indigo dye": "5350727633824941647",
    "orange": "5350838027369352798",
    "carrot juice": "5350741399195126135",
    "persimmon": "5350484865093503243",
    "strawberry": "5353067536302768431",
    "caramel": "5350565116557430511",
    "pure gold": "5350498621873753258",
    "lemongrass": "5350660692464668154",
    "light olive": "5352641793374584823",
    "satin gold": "5352987396507990895",
    "raspberry": "5350516183995025028",
    "moonstone": "5350801120715376967",
    "burgundy": "5352758474751119520",
    "midnight blue": "5352916825900353203",
    "purple": "5350815749373989096",
    "sky blue": "5350331934192994313",
    "steel grey": "5352547793720342793",
    "roman silver": "5350510737976492983",
    "pine green": "5350792973162417899",
    "rosewood": "5352644116951894246",
    "platinum": "5350795335394427679",
    "french blue": "5352678064373399100",
}

def _norm(s: Optional[str]) -> str:
    if not s:
        return ""
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s

# cache per collection name
_CACHE: Dict[str, Dict[str, Any]] = {}

async def _fetch_gift(collection_name: str) -> Optional[dict]:
    session = await session_manager.get_session()
    url = f"https://api.changes.tg/gift/{collection_name}"
    try:
        r = await session.get(url, timeout=20)
        if getattr(r, "status_code", None) != 200:
            return None
        return r.json()
    except Exception:
        return None

async def get_changes_emojis(collection_name: str) -> Dict[str, Any]:
    """
    Returns:
      {
        "collection_emoji_id": str|None,
        "model_emoji": {model_name_norm: emoji_id},
        "symbol_emoji": {symbol_name_norm: emoji_id}
      }
    Uses /gift/{collection} endpoint and reads:
      gift.customEmojiId
      emoji.models[].customEmojiId
      emoji.patterns[].customEmojiId
    """
    cn = collection_name.strip()
    if cn in _CACHE:
        return _CACHE[cn]

    data = await _fetch_gift(cn)
    out: Dict[str, Any] = {"collection_emoji_id": None, "model_emoji": {}, "symbol_emoji": {}}

    if isinstance(data, dict):
        gift = data.get("gift") or {}
        if isinstance(gift, dict) and gift.get("customEmojiId"):
            out["collection_emoji_id"] = str(gift["customEmojiId"])

        emoji = data.get("emoji") or {}
        if isinstance(emoji, dict):
            # models
            models = emoji.get("models") or []
            if isinstance(models, list):
                for m in models:
                    if isinstance(m, dict) and m.get("name") and m.get("customEmojiId"):
                        out["model_emoji"][_norm(m["name"])] = str(m["customEmojiId"])

            # symbols are called "patterns" in this API
            patterns = emoji.get("patterns") or []
            if isinstance(patterns, list):
                for p in patterns:
                    if isinstance(p, dict) and p.get("name") and p.get("customEmojiId"):
                        out["symbol_emoji"][_norm(p["name"])] = str(p["customEmojiId"])

    _CACHE[cn] = out
    return out

def get_backdrop_emoji_id(backdrop_name: Optional[str]) -> Optional[str]:
    return _BACKDROP_EMOJI_MAP.get(_norm(backdrop_name))
