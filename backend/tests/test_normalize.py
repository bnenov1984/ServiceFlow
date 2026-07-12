"""Pure normalization rules (ADR-010) — the P0-7 foundation, no DB needed."""

from serviceflow.shared_kernel.normalize import (
    normalize_identifier,
    normalize_phone,
    transliterate,
)


def test_transliterate_cyrillic_matches_latin() -> None:
    assert transliterate("Иван") == "ivan"
    assert transliterate("Ivan") == "ivan"
    assert transliterate("Щерев") == "shterev"
    assert transliterate("Джурова-Петрова  ") == "dzhurova-petrova"


def test_phone_variants_normalize_identically() -> None:
    expected = "0888123456"
    assert normalize_phone("+359 88 812 3456") == expected
    assert normalize_phone("00359888123456") == expected
    assert normalize_phone("0888 123 456") == expected
    assert normalize_phone("(0888) 123-456") == expected


def test_phone_edge_cases() -> None:
    assert normalize_phone("") == ""
    assert normalize_phone("абв") == ""
    # Landline and short numbers pass through digits-only.
    assert normalize_phone("02 987 65 43") == "029876543"


def test_identifier_normalization() -> None:
    assert normalize_identifier("35-698506-123456 7") == "356985061234567"
    assert normalize_identifier("вн 1234 ак") == "ВН1234АК"
    assert normalize_identifier("wvwzzz1jz3w386752") == "WVWZZZ1JZ3W386752"
