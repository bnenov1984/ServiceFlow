"""Pure normalization rules (ADR-010) — the P0-7 foundation, no DB needed."""

from business_os.shared_kernel.normalize import (
    fold_plate_homoglyphs,
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


def test_fold_plate_homoglyphs_makes_cyrillic_and_latin_plates_identical() -> None:
    # order-workflow-revamp Q11: same physical plate, two keyboards.
    cyrillic = fold_plate_homoglyphs(normalize_identifier("ВН 1234 АК"))
    latin = fold_plate_homoglyphs(normalize_identifier("BH1234AK"))
    assert cyrillic == latin == "BH1234AK"


def test_fold_plate_homoglyphs_only_touches_the_defined_letters() -> None:
    # "Ж" has no Latin homoglyph on a BG plate — left untouched, not dropped.
    assert fold_plate_homoglyphs("ЖУ1234СТ") == "ЖY1234CT"
