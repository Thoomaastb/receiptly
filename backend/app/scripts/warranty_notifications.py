"""
Sucht Belege, deren Garantie in den nächsten 30 Tagen abläuft (Q2 — deckungsgleich mit der
bestehenden Frontend-Schwelle in `ReceiptDetailView.svelte`), und legt für jedes
Haushaltsmitglied eine `warranty_expiring`-Notification an (Q4: haushaltsweite
Adressierung, nicht nur der Ersteller des Belegs). Haushalts-Auflösung läuft über
`Receipt.bucket_id → Bucket.household_id`, nicht über `Receipt.user_id → User.household_id`.

Ein einziger satzbasierter Bulk-Insert pro Lauf via
`postgresql.insert(...).on_conflict_do_nothing(...)` statt zeilenweiser
`create_notification()`-Aufrufe (Performance bei vielen Belegen × Haushaltsmitgliedern).
`dedup_key=f"warranty:{receipt.id}"` ist für alle Empfänger eines Belegs identisch — die
Eindeutigkeit ist bereits pro `user_id` durch den Composite-Unique-Index gegeben, ein
erneuter Lauf (Misfire, Neustart, manueller Re-Trigger) fügt für bereits benachrichtigte
Belege 0 neue Zeilen ein.

Reines Python-Skript, per APScheduler-Job in `app/scheduler.py` täglich um 03:00
angestoßen — manueller Aufruf (innerhalb des Backend-Containers):
`python -m app.scripts.warranty_notifications`
"""

import asyncio
import logging
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.database import AsyncSessionLocal
from app.models.bucket import Bucket
from app.models.merchant import Merchant
from app.models.notification import Notification
from app.models.receipt import Receipt
from app.models.user import User
from app.services.notifications import send_opt_in_email_for_notification

logger = logging.getLogger(__name__)

_WARRANTY_LOOKAHEAD_DAYS = 30


async def scan_warranty_expirations() -> int:
    """Legt warranty_expiring-Notifications für Belege an, deren Garantie in <=30 Tagen abläuft."""
    today = date.today()
    horizon = today + timedelta(days=_WARRANTY_LOOKAHEAD_DAYS)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Receipt, Bucket.household_id, Merchant.name)
            .join(Bucket, Receipt.bucket_id == Bucket.id)
            .outerjoin(Merchant, Receipt.merchant_id == Merchant.id)
            .where(Receipt.warranty_expires_at.is_not(None))
            .where(Receipt.warranty_expires_at.between(today, horizon))
        )
        rows = result.all()

        if not rows:
            logger.info("Garantie-Scan: keine fälligen Belege gefunden")
            return 0

        household_ids = {household_id for _receipt, household_id, _merchant_name in rows}
        members_result = await db.execute(
            select(User.id, User.household_id).where(User.household_id.in_(household_ids))
        )
        members_by_household: dict[uuid.UUID, list[uuid.UUID]] = {}
        for member_id, household_id in members_result.all():
            members_by_household.setdefault(household_id, []).append(member_id)

        values = []
        for receipt, household_id, merchant_name in rows:
            title = "Garantie läuft bald ab"
            body = (
                f"Die Garantie für „{merchant_name or 'Beleg'}\" läuft am "
                f"{receipt.warranty_expires_at.isoformat()} ab."
            )
            link = f"/receipts?open={receipt.id}"
            dedup_key = f"warranty:{receipt.id}"
            for member_id in members_by_household.get(household_id, []):
                values.append(
                    dict(
                        user_id=member_id,
                        household_id=household_id,
                        category="garantie",
                        type="warranty_expiring",
                        title=title,
                        body=body,
                        link=link,
                        dedup_key=dedup_key,
                    )
                )

        if not values:
            return 0

        stmt = (
            postgresql.insert(Notification)
            .values(values)
            .on_conflict_do_nothing(index_elements=["user_id", "dedup_key"])
            .returning(
                Notification.user_id,
                Notification.category,
                Notification.type,
                Notification.title,
                Notification.body,
                Notification.link,
            )
        )
        inserted = (await db.execute(stmt)).all()
        await db.commit()

        # RETURNING liefert nur tatsächlich neu eingefügte Zeilen (ON CONFLICT DO NOTHING
        # übersprungene Duplikate tauchen hier nicht auf) — der E-Mail-Opt-in-Check läuft
        # also nur für frisch erzeugte Notifications, nie für bereits vorhandene.
        for member_id, category_, type_, title, body, link_ in inserted:
            await send_opt_in_email_for_notification(
                db,
                user_id=member_id,
                category=category_,
                type=type_,
                title=title,
                body=body,
                link=link_,
            )

    logger.info("Garantie-Scan: %s Notification(en) angelegt", len(inserted))
    return len(inserted)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(scan_warranty_expirations())
