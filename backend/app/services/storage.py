import hashlib
import uuid
from pathlib import Path

from fastapi import UploadFile

STORAGE_ROOT = Path("storage")
ORIGINALS_DIR = STORAGE_ROOT / "originals"
THUMBS_DIR = STORAGE_ROOT / "thumbs"

ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


class UnsupportedFileTypeError(Exception):
    pass


class FileTooLargeError(Exception):
    pass


def _ensure_dirs() -> None:
    ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)


async def store_upload(file: UploadFile, household_id: uuid.UUID) -> tuple[str, str | None, str]:
    """
    Speichert die Originaldatei unter storage/originals/<household_id>/<uuid>.<ext>.
    Gibt (file_path, thumb_path, content_hash) zurück.

    Thumbnail-Generierung ist bewusst noch ein Platzhalter (None) — die Thumbnail-Strategie
    ist laut Notion eine offene Entscheidung (client-side generiert vs. kein Server-Thumbnail).
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

    return str(destination), None, hasher.hexdigest()
