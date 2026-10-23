"""Tests for v1.1 features: target-size compress, resize, protect, extract, location strip,
result summaries, output folder setting, liquid renderer."""
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from dragshift import convert, imaging, liquid, report
from dragshift.util import CONFIG, UserError


def photo(tmp_path, name="Photo.jpg", size=(2400, 1600), gps=True) -> Path:
    import random
    random.seed(1)
    im = Image.new("RGB", size)
    d = ImageDraw.Draw(im)
    for i in range(400):  # busy content so JPEG has something to compress
        x, y = random.randrange(size[0]), random.randrange(size[1])
        d.ellipse((x, y, x + random.randrange(20, 200), y + random.randrange(20, 200)),
                  fill=tuple(random.randrange(256) for _ in range(3)))
    ex = Image.Exif()
    ex[0x010F] = "Canon"
    ex[0x0110] = "Canon EOS R6"
    if gps:
        ex[0x8825] = {1: "N", 2: (24.0, 33.0, 18.0), 3: "W", 4: (81.0, 47.0, 0.0)}
    p = tmp_path / name
    im.save(p, quality=95, exif=ex)
    return p


def test_compress_target_size(tmp_path):
    p = photo(tmp_path)
    im = convert.open_image(p)
    q, side = imaging.plan_target_size(im, "JPG", 200_000)
    out = imaging.compress_to(p, q, side, "JPG")
    assert out.stat().st_size <= 200_000
    r = report.summarize("tool:Compress", [p], [out], "target 200 KB")
    assert "smaller" in r.good and "→" in r.detail


def test_compress_png_and_webp(tmp_path):
    p = photo(tmp_path)
    assert imaging.compress_to(p, 70, 1000, "WEBP").suffix == ".webp"
    png = tmp_path / "a.png"
    Image.open(p).save(png)
    out = imaging.compress_to(png, 60, None, imaging.lossy_target(png))
    assert out.suffix == ".png" and out.stat().st_size < png.stat().st_size


def test_resize(tmp_path):
    p = photo(tmp_path)
    assert imaging.resize_dims((2400, 1600), "pct", 50) == (1200, 800)
    assert imaging.resize_dims((2400, 1600), "long", 1920) == (1920, 1280)
    out = imaging.resize_image(p, (1200, 800))
    assert Image.open(out).size == (1200, 800)
    r = report.summarize("tool:Resize", [p], [out])
    assert "2400×1600 → 1200×800" in r.detail


def test_metadata_summary_and_location(tmp_path):
    p = photo(tmp_path)
    s = imaging.metadata_summary(p)
    assert s["Camera"] == "Canon EOS R6"
    assert s["Location"].startswith("24.555")
    n, gps = imaging.count_metadata(p)
    assert gps and n >= 3
    out = imaging.strip_location(p)
    s2 = imaging.metadata_summary(out)
    assert "Location" not in s2 and s2.get("Camera") == "Canon EOS R6"
    clean = imaging.strip_image_metadata(p)
    assert imaging.count_metadata(clean)[0] == 0


def make_pdf(tmp_path, img: Path, pages=3) -> Path:
    doc = convert.fitz.open()
    for i in range(pages):
        pg = doc.new_page()
        pg.insert_text((72, 72), f"Page {i + 1}", fontsize=20)
        pg.insert_image(convert.fitz.Rect(72, 100, 400, 400), filename=str(img))
    p = tmp_path / "Doc.pdf"
    doc.save(p)
    return p


def test_protect_and_extract(tmp_path):
    img = photo(tmp_path, size=(400, 300))
    pdf = make_pdf(tmp_path, img)
    prot = imaging.protect_pdf(pdf, "secret123")
    d = convert.fitz.open(prot)
    assert d.needs_pass and d.authenticate("secret123")
    with pytest.raises(UserError):
        convert.convert(prot, "pdf", "TXT")
    imgs = imaging.extract_pdf_images(pdf)
    assert len(imgs) == 1 and imgs[0].parent.name == "Doc images"
    r = report.summarize("tool:Extract", [pdf], imgs)
    assert r.title == "Extracted 1 image"
    r = report.summarize("convert:JPG", [pdf], convert.convert(pdf, "pdf", "JPG"))
    assert r.title == "3 pages → 3 JPGs"


def test_output_folder_setting(tmp_path):
    p = photo(tmp_path, size=(300, 200))
    CONFIG["output"] = "folder"
    try:
        out = convert.convert(p, "image", "PNG")[0]
        assert out.parent.name == "Tesler"
    finally:
        CONFIG["output"] = "next"


def test_auto_enhance_and_summary(tmp_path):
    p = photo(tmp_path, size=(300, 200))
    a = imaging.auto_enhance(convert.open_image(p))
    assert 0.8 < a.brightness < 1.3
    r = report.summarize("convert:PNG", [p], convert.convert(p, "image", "PNG"))
    assert r.title == "JPG → PNG" and "300×200" in r.detail and r.thumb


def test_liquid_render_shapes():
    bg = Image.new("RGB", (200, 200), (255, 120, 80))
    for sdf in (liquid.sdf_rounded_rect(200, 200, 10, 10, 190, 190, 20),
                liquid.sdf_ring_sector(200, 200, 100, 100, 30, 90, 45, 135, 6)):
        img, light = liquid.render(bg, sdf)
        a = img.getchannel("A")
        assert a.getpixel((100, 100 if sdf is not None else 0)) >= 0
        assert img.size == (200, 200)
    img, _ = liquid.render(bg, liquid.sdf_circle(200, 200, 100, 100, 50))
    assert img.getpixel((100, 100))[3] == 255 and img.getpixel((2, 2))[3] == 0
