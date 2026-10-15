from normalize import best, is_uncertain, normalize, normalize_number, readings, reason

UNSURE = {"best": "Sulkies", "alternatives": ["Sulkes", "Sutkies", "Salkies", "Sulkis"], "reason": "row 3"}

def test_possible_readings():
    assert best("Sulkies") == "Sulkies" and best(UNSURE) == "Sulkies" and best(None) is None
    assert readings(UNSURE) == ["Sulkies", "Sulkes", "Sutkies", "Salkies"]  # capped at 3 alternatives
    assert readings("Sulkies") == ["Sulkies"] and readings(None) == []
    assert reason(UNSURE) == "row 3" and reason("Sulkies") is None

def test_uncertainty():
    assert is_uncertain(UNSURE) and is_uncertain("Sul[illegible]")
    assert not is_uncertain("Sulkies") and not is_uncertain({"best": "Sulkies", "alternatives": []})
    assert normalize("Sul [illegible]", "de-pl") == "sul"

def test_german_polish_variants_collapse():
    assert normalize("Schmul", "de-pl") == normalize("Szmul", "de-pl")
    assert normalize("Wolf", "de-pl") == normalize("Volf", "de-pl")
    assert normalize("Łaja Groß", "de-pl") == "laja gross"

def test_cyrillic_transliterated():
    assert normalize("Шмуль", "ru") == normalize("Szmul", "ru")

def test_hungarian_only_strips_diacritics():
    assert normalize("Kovács Sándor", "hu") == "kovacs sandor"

def test_register_numbers():
    for raw in ("6", "6.", "No. 6", "Nr 6"):
        assert normalize_number(raw) == "6"
    assert normalize_number("6a") == "6a"
    assert normalize_number(None) == ""
