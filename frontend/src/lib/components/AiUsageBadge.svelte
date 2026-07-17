<script lang="ts">
	import { onMount } from 'svelte';

	interface AiUsage {
		total_tokens: number;
		total_cost_eur: string;
		has_unpriced_usage: boolean;
	}

	let usage: AiUsage | null = null;

	// Kompakte Token-Anzeige für die "nerdy" Sidebar-Zeile: ab 1 Mio "5.05 M", ab 1.000
	// "820 K", sonst die Rohzahl. Kein bestehender Formatierungs-Helfer im Projekt (siehe
	// frontend/src/lib) — bewusst lokal statt eines verfrühten globalen Utils.
	function formatTokens(tokens: number): string {
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

	function formatCost(costEur: string): string {
		const value = Number(costEur);
		return `${value.toLocaleString('de-DE', {
			minimumFractionDigits: 2,
			maximumFractionDigits: 2
		})} €`;
	}

	onMount(async () => {
		try {
			const res = await fetch('/api/settings/ai-usage', { credentials: 'include' });
			if (!res.ok) return;
			usage = await res.json();
		} catch {
			// Rein informative Nerd-Kennzahl — bei Fehlern lieber nichts anzeigen als kaputt wirken
		}
	});
</script>

{#if usage}
	<div class="px-3 text-[11px] text-hifi-text-faint">
		{formatTokens(usage.total_tokens)} / {formatCost(usage.total_cost_eur)}{#if usage.has_unpriced_usage}<span
				title="Enthält Aufrufe mit unbekannten Modellkosten — Summe ist ein Mindestwert"
			>
				*</span
			>{/if}
	</div>
{/if}
