import asyncio
import hashlib
import io
import logging
import uuid
from pathlib import Path

import fitz  # PyMuPDF
from fastapi import UploadFile
from PIL import Image

logger = logging.getLogger(__name__)

STORAGE_ROOT = Path("storage")
ORIGINALS_DIR = STORAGE_ROOT / "originals"
THUMBS_DIR = STORAGE_ROOT / "thumbs"

ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB

_THUMB_MAX_DIMENSION = 320
_THUMB_JPEG_QUALITY = 80
# PDF-Erstseite mit Overscan rendern, damit das anschließende LANCZOS-Downsampling sauber
# glättet statt ein bereits kleines Rendering weiter zu verschlechtern.
_PDF_RENDER_OVERSAMPLE = 2


class UnsupportedFileTypeError(Exception):
    pass


class FileTooLargeError(Exception):
    pass


def _ensure_dirs() -> None:
    ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)


def _render_pdf_first_page(file_path: Path) -> Image.Image:
    with fitz.open(file_path) as document:
        page = document[0]
        target_px = _THUMB_MAX_DIMENSION * _PDF_RENDER_OVERSAMPLE
        longest_side_pt = max(page.rect.width, page.rect.height) or 1.0
        zoom = target_px / longest_side_pt
        pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        return Image.open(io.BytesIO(pixmap.tobytes("png")))


def _generate_thumbnail(file_path: Path, thumb_path: Path, content_type: str) -> None:
    """
    Synchron & CPU-lastig (Bild-Resize bzw. PDF-Rendering) — vom Aufrufer per
    asyncio.to_thread() aus dem Async-Kontext aufrufen, nie direkt in einer async def.
    Wirft bei korrupten/unerwarteten Dateien; der Aufrufer fängt das ab und lässt den
    Upload trotzdem erfolgreich durchlaufen.
    """
    if content_type == "application/pdf":
        image = _render_pdf_first_page(file_path)
    else:
        image = Image.open(file_path)

    image = image.convert("RGB")
    image.thumbnail((_THUMB_MAX_DIMENSION, _THUMB_MAX_DIMENSION), Image.Resampling.LANCZOS)

    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(thumb_path, format="JPEG", quality=_THUMB_JPEG_QUALITY)


def _thumb_destination(file_path: Path, household_id: uuid.UUID | str) -> Path:
    # Gleicher Dateistamm wie das Original: deterministischer Zielpfad, damit parallele
    # Lazy-Generierungen (siehe generate_thumbnail_for_existing_file) dieselbe Datei
    # treffen statt Kollisions-Handling zu brauchen.
    return THUMBS_DIR / str(household_id) / f"{file_path.stem}.jpg"


def generate_thumbnail_for_existing_file(
    file_path: Path, household_id: uuid.UUID, content_type: str
) -> Path | None:
    """
    Erzeugt nachträglich ein Thumbnail für eine bereits auf Platte liegende Original-
    datei — für Alt-Belege ohne thumb_path (Lazy-Healing, siehe GET /receipts/{id}/thumb).
    Synchron & CPU-lastig — vom Aufrufer per asyncio.to_thread() ausführen.
    Gibt bei Erfolg den Thumbnail-Pfad zurück, sonst None (z.B. korrupte Altdatei) — der
    Aufrufer entscheidet dann, mit 404 zu antworten; kein Fehlerzustand wird zwischen-
    gespeichert, jeder weitere Aufruf versucht es einfach erneut.
    """
    thumb_destination = _thumb_destination(file_path, household_id)
    try:
        _generate_thumbnail(file_path, thumb_destination, content_type)
    except Exception:
        logger.warning(
            "Nachträgliche Thumbnail-Generierung fehlgeschlagen für %s", file_path, exc_info=True
        )
        return None
    return thumb_destination


async def store_upload(file: UploadFile, household_id: uuid.UUID) -> tuple[str, str | None, str]:
    """
    Speichert die Originaldatei unter storage/originals/<household_id>/<uuid>.<ext> und
    erzeugt synchron ein Thumbnail unter storage/thumbs/<household_id>/<uuid>.jpg.
    Gibt (file_path, thumb_path, content_hash) zurück.

    Schlägt die Thumbnail-Generierung fehl (korrupte Datei, unerwartetes Format), bricht das
    den Upload nicht ab — thumb_path bleibt dann None, der Fehler wird geloggt.
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise UnsupportedFileTypeError(f"Nicht unterstützter Dateityp: {file.content_type}")

    _ensure_dirs()

    extension = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png"}[
        file.content_type
    ]
    file_id = uuid.uuid4()
    household_dir = ORIGINALS_DIR / str(household_id)
    household_dir.mkdir(parents=True, exist_ok=True)
    destination = household_dir / f"{file_id}.{extension}"

    hasher = hashlib.sha256()
    size = 0
    with destination.open("wb") as out_file:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                destination.unlink(missing_ok=True)
                raise FileTooLargeError(f"Datei überschreitet {MAX_UPLOAD_BYTES} Bytes")
            hasher.update(chunk)
            out_file.write(chunk)

    generated_thumb = await asyncio.to_thread(
        generate_thumbnail_for_existing_file, destination, household_id, file.content_type
    )
    thumb_path = str(generated_thumb) if generated_thumb is not None else None

    return str(destination), thumb_path, hasher.hexdigest()
