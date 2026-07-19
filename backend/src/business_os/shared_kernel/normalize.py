"""Search/duplicate normalization (ADR-010): pure functions, reused by every module.

Rules are Bulgarian-market specific and documented in docs/02 §14.
"""

# Official BG transliteration (Закон за транслитерацията), lowercase source.
_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sht", "ъ": "a",
    "ь": "y", "ю": "yu", "я": "ya",
}


def transliterate(value: str) -> str:
    """Lowercase + Cyrillic→Latin so 'Иван' and 'Ivan' normalize identically."""
    return "".join(_CYR.get(ch, ch) for ch in value.lower().strip())


def normalize_phone(value: str) -> str:
    """Canonical national format: digits only, +359/00359 prefix → leading 0.

    '+359 88 812 3456', '00359888123456' and '0888 123 456' all → '0888123456'.
    """
    digits = "".join(ch for ch in value if ch.isdigit())
    if digits.startswith("00359"):
        digits = "0" + digits[5:]
    elif digits.startswith("359"):
        digits = "0" + digits[3:]
    return digits


def normalize_identifier(value: str) -> str:
    """IMEI/VIN/serial/рег.№: uppercase alphanumerics only (spaces, dashes dropped)."""
    return "".join(ch for ch in value.upper() if ch.isalnum())
