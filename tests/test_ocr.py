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
