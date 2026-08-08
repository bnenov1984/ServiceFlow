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


def normalize_eik(value: str) -> str:
    """ЕИК/БУЛСТАТ: strip incidental surrounding whitespace only — matches
    the trim-before-validate convention every normalizer here follows. Does
    not validate format; see is_valid_eik. Used identically by both the
    seller (Company.requisites) and buyer-company (Customer.company_requisites)
    contracts — one canonical rule, not two (docs/ACCOUNTANT_REVIEW.md §3 R1)."""
    return value.strip()


def is_valid_eik(value: str) -> bool:
    """Conservative structural check only: digits, and one of the two
    legally valid lengths — 9 (primary Commercial Register entity) or 13
    (VAT sub-registration/branch). No checksum/modulus algorithm and no
    registry lookup: docs/ACCOUNTANT_REVIEW.md doesn't establish a single
    unambiguous format, so this deliberately stays permissive rather than
    risk rejecting a valid business. Expects an already-normalized value
    (see normalize_eik)."""
    return value.isdigit() and len(value) in (9, 13)
