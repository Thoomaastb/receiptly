// Gemeinsame Formatierung für KI-Token-/Kosten-Zahlen — geteilt zwischen AiUsageBadge.svelte
// (kumulierter Zähler) und AiUsageHistoryModal.svelte (Tageshistorie), damit beide Stellen
// exakt dieselbe Darstellung ("5.05 M", "4,95 €") zeigen.

// Kompakte Token-Anzeige: ab 1 Mio "5.05 M", ab 1.000 "820 K", sonst die Rohzahl.
export function formatTokens(tokens: number): string {
	if (tokens >= 1_000_000) {
		return `${(tokens / 1_000_000).toLocaleString('de-DE', {
			minimumFractionDigits: 2,
			maximumFractionDigits: 2
		})} M`;
	}
	if (tokens >= 1_000) {
		return `${(tokens / 1_000).toLocaleString('de-DE', {
			minimumFractionDigits: 0,
			maximumFractionDigits: 1
		})} K`;
	}
	return tokens.toLocaleString('de-DE');
}

export function formatCost(costEur: string): string {
	const value = Number(costEur);
	return `${value.toLocaleString('de-DE', {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2
	})} €`;
}

// Für die Kosten-Sparkline in AiUsageHistoryModal.svelte: `formatCost()` rundet fix auf
// 2 Nachkommastellen — bei günstigen Modellen sind Tageskosten oft Bruchteile eines Cents,
// die dort durchgängig als "0,00 €" erscheinen. Das Backend liefert `total_cost_eur` als
// unrundenden Decimal-String (siehe ai_pricing.usd_to_eur(), keine .quantize()); diese
// Funktion rundet adaptiv nach Größenordnung, damit Trendlinie/Tooltip auch bei Sub-Cent-
// Beträgen noch eine Bewegung zeigen, statt optisch komplett flach bei 0 zu liegen.
export function formatCostPrecise(costEur: number): string {
	if (costEur === 0) return '0,00 €';
	const abs = Math.abs(costEur);
	const decimals = abs < 0.01 ? 4 : abs < 1 ? 3 : 2;
	return `${costEur.toLocaleString('de-DE', {
		minimumFractionDigits: decimals,
		maximumFractionDigits: decimals
	})} €`;
}
