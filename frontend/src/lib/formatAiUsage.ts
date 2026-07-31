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
