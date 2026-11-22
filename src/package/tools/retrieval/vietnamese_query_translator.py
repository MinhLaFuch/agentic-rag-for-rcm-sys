"""Deterministic Vietnamese-to-English e-commerce query translator/expander for cross-lingual retrieval.

Used as an opt-in query bridge when the catalog is English (Electronics, Video_Games, Toys_and_Games)
and end-users ask in Vietnamese (with or without diacritics). Preserves English tokens, model codes,
and brand names verbatim while mapping Vietnamese product phrases to English catalog terminology.
"""

from __future__ import annotations

import re
import unicodedata


def _strip_accents(text: str) -> str:
    # Map Vietnamese d-stroke explicitly because NFKD does not decompose đ/Đ.
    text = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


# Multi-word phrases checked longest-first on accent-stripped lowercase text.
_PHRASE_MAP: tuple[tuple[str, str], ...] = (
    # Electronics / Audio / Peripherals
    ("tai nghe chong on", "noise cancelling headphones"),
    ("tai nghe chup tai", "over ear headphones"),
    ("tai nghe nhet tai", "in ear earbuds"),
    ("tai nghe khong day", "wireless bluetooth headphones earbuds"),
    ("tai nghe gaming", "gaming headset microphone"),
    ("tai nghe", "headphones earbuds headset"),
    ("ban phim co", "mechanical keyboard"),
    ("ban phim khong day", "wireless keyboard"),
    ("ban phim gaming", "gaming keyboard"),
    ("ban phim", "keyboard"),
    ("chuot cong thai hoc", "ergonomic mouse"),
    ("chuot khong day", "wireless mouse"),
    ("chuot gaming", "gaming mouse"),
    ("chuot may tinh", "computer mouse"),
    ("chuot", "mouse"),
    ("loa bluetooth", "bluetooth portable speaker"),
    ("loa khong day", "wireless speaker"),
    ("loa vi tinh", "computer speaker"),
    ("loa", "speaker"),
    ("o cung di dong", "external portable hard drive ssd"),
    ("o cung ssd", "ssd solid state drive"),
    ("o cung", "hard drive storage ssd"),
    ("the nho", "memory card sd microsd"),
    ("cap sac nhanh", "fast charging cable usb"),
    ("cap sac", "charging cable usb"),
    ("day cap", "cable cord adapter"),
    ("sac du phong", "portable power bank charger"),
    ("cu sac", "wall charger power adapter"),
    ("bo sac", "charger power adapter"),
    ("pin sac", "rechargeable battery"),
    ("kiem tra pin", "battery tester checker"),
    ("man hinh may tinh", "computer monitor display"),
    ("man hinh", "monitor screen display"),
    ("may anh", "digital camera"),
    ("ong kinh", "camera lens"),
    ("chan may anh", "camera tripod"),
    ("may quay", "camcorder video camera"),
    ("bo phat wifi", "wifi router wireless"),
    ("bo kich song", "wifi range extender"),
    ("tay cam choi game", "game controller gamepad"),
    ("tay cam game", "game controller gamepad"),
    ("tay cam", "controller gamepad"),
    ("may choi game", "gaming console"),
    ("dia game", "video game disc"),
    ("tro choi dien tu", "video game"),
    ("choi game", "gaming video game"),
    ("phu kien", "accessories"),
    ("op lung", "protective case cover"),
    ("bao da", "leather case cover"),
    ("tui chong soc", "carrying case sleeve"),
    ("mieng dan man hinh", "screen protector"),
    ("gia do dien thoai", "phone stand mount holder"),
    ("gia do", "stand mount holder"),
    ("dong ho thong minh", "smartwatch"),
    ("den pin", "flashlight"),
    ("may tinh bang", "tablet"),
    ("dien thoai", "phone smartphone"),
    ("may tinh xach tay", "laptop"),
    ("may tinh", "computer pc"),
    ("micro thu am", "microphone studio"),
    ("micro", "microphone"),
    # Toys & Games
    ("do choi lap rap", "building blocks construction toy set"),
    ("do choi xep hinh", "building blocks puzzle toy"),
    ("xep hinh", "puzzle jigsaw blocks"),
    ("ghep hinh", "jigsaw puzzle"),
    ("gau bong", "plush stuffed animal toy"),
    ("thu nhoi bong", "stuffed animal plush toy"),
    ("bup be", "doll playset"),
    ("xe dieu khien tu xa", "remote control rc car"),
    ("dieu khien tu xa", "remote control rc"),
    ("xe mo hinh", "diecast toy car vehicle"),
    ("mo hinh", "action figure model collectible"),
    ("tro choi gia dinh", "family board game card game"),
    ("co vua", "chess board game"),
    ("bo bai", "card game deck"),
    ("bai tay", "playing cards"),
    ("board game", "board game tabletop"),
    ("do choi tre em", "kids children toy"),
    ("do choi cho be", "kids toddler baby toy"),
    ("do choi giao duc", "educational learning stem toy"),
    ("do choi nha tam", "bath toy water"),
    ("do choi", "toy playset"),
    ("qua tang", "gift"),
    ("tre em", "kids children"),
    ("be trai", "boys kids"),
    ("be gai", "girls kids"),
    # Attributes / Modifiers
    ("chong on", "noise cancelling"),
    ("khong day", "wireless bluetooth"),
    ("co day", "wired"),
    ("chong nuoc", "waterproof"),
    ("yen tinh", "quiet silent"),
    ("em ai", "quiet silent"),
    ("nho gon", "compact mini portable"),
    ("di dong", "portable travel"),
    ("van phong", "office ergonomic"),
    ("sac nhanh", "fast charging"),
    ("ben bi", "durable heavy duty"),
    ("chinh hang", "official authentic"),
    ("gia re", "budget affordable"),
    ("cao cap", "premium pro"),
    ("mau den", "black"),
    ("mau trang", "white"),
    ("mau do", "red"),
    ("mau xanh", "blue green"),
    ("mau hong", "pink"),
)

# Pure Vietnamese conversational stopwords to strip after phrase extraction so they do not pollute BM25 OR queries.
_VI_STOPWORDS = frozenset({
    "toi", "minh", "ban", "cho", "can", "muon", "tim", "kiem", "goi", "mua",
    "mot", "cai", "chiec", "bo", "san", "pham", "loai", "nao", "tot", "nhat",
    "hay", "dep", "ben", "re", "dat", "duoi", "tren", "khoang", "tam", "gia",
    "cua", "va", "hoac", "voi", "de", "lam", "dung", "rat", "nhieu", "co",
    "khong", "duoc", "la", "nay", "kia", "do", "nhung", "cac", "tu", "den",
    "xin", "giup", "tu", "van", "xem", "thu", "nhe", "nha", "a", "oi", "ve",
})

# Common Vietnamese diacritic characters or multi-word hints to detect Vietnamese input quickly.
_VI_DIACRITIC_RE = re.compile(
    r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[a-z0-9][a-z0-9'-]*")


class VietnameseQueryTranslator:
    """Translates Vietnamese shopping queries into clean English catalog keywords while preserving EN/model terms."""

    def __init__(self, extra_phrases: dict[str, str] | None = None) -> None:
        pairs = list(_PHRASE_MAP)
        if extra_phrases:
            for vi, en in extra_phrases.items():
                pairs.append((_strip_accents(vi.lower()).strip(), en.strip()))
        # Sort longest phrase first to prefer specific multi-word matches over single words.
        self._phrases: list[tuple[str, re.Pattern[str], str]] = [
            (vi, re.compile(rf"(?<!\w){re.escape(vi)}(?!\w)"), en)
            for vi, en in sorted(pairs, key=lambda kv: len(kv[0]), reverse=True)
        ]

    def is_vietnamese(self, query: str) -> bool:
        if not query:
            return False
        if _VI_DIACRITIC_RE.search(query):
            return True
        stripped = _strip_accents(query.lower())
        for _, pat, _ in self._phrases:
            if pat.search(stripped):
                return True
        return False

    def translate(self, query: str) -> dict[str, object]:
        """Return {'original', 'translated', 'is_vietnamese', 'matched_phrases'}."""
        if not query or not query.strip():
            return {"original": query or "", "translated": "", "is_vietnamese": False, "matched_phrases": []}
        has_diacritics = bool(_VI_DIACRITIC_RE.search(query))
        stripped = _strip_accents(query.lower())
        matched_phrases: list[str] = []
        en_tokens: list[str] = []
        residual = stripped

        for vi, pat, en in self._phrases:
            if pat.search(residual):
                matched_phrases.append(vi)
                en_tokens.extend(en.split())
                residual = pat.sub(" ", residual)

        is_vi = has_diacritics or bool(matched_phrases)
        if not is_vi:
            return {"original": query, "translated": query.strip(), "is_vietnamese": False, "matched_phrases": []}

        # Keep remaining English/brand/model tokens (e.g. "sony", "logitech", "4k", "usb-c", "ps5", "lego").
        for tok in _WORD_RE.findall(residual):
            if tok in _VI_STOPWORDS or len(tok) <= 1 or tok.isdigit():
                continue
            en_tokens.append(tok)

        deduped = list(dict.fromkeys(en_tokens))
        translated = " ".join(deduped).strip() or stripped.strip()
        return {
            "original": query,
            "translated": translated,
            "is_vietnamese": True,
            "matched_phrases": matched_phrases,
        }
