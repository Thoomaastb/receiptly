<script lang="ts">
	import { onMount } from 'svelte';
	import { formatTokens, formatCost } from '$lib/formatAiUsage';
	import AiUsageHistoryModal from './AiUsageHistoryModal.svelte';

	interface AiUsage {
		total_tokens: number;
		total_cost_eur: string;
		has_unpriced_usage: boolean;
	}

	let usage: AiUsage | null = null;
	let modalOpen = false;

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
	<!-- Öffnet die Tageshistorie (AiUsageHistoryModal). Bewusst mit
	     appearance-none/bg-transparent/p-0/text-left neutralisiert, damit ein <button> hier
	     optisch exakt wie die bisherige <div>-Zeile aussieht — keine Stiländerung, nur
	     Klickbarkeit. -->
	<button
		type="button"
		on:click={() => (modalOpen = true)}
		class="w-full appearance-none bg-transparent p-0 px-3 text-left text-[11px] text-hifi-text-faint"
	>
		{formatTokens(usage.total_tokens)} / {formatCost(usage.total_cost_eur)}{#if usage.has_unpriced_usage}<span
				title="Enthält Aufrufe mit unbekannten Modellkosten — Summe ist ein Mindestwert"
			>
				*</span
			>{/if}
	</button>
{/if}

{#if modalOpen}
	<AiUsageHistoryModal onClose={() => (modalOpen = false)} />
{/if}
