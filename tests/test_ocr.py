"""Copy text: PDF text layer first, OCR fallback."""
from pathlib import Path

import fitz
import pytest
from PIL import Image

from dragshift import ocr
from dragshift.util import UserError


def make_pdf(path: Path, rotation: int = 0, text: bool = True) -> Path:
    doc = fitz.open()
    pg = doc.new_page(width=600, height=800)
    if text:
        pg.insert_text((50, 100), "Receita cresceu 12%", fontsize=14)
        pg.insert_text((50, 700), "Rodapé da página", fontsize=14)
    else:  # a "scan": the text only exists as pixels
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 200, 50), False)
        pix.clear_with(200)
        pg.insert_image(fitz.Rect(50, 80, 250, 130), pixmap=pix)
    pg.set_rotation(rotation)
    doc.save(path)
    return path


def test_text_layer_area(tmp_path):
    p = make_pdf(tmp_path / "a.pdf")
    text, how = ocr.pdf_area_text(p, 0, (0, 0, 1, 0.3))
    assert how == "pdf" and text == "Receita cresceu 12%"
    text, how = ocr.pdf_area_text(p, 0, (0, 0.7, 1, 1))
    assert "Rodapé" in text and "Receita" not in text


def test_text_layer_rotated_page(tmp_path):
    p = make_pdf(tmp_path / "r.pdf", rotation=90)
    # rotated 90° clockwise: the top of the page is now on the right
    text, how = ocr.pdf_area_text(p, 0, (0.7, 0, 1, 1))
    assert how == "pdf" and "Receita" in text and "Rodapé" not in text


def test_falls_back_to_ocr_for_scans(tmp_path):
    p = make_pdf(tmp_path / "s.pdf", text=False)
    seen = {}

    def fake_ocr(im):
        seen["size"] = im.size
        return "texto escaneado"
    text, how = ocr.pdf_area_text(p, 0, (0, 0, 0.5, 0.25), ocr=fake_ocr)
    assert (text, how) == ("texto escaneado", "ocr")
    assert seen["size"][0] == 1250            # rendered at 300 dpi for the OCR


def test_ocr_unavailable_message(monkeypatch):
    monkeypatch.setattr(ocr, "windows_ocr_available", lambda: (False, "needs Windows"))
    with pytest.raises(UserError):
        ocr.image_to_text(Image.new("RGB", (100, 40), "white"))


def test_prepare_limits_and_upscales():
    im, k = ocr._prepare(Image.new("RGB", (6000, 3000)), 2600)
    assert max(im.size) == 2600 and abs(k - 2600 / 6000) < 1e-9
    im, k = ocr._prepare(Image.new("RGB", (300, 100)), 2600)
    assert im.size == (600, 200) and k == 2.0


def test_tidy():
    assert ocr.tidy("a  \r\n\n\n\nb\x0c\n") == "a\n\nb"


def test_unlock_pdf(tmp_path):
    from dragshift import imaging
    p = make_pdf(tmp_path / "a.pdf")
    locked = imaging.protect_pdf(p, "segredo")
    assert imaging.pdf_lock_state(locked) == "password"
    assert not imaging.check_pdf_password(locked, "errada")
    with pytest.raises(UserError):
        imaging.unlock_pdf(locked, "errada")
    out = imaging.unlock_pdf(locked, "segredo")
    assert imaging.pdf_lock_state(out) == "open"
    assert "Receita" in fitz.open(out)[0].get_text()


def test_organize_pages(tmp_path):
    from dragshift import imaging
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    for path, tag in ((a, "A"), (b, "B")):
        doc = fitz.open()
        for i in range(3):
            doc.new_page().insert_text((72, 72), f"{tag}{i + 1}")
        doc.save(path)
    refs = imaging.list_pages([a, b])
    assert len(refs) == 6
    order = [refs[4], refs[0], imaging.PageRef(1, 2, 90)]          # B2, A1, B3 rotated
    out = imaging.build_pdf([a, b], order, "Organized")
    d = fitz.open(out)
    assert [p.get_text().strip() for p in d] == ["B2", "A1", "B3"]
    assert [p.rotation for p in d] == [0, 0, 90]


def test_parse_page_ranges():
    from dragshift import imaging
    assert imaging.parse_page_ranges("1-3, 7, 9-", 10) == [0, 1, 2, 6, 8, 9]
    assert imaging.parse_page_ranges("2;2;1", 5) == [1, 0]
    assert imaging.parse_page_ranges("", 5) == []
    for bad in ("0", "3-1", "11", "a"):
        with pytest.raises(UserError):
            imaging.parse_page_ranges(bad, 10)


@pytest.mark.parametrize("rotation", [0, 90, 270])
def test_searchable_pdf_places_words(tmp_path, rotation):
    """Invisible words land where the OCR saw them, also on rotated pages."""
    p = tmp_path / "scan.pdf"
    doc = fitz.open()
    pg = doc.new_page(width=600, height=800)
    pg.draw_rect(fitz.Rect(40, 40, 200, 90), fill=(0.8, 0.8, 0.8))   # "ink", no text layer
    pg.set_rotation(rotation)
    doc.save(p)
    k = ocr.OCR_DPI / 72
    # boxes in displayed-page pixels (300 dpi): "Nota" at (100,50)pt, "fiscal" right after it
    fake = lambda im: [[ocr.Word("Nota", 100 * k, 50 * k, 40 * k, 14 * k),
                        ocr.Word("fiscal", 146 * k, 50 * k, 44 * k, 14 * k)]]
    out, done, skipped = ocr.make_searchable_pdf(p, ocr_lines=fake)
    assert (done, skipped) == (1, 0)
    page = fitz.open(out)[0]
    # order by position on the displayed page (sort=True would use unrotated space)
    words = sorted(page.get_text("words"), key=lambda w: (fitz.Rect(w[:4]) * page.rotation_matrix).x0)
    assert [w[4] for w in words] == ["Nota", "fiscal"]
    shown = fitz.Rect(words[0][:4]) * page.rotation_matrix          # back to displayed coords
    assert abs(shown.x0 - 100) < 4 and 48 < (shown.y0 + shown.y1) / 2 < 66
    assert page.get_text("text", clip=fitz.Rect(90, 40, 200, 70) * page.derotation_matrix).split() == ["Nota", "fiscal"]


def test_searchable_pdf_skips_text_pages(tmp_path):
    p = make_pdf(tmp_path / "t.pdf")
    with pytest.raises(UserError):
        ocr.make_searchable_pdf(p, ocr_lines=lambda im: [])


def test_trim_transparent():
    from dragshift import bgremove
    im = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
    im.paste((255, 0, 0, 255), (50, 20, 90, 60))
    assert bgremove.trim_transparent(im, pad=5).size == (50, 50)


def test_download_rejects_corrupted(tmp_path, monkeypatch):
    """A bad download never ends up as the model file."""
    import io
    from dragshift import bgremove
    monkeypatch.setattr(bgremove, "models_dir", lambda: tmp_path)

    class FakeResp(io.BytesIO):
        headers = {"Content-Length": "4"}
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(bgremove.urllib.request, "urlopen", lambda *a, **k: FakeResp(b"junk"))
    with pytest.raises(UserError):
        bgremove.download_model()
    assert not bgremove.model_ready() and not any(tmp_path.iterdir())


def _photo_pdf(path, pages=3):
    import numpy as np
    rng = np.random.default_rng(0)
    doc = fitz.open()
    for i in range(pages):
        pg = doc.new_page()
        arr = (rng.random((1400, 1000, 3)) * 60 + np.linspace(0, 190, 1000)[None, :, None]).astype("uint8")
        buf = io.BytesIO()
        Image.fromarray(arr).save(buf, "JPEG", quality=95)
        pg.insert_image(pg.rect, stream=buf.getvalue())
        pg.insert_text((50, 50), f"Página {i + 1}", fontsize=20)
    doc.save(path)
    return path


import io  # noqa: E402


def test_compress_pdf_to_target(tmp_path):
    from dragshift import imaging
    src = _photo_pdf(tmp_path / "fotos.pdf")
    size = src.stat().st_size
    target = size // 6
    out, reached = imaging.compress_pdf_to(src, target)
    assert reached and out.stat().st_size <= target
    assert "Página 2" in fitz.open(out)[1].get_text()          # text survives


def test_compress_pdf_target_unreachable(tmp_path):
    from dragshift import imaging
    p = make_pdf(tmp_path / "texto.pdf")
    out, reached = imaging.compress_pdf_to(p, 50)                 # 50 bytes: impossible
    assert not reached and out.exists()


def test_signature_from_photo_ignores_shadow(tmp_path, monkeypatch):
    import numpy as np
    from PIL import ImageDraw
    from dragshift import imaging
    monkeypatch.setattr(imaging, "signatures_dir", lambda: tmp_path)
    # paper with a strong shadow gradient + a dark-blue scribble
    g = np.linspace(250, 150, 1200)[None, :].repeat(600, 0)
    photo = Image.fromarray(np.stack([g, g, g * 0.97], -1).astype("uint8"))
    d = ImageDraw.Draw(photo)
    d.line([(300, 350), (420, 250), (520, 380), (640, 260), (800, 340)], fill=(20, 30, 90), width=9)
    cut = imaging.signature_from_photo(photo)
    a = np.asarray(cut.getchannel("A"))
    assert cut.width < 600 and cut.height < 200          # trimmed to the ink, shadow ignored
    assert a.max() == 255 and (a == 0).mean() > 0.5
    saved = imaging.save_signature(cut)
    assert saved in imaging.list_signatures()


def test_sign_pdf_all_pages(tmp_path):
    import numpy as np
    from dragshift import imaging
    sig = Image.new("RGBA", (300, 100), (200, 0, 0, 255))
    sp = tmp_path / "s.png"
    sig.save(sp)
    doc = fitz.open()
    for _ in range(3):
        doc.new_page()
    p = tmp_path / "c.pdf"
    doc.save(p)
    out = imaging.sign_pdf(p, sp, None, (0.6, 0.85, 0.9, 0.95))
    d = fitz.open(out)
    assert out.name == "c Signed.pdf" and all(len(pg.get_images()) == 1 for pg in d)


def test_collage_layouts(tmp_path):
    from dragshift import imaging
    a = Image.new("RGB", (400, 300), "red")
    b = Image.new("RGB", (200, 300), "blue")
    c = Image.new("RGB", (300, 300), "green")
    row = imaging.collage([a, b, c], "row", 10, "white")
    assert row.size == (400 + 200 + 300 + 40, 320)
    col = imaging.collage([a, b], "column", 0, "black")
    assert col.width == 300 and col.height == 225 + 450
    grid = imaging.collage([a, b, c, a], "grid", 10, "transparent")
    assert grid.getpixel((0, 0))[3] == 0                       # transparent gap
    paths = []
    for i, im in enumerate((a, b)):
        p = tmp_path / f"{i}.png"
        im.save(p)
        paths.append(p)
    out = imaging.save_collage(paths, "row", 20, "white")
    assert out.name == "0 Collage file.jpg" and out.exists()
