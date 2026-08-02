"""
Einmaliger Backfill: setzt `ai_suggested_title` für alle Bestandsbelege, die noch keinen
Titel haben (weder ein bestätigtes `title` noch bereits einen Vorschlag
`ai_suggested_title`) — siehe concepts/beleg-titel.md.

Nutzt AUSSCHLIESSLICH das deterministische Regel-Fallback-Template
(app/services/receipt_title.py::build_fallback_title), KEINEN KI-Call — für Bestandsdaten
zu teuer/langsam, und neue/erneut analysierte Belege bekommen ihren Titel ohnehin bereits
über die normale Extraktions-Pipeline (app/services/ai_extraction.py).

Schreibt bewusst nur nach `ai_suggested_title`, nicht nach `title` — der Titel bleibt ein
überschreibbarer Vorschlag, exakt wie bei ai_suggested_merchant_name (Herkunfts-Tracking,
siehe Receipt-Modell). Belege ohne bekanntes `receipt_date` bleiben unangetastet
(build_fallback_title liefert dann None) — sie bekommen ihren Titel-Vorschlag automatisch
nachträglich, sobald Datum/Titel über eine erneute Extraktion oder manuelle Eingabe
gesetzt werden.

Bewusst KEIN APScheduler-Job (einmaliger Lauf, kein wiederkehrender wie
warranty_notifications.py/cleanup_notifications.py) — manueller Aufruf innerhalb des
Backend-Containers, wenn/sobald gewünscht:
`docker compose exec backend python -m app.scripts.backfill_receipt_titles`
"""

import asyncio
import logging

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.receipt import Receipt
from app.services.receipt_title import build_fallback_title

logger = logging.getLogger(__name__)


async def backfill_receipt_titles() -> int:
    """Setzt ai_suggested_title für alle Belege ohne title/ai_suggested_title, gibt die Anzahl aktualisierter Belege zurück."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Receipt).where(Receipt.title.is_(None), Receipt.ai_suggested_title.is_(None))
        )
        receipts = list(result.scalars().all())

        updated = 0
        skipped_no_date = 0
        for receipt in receipts:
            fallback_title = build_fallback_title(receipt.category, receipt.receipt_date)
            if fallback_title is None:
                skipped_no_date += 1
                continue
            receipt.ai_suggested_title = fallback_title
            updated += 1

        if updated:
            await db.commit()

    logger.info(
        "Titel-Backfill abgeschlossen: %s Beleg(e) aktualisiert, %s ohne Belegdatum übersprungen",
        updated,
        skipped_no_date,
    )
    return updated


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(backfill_receipt_titles())
