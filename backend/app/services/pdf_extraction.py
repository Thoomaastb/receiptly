import io
import logging
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)

# Heuristik-Wert, kein exakter Schwellenwert: darunter gilt eine Seite als "keine nutzbare
# Text-Ebene" (z.B. nur Kopfzeile/Seitenzahl eingebettet) und wird stattdessen per OCR
# gerendert.
_MIN_TEXT_LAYER_CHARS = 40

# Kompromiss Qualität/Performance für Tesseract — höher bringt kaum bessere Trefferquote,
# kostet aber überproportional mehr Rechenzeit pro Seite.
_OCR_RENDER_DPI = 200


def extract_pdf_text(file_path: Path) -> str:
    """
    Extrahiert Text aus einem PDF: zuerst Text-Ebene je Seite, bei zu wenig Ausbeute
    (vermutlich gescannt/reines Bild-PDF) Fallback auf OCR-Rendering je Seite. Alle Seiten
    werden aneinandergehängt zurückgegeben.

    Synchron & CPU-lastig (PDF-Rendering + Tesseract) — vom Aufrufer per
    asyncio.to_thread() aus dem Async-Kontext aufrufen, nie direkt in einer async def.

    Liefert bei nicht öffenbarem/korruptem PDF einen leeren String statt zu crashen, damit
    der Beleg im bestehenden "Kein OCR-Text vorhanden"-Pfad landet statt den Background-Task
    mit einem unbehandelten Fehler sterben zu lassen.
    """
    try:
        document = fitz.open(file_path)
    except Exception:
        logger.warning("PDF konnte nicht geöffnet werden: %s", file_path, exc_info=True)
        return ""

    pages: list[str] = []
    try:
        with document:
            for page in document:
                text = page.get_text()
                if len(text.strip()) >= _MIN_TEXT_LAYER_CHARS:
                    pages.append(text)
                else:
                    pages.append(_ocr_page(page))
    except Exception:
        logger.warning("PDF-Textextraktion fehlgeschlagen: %s", file_path, exc_info=True)
        return ""

    return "\n".join(pages)


def _ocr_page(page: "fitz.Page") -> str:
    pix = page.get_pixmap(dpi=_OCR_RENDER_DPI)
    image = Image.open(io.BytesIO(pix.tobytes("png")))
    return pytesseract.image_to_string(image, lang="deu")
