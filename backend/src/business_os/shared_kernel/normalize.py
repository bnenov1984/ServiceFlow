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


# order-workflow-revamp Q11: Bulgarian plates mix Cyrillic and Latin letters
# that are visually identical, depending on who/what typed them — a Cyrillic
# keyboard gives "СА1234ВХ", a Latin one gives "CA1234BX", same physical
# plate. Only the ~11 letters that are genuinely homoglyphs in the Cyrillic
# alphabet used on BG plates; this is deliberately narrower than
# `transliterate` above (which maps every Cyrillic letter, including ones
# with no Latin look-alike, e.g. "ж"→"zh" — wrong tool here, it would turn
# one plate character into several). Folds to Latin since `normalize_identifier`
# already uppercases, and ASCII alphanumerics are what a VIN/reg-№ index
# compares.
_PLATE_HOMOGLYPHS = str.maketrans("АВЕКМНОРСТУХ", "ABEKMHOPCTYX")


def fold_plate_homoglyphs(value: str) -> str:
    """Applied on top of `normalize_identifier` for `reg` identifiers only
    (VIN is Latin-only by spec, every other identifier kind is untouched)."""
    return value.translate(_PLATE_HOMOGLYPHS)


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


def normalize_vat_number(value: str) -> str:
    """BG VAT identification number: strip incidental surrounding whitespace,
    uppercase only the "bg"/"Bg"/etc. prefix (never the digits, which are
    numeric anyway) — same trim-before-validate convention as normalize_eik.
    Does not validate format; see is_valid_vat_number."""
    stripped = value.strip()
    if stripped[:2].lower() == "bg":
        return "BG" + stripped[2:].strip()
    return stripped


def is_valid_vat_number(value: str) -> bool:
    """Conservative structural check only, mirroring is_valid_eik: a BG VAT
    number is law-confirmed (docs/ACCOUNTANT_REVIEW.md §3 R2) to be
    `"BG" + ЕИК` — never an independently issued value — so the digit
    portion must satisfy the exact same 9-or-13-digit shape as an EIK. No
    checksum/modulus algorithm and no registry lookup, for the same reason
    is_valid_eik stays permissive. Expects an already-normalized value (see
    normalize_vat_number)."""
    return value[:2] == "BG" and is_valid_eik(value[2:])


def derive_seller_vat_number(eik: str) -> str:
    """The seller's own VAT identification number: LAW-CONFIRMED
    (docs/ACCOUNTANT_REVIEW.md §3 R1/R2, ЗДДС чл. 94, ал. 2) to always be
    `"BG" + ЕИК` — never an independently issued or separately stored value,
    unlike the buyer-side vat_number (which IS explicitly entered — see
    normalize_vat_number/is_valid_vat_number above). Expects an
    already-normalized, already-validated eik (see normalize_eik/is_valid_eik)."""
    return f"BG{eik}"
