"""Portuguese translation layer."""
from pathlib import Path

from PIL import Image

from dragshift import i18n, report


def teardown_function():
    i18n.set_language("en")


def test_english_is_passthrough():
    i18n.set_language("en")
    assert i18n.tr("Compress") == "Compress"
    assert i18n.tr("Converting to {name}…", name="PNG") == "Converting to PNG…"


def test_portuguese():
    i18n.set_language("pt")
    assert i18n.tr("Compress") == "Comprimir"
    assert i18n.tr("Converting to {name}…", name="PNG") == "Convertendo para PNG…"
    assert i18n.plural(1, "{n} page", "{n} pages") == "1 página"
    assert i18n.plural(3, "{n} page", "{n} pages") == "3 páginas"
    assert i18n.tr("not a known string") == "not a known string"


def test_placeholders_match():
    import re
    ph = lambda s: sorted(re.findall(r"{(\w+)}", s))
    for en, pt in i18n.PT.items():
        assert ph(en) == ph(pt), en


def test_report_in_portuguese(tmp_path: Path):
    i18n.set_language("pt")
    src = tmp_path / "a.png"
    Image.new("RGB", (300, 200), "red").save(src)
    out = tmp_path / "a.jpg"
    Image.new("RGB", (300, 200), "red").save(out)
    r = report.summarize("tool:Rotate", [src], [out])
    assert r.title == "Girado 90°"
