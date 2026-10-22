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
        assert "text" not in ph(en), f"{{text}} clashes with tr(text, ...): {en}"


def test_report_in_portuguese(tmp_path: Path):
    i18n.set_language("pt")
    src = tmp_path / "a.png"
    Image.new("RGB", (300, 200), "red").save(src)
    out = tmp_path / "a.jpg"
    Image.new("RGB", (300, 200), "red").save(out)
    r = report.summarize("tool:Rotate", [src], [out])
    assert r.title == "Girado 90°"


def test_hub_flips_rings_only_once():
    """Resting the cursor on the hub flipped Convert ⇄ Tools every ~0.4 s (bug)."""
    from PySide6.QtWidgets import QApplication
    from dragshift.radial import Item, RadialMenu
    QApplication.instance() or QApplication([])
    m = RadialMenu(lambda p: {"Convert": [Item("PNG")], "Tools": [Item("Crop", "x")]}, lambda p: "1 KB")
    m.rings = m.build_rings([])
    m.ring_names = list(m.rings)
    m._set_hover(0)            # visit a petal
    m._set_hover(-2)           # then rest on the hub
    assert m.hub_timer.isActive()
    m.next_ring()              # the timer fires once
    assert m.ring_idx == 1
    m._set_hover(-2)           # Windows keeps sending drag-move events on the hub
    assert not m.hub_timer.isActive()


def test_pdf_snip(tmp_path: Path):
    import fitz
    from dragshift import imaging
    p = tmp_path / "doc.pdf"
    doc = fitz.open()
    for rot in (0, 90):
        pg = doc.new_page(width=600, height=800)
        pg.draw_rect(fitz.Rect(0, 0, 300, 400), color=(1, 0, 0), fill=(1, 0, 0))
        pg.set_rotation(rot)
    doc.save(p)
    im = imaging.snip_pdf(p, 0, (0.1, 0.1, 0.4, 0.4), 144)       # inside the red box
    assert im.size == (360, 480) and im.getpixel((10, 10))[1] < 50
    im = imaging.snip_pdf(p, 1, (0.6, 0.1, 0.9, 0.4), 72)         # rotated page: red is top-right
    assert im.getpixel((im.width // 2, im.height // 2))[1] < 50
    out = imaging.save_pdf_snip(p, 1, (0, 0, 1, 0.5), 72)
    assert out.name == "doc page 2 snip.png" and out.exists()
