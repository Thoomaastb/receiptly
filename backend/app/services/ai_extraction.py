import asyncio
import logging
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.ai_usage_event import AIUsageEvent
from app.models.item import Item
from app.models.receipt import Receipt, ReceiptStatus
from app.schemas.receipt import ALLOWED_CATEGORY_VALUES
from app.services import ai_pricing
from app.services.ai_provider_client import AIProviderError, StructuredCallResult, call_structured, resolve_model_name
from app.services.ai_provider_resolution import EffectiveProviderConfig, resolve_effective_provider
from app.services.pdf_extraction import extract_pdf_text
from app.services.pii_redaction import redact_sensitive_patterns
from app.services.receipt_heuristics import extract_receipt_heuristics

logger = logging.getLogger(__name__)
settings = get_settings()

_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")

_SYSTEM_PROMPT = (
    "Du extrahierst strukturierte Daten aus dem OCR-Text eines Kassenbelegs. Antworte "
    "ausschließlich mit den angeforderten Feldern im vorgegebenen JSON-Format. Erfinde "
    "keine Werte, die im Text nicht erkennbar sind — setze sie stattdessen auf null bzw. "
    "lasse Artikel weg, wenn du dir unsicher bist. Steht direkt unter einem Artikel eine "
    "eigene Rabatt-/Gutschein-Zeile, gehört diese zu genau diesem Artikel: erfasse sie "
    "NICHT als eigene Artikelzeile, sondern als deren discount_amount. Eine Rabattzeile, "
    "die du bereits einem Artikel als dessen discount_amount zugeordnet hast, darf NICHT "
    "zusätzlich in die beleg-weite discount_amount-Summe einfließen — das beleg-weite "
    "discount_amount ist ausschließlich für Rabatte/Gutscheine ohne Bezug zu einer "
    "einzelnen Artikelzeile (z.B. ein pauschaler Rabatt beim Bezahlen). Zähle keinen "
    "Rabatt doppelt. Die auf praktisch jedem deutschen Kassenbon vorhandene "
    "MwSt.-/USt.-Aufschlüsselungstabelle (mehrere Zeilen mit Steuersatz % + Netto + "
    "Brutto pro Steuerklasse, endend in einer Summe-Zeile) ist NIEMALS tax_amount — diese "
    "Steuer ist immer bereits im Gesamtbetrag enthalten. tax_amount ist ausschließlich für "
    "den seltenen Fall einer Steuer, die ZUSÄTZLICH zum ausgewiesenen Gesamtbetrag erhoben "
    "wird."
)

_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "receipt_date": {
            "type": ["string", "null"],
            "description": "Belegdatum im ISO-Format YYYY-MM-DD, oder null wenn nicht erkennbar.",
        },
        "total_amount": {
            "type": ["number", "null"],
            "description": "Gesamtbetrag des Belegs als Zahl, oder null wenn nicht erkennbar.",
        },
        "shipping_cost": {
            "type": ["number", "null"],
            "description": "Separat ausgewiesene Versandkosten als Zahl, oder null wenn keine erkennbar.",
        },
        "discount_amount": {
            "type": ["number", "null"],
            "description": (
                "Summe von Rabatten/Gutscheinen OHNE Bezug zu einer einzelnen Artikelzeile "
                "(z.B. ein pauschaler Gutschein/Rabatt beim Bezahlen, der nicht auf eine "
                "bestimmte Position aufgeschlüsselt ist), als positive Zahl, oder null wenn "
                "keine erkennbar. Eine Rabatt-/Gutschein-Zeile, die bereits einem Artikel als "
                "dessen discount_amount zugeordnet wurde, NICHT hier nochmal einrechnen — "
                "sonst wird derselbe Rabatt doppelt gezählt."
            ),
        },
        "tax_amount": {
            "type": ["number", "null"],
            "description": (
                "Separat ausgewiesene Steuer als Zahl, NUR falls diese Steuer ZUSÄTZLICH "
                "zum ausgewiesenen total_amount erhoben wird (total_amount enthält sie also "
                "noch NICHT) — sonst null. WICHTIG: Die auf praktisch jedem deutschen "
                "Kassenbon vorhandene MwSt.-/USt.-Aufschlüsselungstabelle (Muster: mehrere "
                "Zeilen mit Steuersatz % + Netto + Brutto pro Steuerklasse, endend in einer "
                "Summe-Zeile, deren Brutto-Summe dem total_amount entspricht) ist NIEMALS "
                "tax_amount — diese Steuer ist bereits im Gesamtbetrag enthalten, hier "
                "IMMER null zurückgeben."
            ),
        },
        "currency": {
            "type": ["string", "null"],
            "description": "3-stelliger ISO-Währungscode (z.B. EUR), oder null.",
        },
        "merchant_name": {
            "type": ["string", "null"],
            "description": "Name des Händlers/Geschäfts, oder null wenn nicht erkennbar.",
        },
        "category": {
            "type": ["string", "null"],
            "description": "Eine von: " + ", ".join(sorted(ALLOWED_CATEGORY_VALUES)) + ", oder null.",
        },
        "items": {
            "type": "array",
            "description": "Einzelne Artikel-Positionen des Belegs, leere Liste falls keine erkennbar.",
            "items": {
                "type": "object",
                "properties": {
                    "raw_name": {"type": "string"},
                    "quantity": {"type": ["number", "null"]},
                    "unit_price": {"type": ["number", "null"]},
                    "total_price": {"type": ["number", "null"]},
                    "discount_amount": {
                        "type": ["number", "null"],
                        "description": (
                            "Falls unter diesem Artikel eine eigene Rabatt-/Gutschein-Zeile "
                            "steht: deren Betrag als positive Zahl. Sonst null."
                        ),
                    },
                },
                # OpenAI Structured Outputs (strict) verlangt additionalProperties:false UND
                # jede Property in required (Pflicht schließt "optional" nicht aus — dafür
                # steht null im type-Array, siehe oben) — sonst 400 "additionalProperties is
                # required to be supplied and to be false".
                "required": ["raw_name", "quantity", "unit_price", "total_price", "discount_amount"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "receipt_date",
        "total_amount",
        "shipping_cost",
        "discount_amount",
        "tax_amount",
        "currency",
        "merchant_name",
        "category",
        "items",
    ],
    "additionalProperties": False,
}


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _parse_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().replace(",", "."))
        except ValueError:
            return None
    return None


def _parse_non_negative(value: object) -> float | None:
    parsed = _parse_float(value)
    return parsed if parsed is not None and parsed >= 0 else None


def _parse_positive(value: object) -> float | None:
    parsed = _parse_float(value)
    return parsed if parsed is not None and parsed > 0 else None


def _none_if_zero(value: float | None) -> float | None:
    """Ein Rabatt von exakt 0 ist äquivalent zu 'kein Rabatt' (vgl. Migration-0011-
    Docstring-Philosophie: NULL heißt nicht erfasst, nicht 0) — die KI liefert trotz
    Prompt-Anweisung "sonst null" öfter 0 statt null, wenn kein Rabatt vorliegt."""
    return None if value == 0 else value


async def run_ai_extraction(receipt_id: uuid.UUID, household_id: uuid.UUID) -> None:
    """
    Läuft als FastAPI BackgroundTask nach dem Response-Zyklus, daher eine eigene Session
    statt der request-gebundenen. Jeder Codepfad (auch unerwartete Exceptions) endet in
    einem terminalen Status (processed/needs_review) — nie ein hängender 'pending'-Beleg.
    """
    async with AsyncSessionLocal() as db:
        try:
            await _run(db, receipt_id, household_id)
        except Exception:
            logger.exception("Unerwarteter Fehler bei der KI-Struktur-Extraktion für Beleg %s", receipt_id)
            await db.rollback()
            try:
                await _mark_needs_review(db, receipt_id, "Unerwarteter Fehler bei der Extraktion")
            except Exception:
                logger.exception(
                    "Konnte Beleg %s nach Extraktionsfehler nicht auf needs_review setzen", receipt_id
                )


async def _run(db: AsyncSession, receipt_id: uuid.UUID, household_id: uuid.UUID) -> None:
    result = await db.execute(
        select(Receipt).options(selectinload(Receipt.items)).where(Receipt.id == receipt_id)
    )
    receipt = result.scalar_one_or_none()
    if receipt is None:
        logger.info("Beleg %s existiert nicht mehr (vermutlich gelöscht), Extraktion abgebrochen", receipt_id)
        return

    if not receipt.ocr_raw_text or not receipt.ocr_raw_text.strip():
        # Client-seitiges OCR (tesseract.js) kann keine PDFs dekodieren und überspringt sie
        # deshalb bewusst (siehe UploadFlow.svelte) — hier stattdessen serverseitig aus dem
        # PDF selbst extrahieren, bevor der Beleg vorschnell auf needs_review landet.
        if receipt.file_path.lower().endswith(".pdf"):
            try:
                pdf_text = await asyncio.wait_for(
                    asyncio.to_thread(extract_pdf_text, Path(receipt.file_path)),
                    timeout=settings.pdf_ocr_timeout_seconds,
                )
            except TimeoutError:
                # asyncio.to_thread-Threads sind nicht abbrechbar — der Tesseract-Subprozess
                # läuft im Hintergrund-Thread weiter, nur dieser wartende Task wird durch das
                # Timeout freigegeben. Unkritisch, da Background-Task ohne offene
                # HTTP-Verbindung. Früher Return statt Durchfallen, damit die generische
                # "Kein OCR-Text vorhanden"-Meldung weiter unten die präzisere Diagnose nicht
                # überschreibt.
                logger.warning(
                    "OCR-Zeitüberschreitung bei Beleg %s (>%.0fs)", receipt_id, settings.pdf_ocr_timeout_seconds
                )
                await _finish_needs_review(db, receipt, "OCR-Zeitüberschreitung")
                return
            if pdf_text.strip():
                receipt.ocr_raw_text = pdf_text

    if not receipt.ocr_raw_text or not receipt.ocr_raw_text.strip():
        await _finish_needs_review(db, receipt, "Kein OCR-Text vorhanden")
        return

    # Regex-Fallback VOR dem eigentlichen KI-Call: Die äußere Bedingung (alle drei
    # ai_suggested_* noch None) verhindert redundantes Neu-Schreiben, falls eine künftige
    # clientseitige Heuristik bei Bild-Uploads dieselben Felder bereits beim Upload gesetzt
    # hat. Bei PDFs greift der Block praktisch immer, da dort aktuell nichts diese Felder vor
    # diesem Zeitpunkt setzt. Läuft nicht-blockierend im ohnehin schon laufenden
    # Background-Task, verzögert also nicht die Upload-HTTP-Response. Die direkt danach
    # laufende KI-Extraktion (_apply_extraction_result, Vorrang-sicher) überschreibt bei
    # Erfolg ohnehin wie gehabt.
    if (
        receipt.ai_suggested_receipt_date is None
        and receipt.ai_suggested_total_amount is None
        and receipt.ai_suggested_currency is None
    ):
        heur = extract_receipt_heuristics(receipt.ocr_raw_text)
        if heur.receipt_date is not None and receipt.receipt_date is None:
            receipt.receipt_date = heur.receipt_date
            receipt.ai_suggested_receipt_date = heur.receipt_date
        if heur.total_amount is not None and receipt.total_amount is None:
            receipt.total_amount = heur.total_amount
            receipt.ai_suggested_total_amount = heur.total_amount
        if heur.currency is not None:
            receipt.currency = heur.currency
            receipt.ai_suggested_currency = heur.currency

    try:
        effective = await resolve_effective_provider(db, household_id)
    except ValueError as exc:
        # z.B. decrypt_secret() bei rotiertem ENCRYPTION_KEY — kein Crash, nur needs_review
        logger.warning("KI-Zugangsschlüssel für Haushalt %s ungültig: %s", household_id, exc)
        await _finish_needs_review(db, receipt, "Gespeicherter KI-Zugangsschlüssel ist ungültig")
        return

    if effective is None:
        await _finish_needs_review(db, receipt, "Kein KI-Anbieter konfiguriert")
        return

    # Redaction wirkt NUR auf diese Kopie, ocr_raw_text bleibt unverändert gespeichert.
    outbound_text = redact_sensitive_patterns(receipt.ocr_raw_text)
    outbound_text = outbound_text[: settings.ai_extraction_max_ocr_chars]

    try:
        result = await call_structured(
            provider=effective.provider,
            api_key=effective.api_key,
            endpoint=effective.endpoint,
            model_name=effective.model_name,
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=outbound_text,
            json_schema=_JSON_SCHEMA,
            timeout=settings.ai_extraction_timeout_seconds,
        )
    except AIProviderError as exc:
        # Nur Fehlerklasse/-meldung loggen, nie den (redigierten oder rohen) KI-Payload.
        # Kein Usage-Event hier: AIProviderError kann bereits vor dem eigentlichen HTTP-Call
        # geworfen werden (z.B. fehlender api_key) — dann wurden keine Tokens verbraucht,
        # ein Log-Eintrag wäre ein Phantom-Eintrag.
        logger.warning("KI-Provider-Call fehlgeschlagen für Beleg %s: %s", receipt_id, exc)
        await _finish_needs_review(db, receipt, "KI-Anbieter konnte nicht abgefragt werden")
        return

    await _apply_extraction_result(db, receipt, result.content)

    # Tokens wurden real verbraucht, unabhängig davon, ob die Extraktion inhaltlich
    # erfolgreich ist — aber bewusst ERST NACH dem obigen Commit und in einem eigenen
    # Try/Except: das Usage-Logging ist ein Nice-to-have (Admin-Zähler) und darf unter
    # keinen Umständen das eigentliche Extraktionsergebnis mit sich reißen, falls es aus
    # irgendeinem Grund fehlschlägt (z.B. Migration fehlt, Constraint-Verletzung).
    try:
        _log_usage_event(db, effective, result)
        await db.commit()
    except Exception:
        logger.exception(
            "KI-Usage-Event für Beleg %s konnte nicht gespeichert werden (Extraktion war "
            "trotzdem erfolgreich, nur der Admin-Zähler bleibt für diesen Call ungenau)",
            receipt_id,
        )
        await db.rollback()


def _log_usage_event(
    db: AsyncSession, effective: EffectiveProviderConfig, result: StructuredCallResult
) -> None:
    model = resolve_model_name(effective.provider, effective.model_name)
    db.add(
        AIUsageEvent(
            provider=effective.provider.value,
            model=model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.prompt_tokens + result.completion_tokens,
            estimated_cost_usd=ai_pricing.estimate_cost_usd(
                model, result.prompt_tokens, result.completion_tokens
            ),
        )
    )


async def _apply_extraction_result(db: AsyncSession, receipt: Receipt, data: dict) -> None:
    notes: list[str] = []

    # Herkunfts-Tracking (siehe Receipt-Modell): ein bereits vom Nutzer bestätigter Wert
    # (ai_suggested_X is None, receipt.X gesetzt) wird von der KI nie mehr überschrieben —
    # nur ein noch unbestätigter Wert (leer, oder selbst noch eine Schätzung) darf ersetzt
    # werden. Das gilt auch bei "Neu analysieren" auf einem bereits bestätigten Beleg.
    receipt_date = _parse_date(data.get("receipt_date"))
    if receipt_date is not None:
        if receipt.receipt_date is None or receipt.ai_suggested_receipt_date is not None:
            receipt.receipt_date = receipt_date
            receipt.ai_suggested_receipt_date = receipt_date
    else:
        notes.append("Kein Beleg-Datum erkannt")

    total_amount = _parse_non_negative(data.get("total_amount"))
    if total_amount is not None:
        if receipt.total_amount is None or receipt.ai_suggested_total_amount is not None:
            receipt.total_amount = total_amount
            receipt.ai_suggested_total_amount = total_amount
    else:
        notes.append("Kein Gesamtbetrag erkannt")

    shipping_cost = _parse_non_negative(data.get("shipping_cost"))
    if shipping_cost is not None and (
        receipt.shipping_cost is None or receipt.ai_suggested_shipping_cost is not None
    ):
        receipt.shipping_cost = shipping_cost
        receipt.ai_suggested_shipping_cost = shipping_cost

    discount_amount = _none_if_zero(_parse_non_negative(data.get("discount_amount")))
    if discount_amount is not None and (
        receipt.discount_amount is None or receipt.ai_suggested_discount_amount is not None
    ):
        receipt.discount_amount = discount_amount
        receipt.ai_suggested_discount_amount = discount_amount

    tax_amount = _parse_non_negative(data.get("tax_amount"))
    if tax_amount is not None and (
        receipt.tax_amount is None or receipt.ai_suggested_tax_amount is not None
    ):
        receipt.tax_amount = tax_amount
        receipt.ai_suggested_tax_amount = tax_amount

    currency = data.get("currency")
    if (
        isinstance(currency, str)
        and _CURRENCY_PATTERN.match(currency.strip())
        and receipt.ai_suggested_currency is not None
    ):
        receipt.currency = currency.strip()
        receipt.ai_suggested_currency = currency.strip()

    merchant_name = data.get("merchant_name")
    if isinstance(merchant_name, str) and merchant_name.strip():
        # Ausschließlich der Vorschlagsspalte zugewiesen — die KI legt nie selbst einen
        # Merchant an, das passiert erst, wenn der Nutzer den Vorschlag über PATCH übernimmt.
        # Nur solange kein Merchant bestätigt ist (merchant_id is None) — sonst würde jedes
        # "Neu analysieren" den längst bestätigten Händler erneut als offenen Vorschlag zeigen.
        if receipt.merchant_id is None:
            receipt.ai_suggested_merchant_name = merchant_name.strip()[:255]
    else:
        notes.append("Kein Händler erkannt")

    category = data.get("category")
    if isinstance(category, str) and category.strip() in ALLOWED_CATEGORY_VALUES:
        guessed = category.strip()
        receipt.ai_suggested_category = guessed
        # Nur automatisch übernehmen, wenn der Beleg noch keine Kategorie hat — schützt eine
        # bereits manuell gesetzte/korrigierte Kategorie vor einem späteren "Neu analysieren".
        if receipt.category is None:
            receipt.category = guessed

    items_data = data.get("items")
    # Nur anlegen, wenn der Beleg noch keine Artikel hat — verhindert Duplikate bei
    # "Neu analysieren" auf einem bereits (teilweise) befüllten Beleg.
    if isinstance(items_data, list) and not receipt.items:
        _apply_items(db, receipt, items_data)

    success = (
        receipt.receipt_date is not None
        and receipt.total_amount is not None
        # Händler gilt als bekannt, wenn entweder ein neuer Vorschlag vorliegt ODER bereits
        # ein Merchant bestätigt ist — Letzteres bleibt bei einer Re-Analyse nach Bestätigung
        # bewusst None (siehe Guard oben), zählt aber trotzdem als Erfolg.
        and (bool(receipt.ai_suggested_merchant_name) or receipt.merchant_id is not None)
    )
    receipt.ai_extracted_at = datetime.now(timezone.utc)
    if success:
        receipt.status = ReceiptStatus.PROCESSED
        receipt.ai_extraction_note = None
    else:
        receipt.status = ReceiptStatus.NEEDS_REVIEW
        receipt.ai_extraction_note = "; ".join(notes) if notes else "KI-Extraktion unvollständig"

    await db.commit()


def _apply_items(db: AsyncSession, receipt: Receipt, items_data: list) -> None:
    for raw_item in items_data:
        if not isinstance(raw_item, dict):
            continue
        raw_name = raw_item.get("raw_name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            continue
        total_price = _parse_non_negative(raw_item.get("total_price"))
        if total_price is None:
            continue
        quantity = _parse_positive(raw_item.get("quantity")) or 1
        unit_price = _parse_non_negative(raw_item.get("unit_price"))
        discount_amount = _none_if_zero(_parse_non_negative(raw_item.get("discount_amount")))

        db.add(
            Item(
                receipt_id=receipt.id,
                raw_name=raw_name.strip()[:255],
                quantity=quantity,
                unit_price=unit_price,
                total_price=total_price,
                discount_amount=discount_amount,
            )
        )


async def _finish_needs_review(db: AsyncSession, receipt: Receipt, note: str) -> None:
    receipt.status = ReceiptStatus.NEEDS_REVIEW
    receipt.ai_extraction_note = note
    receipt.ai_extracted_at = datetime.now(timezone.utc)
    await db.commit()


async def _mark_needs_review(db: AsyncSession, receipt_id: uuid.UUID, note: str) -> None:
    """Fallback-Pfad für den äußeren except-Block — lädt den Beleg unabhängig neu, falls
    das ursprüngliche ORM-Objekt nach einem Rollback nicht mehr sicher verwendbar ist."""
    result = await db.execute(select(Receipt).where(Receipt.id == receipt_id))
    receipt = result.scalar_one_or_none()
    if receipt is None:
        return
    await _finish_needs_review(db, receipt, note)
