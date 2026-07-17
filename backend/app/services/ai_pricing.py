from decimal import Decimal

# Preise in USD pro 1 Million Tokens, Stand 2026-07 (öffentliche Provider-Preislisten).
# MUSS manuell aktualisiert werden, wenn sich Provider-Preise ändern — keine Live-Quelle.
# Modelle, die hier fehlen (z.B. individuell konfigurierte Custom-Modelle), liefern
# estimated_cost_usd=None statt eines falschen Werts.
#
# Quellen (abgerufen 2026-07-17):
# - gpt-4o-mini: platform.openai.com/docs/pricing (weiterhin aktiv, kein Deprecation-Datum;
#   nicht mehr auf der Haupt-Preistabelle gelistet, dort stehen nur noch GPT-5.x-Modelle).
# - claude-3-5-haiku-20241022: platform.claude.com/docs/en/about-claude/pricing. ACHTUNG:
#   dieses Modell wurde am 19.02.2026 aus der First-Party-Anthropic-API zurückgezogen und
#   ist nur noch über Bedrock/Vertex mit diesen Konditionen erreichbar — der Preis ist real,
#   aber der Default in _DEFAULT_MODELS (ai_provider_client.py) ruft ihn ggf. gar nicht mehr
#   erfolgreich auf. Nicht Teil dieses Tickets, beim nächsten Provider-Review aufgreifen.
# - gemini-2.5-flash: ai.google.dev/gemini-api/docs/pricing, Standard-Tier (Text/Bild/Video-
#   Input), Output-Preis gilt einheitlich inkl. Thinking-Tokens.
_PRICING_USD_PER_1M_TOKENS: dict[str, tuple[Decimal, Decimal]] = {
    # model_name: (price_per_1M_prompt_tokens, price_per_1M_completion_tokens)
    "gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),
    "claude-3-5-haiku-20241022": (Decimal("0.80"), Decimal("4.00")),
    "gemini-2.5-flash": (Decimal("0.30"), Decimal("2.50")),
    # Ollama: selbst gehostet, keine API-Kosten
    "llama3.1": (Decimal("0"), Decimal("0")),
}

# Manuell gepflegter Näherungskurs, kein Live-FX — Stand 2026-07.
USD_TO_EUR_RATE = Decimal("0.92")


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> Decimal | None:
    """None bei unbekanntem Modellnamen (z.B. Custom-Modell eines Haushalts) — bewusst
    keine Schätzung/Näherung, ein falscher stiller Wert wäre schlimmer als eine Lücke."""
    pricing = _PRICING_USD_PER_1M_TOKENS.get(model)
    if pricing is None:
        return None
    prompt_price, completion_price = pricing
    million = Decimal("1000000")
    return (Decimal(prompt_tokens) * prompt_price / million) + (
        Decimal(completion_tokens) * completion_price / million
    )


def usd_to_eur(amount_usd: Decimal) -> Decimal:
    return amount_usd * USD_TO_EUR_RATE
