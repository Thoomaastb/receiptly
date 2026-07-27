from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.receipt import Receipt
from app.models.tag import Tag, receipt_tags
from app.models.user import User
from app.services.bucket_access import visible_bucket_ids_query

# "Letzte N" statt gesamte Historie — verhindert, dass sich der Vorschlag nie von alten,
# inzwischen überholten Tag-Gewohnheiten für diesen Händler löst.
_RECENT_RECEIPT_LIMIT = 10
# Ein einziger Treffer wäre reines Rauschen (z.B. ein Tippfehler-Tag) — erst ab zwei
# Vorkommen in den letzten N Belegen gilt ein Tag als Muster.
_MIN_OCCURRENCES = 2


async def suggest_tags_for_receipt(db: AsyncSession, receipt: Receipt, user: User) -> list[Tag]:
    """
    Ermittelt die häufigsten Tags früherer Belege desselben Händlers, als Vorschlag für
    `receipt` (siehe concepts/tag-vorschlaege.md). Reine Lese-Query, keine Persistenz.

    Erwartet `receipt.tags` bereits vorgeladen (z.B. via `_RECEIPT_DETAIL_OPTIONS` in
    app/api/receipts.py) — hier bewusst kein Nachladen, um die Funktion als reine,
    session-günstige Query-Funktion zu halten.

    Design-Entscheidungen:
    - Sichtbarkeits-Scope über `visible_bucket_ids_query(user)` statt rohem
      `household_id`-Join auf Receipt: hält sich an das bestehende Bucket-Privacy-Modell,
      private Buckets anderer Haushaltsmitglieder bleiben auch als Vorschlagsquelle
      unsichtbar. Bewusste, leichte Abweichung von der wörtlichen Konzept-Formulierung
      "im selben Haushalt".
    - Recency-Kriterium ist `created_at`, nicht `receipt_date` — robuster (viele Belege
      haben `receipt_date` erst nach erfolgreicher KI-Extraktion), konsistent mit dem
      App-weiten "neueste zuerst"-Default.
    - Die "letzten N"-Auswahl läuft als Subquery VOR der Aggregation, nicht als Filter
      danach — sonst würde die gesamte Historie einfließen.
    """
    if receipt.merchant_id is None:
        return []

    recent_receipt_ids = (
        select(Receipt.id)
        .where(
            Receipt.merchant_id == receipt.merchant_id,
            Receipt.id != receipt.id,
            Receipt.bucket_id.in_(visible_bucket_ids_query(user)),
        )
        .order_by(Receipt.created_at.desc())
        .limit(_RECENT_RECEIPT_LIMIT)
        .subquery()
    )

    stmt = (
        select(Tag, func.count(receipt_tags.c.receipt_id))
        .join(receipt_tags, receipt_tags.c.tag_id == Tag.id)
        .where(
            receipt_tags.c.receipt_id.in_(select(recent_receipt_ids.c.id)),
            Tag.household_id == user.household_id,
        )
        .group_by(Tag.id)
        .having(func.count(receipt_tags.c.receipt_id) >= _MIN_OCCURRENCES)
        .order_by(func.count(receipt_tags.c.receipt_id).desc())
    )
    result = await db.execute(stmt)

    already_assigned = {t.id for t in receipt.tags}
    return [tag for tag, _ in result.all() if tag.id not in already_assigned]
