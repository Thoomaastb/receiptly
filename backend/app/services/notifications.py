"""
Einziger Schreib-/Lesepfad für `Notification` (analog zu `services/audit.py` für
`AuditLog`) — genutzt vom API-Router (`api/notifications.py`), den Scheduler-Jobs
(`scripts/warranty_notifications.py`, indirekt) und dem `record_event()`-Hook in
`services/audit.py`.

`NOTIFICATION_TYPES`/`ALL_NOTIFICATION_TYPES` sind die v1-Werteliste für `category`/`type` —
bewusst als Python-Konstante geführt statt als DB-Constraint (siehe
`app/models/notification.py`-Docstring), damit neue Typen ohne Migration ergänzt werden
können. Dient zwei Zwecken: Dokumentation, welche Typen es gibt, UND Validierung beim
Schreiben von `User.notification_email_opt_ins` (siehe `api/settings.py`).
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.notification import Notification
from app.models.user import User
from app.services.email import send_email
from app.services.email_templates import render_notification_email

logger = logging.getLogger(__name__)

NOTIFICATION_TYPES: dict[str, list[str]] = {
    "garantie": ["warranty_expiring"],
    "sicherheit": [
        "security_password_changed",
        "security_totp_enabled",
        "security_totp_disabled",
        "security_passkey_registered",
        "security_passkey_removed",
        "security_recovery_code_used",
        "security_session_terminated",
        "security_passkey_exclusive_login_toggled",
        "security_new_login",
    ],
}

ALL_NOTIFICATION_TYPES: set[str] = {
    type_ for types in NOTIFICATION_TYPES.values() for type_ in types
}


async def send_opt_in_email_for_notification(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    category: str,
    type: str,
    title: str,
    body: str,
    link: str | None = None,
    recipient: User | None = None,
) -> None:
    """
    Prüft `User.notification_email_opt_ins` des Empfängers und verschickt bei Opt-in eine
    E-Mail zusätzlich zur (bereits geschriebenen) In-App-Zeile — als HTML-Template über
    `email_templates.render_notification_email()` (verbindlich für JEDE Mail, siehe
    email_templates.py-Moduldocstring; die Benachrichtigungs-Mail lief bis 2026-07-22
    fälschlich nur als Plain-Text). In try/except gekapselt — ein SMTP-Fehlschlag darf weder
    die bereits gespeicherte In-App-Notification zurückrollen noch den aufrufenden
    Job-/Request-Pfad crashen lassen (nur `logger.warning(...)`, `send_email()` selbst ist
    bereits no-op-sicher ohne konfiguriertes SMTP).

    `link` ist der app-relative Pfad (z.B. `/receipts?open={id}`, wie in der
    `Notification.link`-Spalte gespeichert) — wird hier erst mit `settings.public_app_url`
    zu einem absoluten Link zusammengesetzt, analog zu `api/auth.py`'s Passwort-Reset-Link.

    `recipient` erlaubt Aufrufern, die den User bereits geladen haben (z.B. der einzelne
    Security-Notification-Pfad in `services/audit.py`), eine zusätzliche Query zu sparen.
    Ohne `recipient` wird der User per `user_id` nachgeladen — nötig für den Bulk-Insert-Pfad
    in `scripts/warranty_notifications.py`, wo `RETURNING` nur Notification-Spalten liefert.
    """
    user = recipient
    if user is None:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

    if user is None or type not in user.notification_email_opt_ins:
        return

    absolute_link = f"{get_settings().public_app_url}{link}" if link else None
    try:
        await send_email(
            db,
            to=user.email,
            subject=title,
            text_body=body,
            html_body=render_notification_email(
                category=category, title=title, body=body, link=absolute_link
            ),
        )
    except Exception:
        logger.warning(
            "E-Mail-Zustellung für Notification-Typ %s an User %s fehlgeschlagen",
            type,
            user_id,
            exc_info=True,
        )


async def create_notification(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    household_id: uuid.UUID,
    category: str,
    type: str,
    title: str,
    body: str,
    link: str | None = None,
    dedup_key: str | None = None,
    recipient: User | None = None,
    commit: bool = True,
) -> Notification | None:
    """
    Einzeiliger Insert-Pfad für Aufrufer außerhalb eines Bulk-Kontexts (der
    Garantie-Scan in `scripts/warranty_notifications.py` inseriert stattdessen satzweise,
    siehe dort).

    `dedup_key` gesetzt (aktuell immer, für jeden v1-Typ): `INSERT ... ON CONFLICT DO
    NOTHING` über den Unique-Index `(user_id, dedup_key)` — gibt `None` zurück, wenn die
    Zeile als Duplikat übersprungen wurde, damit Aufrufer den E-Mail-Versand nicht für eine
    bereits vorhandene Notification erneut anstoßen.

    `commit=True` ist der Default (wie bei `services/audit.py::record_event`) —
    `commit=False` ist für Aufrufer gedacht, die die Notification in eine bereits laufende,
    fremde Transaktion einbetten wollen (der `record_event()`-Hook: muss sich dessen eigenen
    Commit teilen, sonst würde ein Rollback des Audit-Eintrags eine bereits committete
    Notification ohne zugehöriges Audit-Event zurücklassen).
    """
    values = dict(
        user_id=user_id,
        household_id=household_id,
        category=category,
        type=type,
        title=title,
        body=body,
        link=link,
        dedup_key=dedup_key,
    )

    if dedup_key is not None:
        stmt = (
            postgresql_insert(Notification)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["user_id", "dedup_key"])
            .returning(Notification)
        )
        notification = (await db.execute(stmt)).scalar_one_or_none()
    else:
        notification = Notification(**values)
        db.add(notification)
        await db.flush()

    if notification is not None:
        await send_opt_in_email_for_notification(
            db,
            user_id=notification.user_id,
            category=notification.category,
            type=notification.type,
            title=notification.title,
            body=notification.body,
            link=notification.link,
            recipient=recipient,
        )

    if commit:
        await db.commit()
    else:
        await db.flush()

    return notification


async def list_notifications(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Notification]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if category is not None:
        stmt = stmt.where(Notification.category == category)
    stmt = stmt.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def count_unread(db: AsyncSession, *, user_id: uuid.UUID) -> dict:
    """
    Eine gruppierte Query statt global + pro Kategorie getrennt — bedient von
    `ix_notifications_user_id_category_read_at` (Migration 0018). Kategorien ohne
    ungelesene Zeile tauchen in `by_category` nicht auf (0 implizit), `total` ist die Summe
    über alle zurückgegebenen Kategorien.
    """
    result = await db.execute(
        select(Notification.category, func.count())
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .group_by(Notification.category)
    )
    by_category = {category: count for category, count in result.all()}
    return {"total": sum(by_category.values()), "by_category": by_category}


async def mark_read(db: AsyncSession, *, user_id: uuid.UUID, notification_id: uuid.UUID) -> bool:
    """
    False nur, wenn keine Zeile mit dieser id UND diesem user_id existiert (nie ein fremder
    User kann eine andere Notification als gelesen markieren) — die HTTPException-
    Übersetzung (404) ist Aufgabe des Routers. Bereits gelesene Zeilen bleiben idempotent
    True, ohne read_at zu überschreiben.
    """
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id
        )
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        return False

    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        await db.commit()

    return True


async def mark_all_read(
    db: AsyncSession, *, user_id: uuid.UUID, category: str | None = None
) -> int:
    stmt = update(Notification).where(
        Notification.user_id == user_id, Notification.read_at.is_(None)
    )
    if category is not None:
        stmt = stmt.where(Notification.category == category)
    stmt = stmt.values(read_at=func.now())

    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0
