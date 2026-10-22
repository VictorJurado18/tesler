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
    assert max(ocr._prepare(Image.new("RGB", (6000, 3000)), 2600).size) == 2600
    assert ocr._prepare(Image.new("RGB", (300, 100)), 2600).size == (600, 200)


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
