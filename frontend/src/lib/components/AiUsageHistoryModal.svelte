<script lang="ts">
	import { onMount } from 'svelte';
	import { fade, fly } from 'svelte/transition';
	import { m } from '$lib/i18n';
	import { formatDate } from '$lib/formatDate';
	import { formatTokens, formatCost, formatCostPrecise } from '$lib/formatAiUsage';
	import Sparkline from './Sparkline.svelte';

	export let onClose: () => void;

	interface AiUsageHistoryEntry {
		date: string;
		call_count: number;
		total_tokens: number;
		total_cost_eur: string;
		has_unpriced_usage: boolean;
	}

	let history: AiUsageHistoryEntry[] = [];
	let loading = true;
	let loadError = '';

	// Baut aus `history` (absteigend, Tage OHNE Aufrufe fehlen komplett in der API-Response)
	// eine lückenlose, aufsteigend sortierte Tagesreihe für die Sparklines — fehlende Tage
	// werden explizit mit value=0 aufgefüllt (kein API-Call an diesem Tag = 0 Nutzung an
	// diesem Tag), statt die vorhandenen Punkte einfach gleichmäßig nebeneinander zu reihen.
	// So bildet gleichmäßiger Punktabstand automatisch den echten Kalendertag-Abstand ab,
	// auch über mehrtägige Lücken hinweg, ohne eine eigene Datums-Skala zu brauchen.
	function buildDailySeries(
		entries: AiUsageHistoryEntry[],
		valueOf: (entry: AiUsageHistoryEntry) => number
	): { date: string; value: number }[] {
		if (entries.length === 0) return [];
		const byDate = new Map(entries.map((entry) => [entry.date, valueOf(entry)]));
		const sortedDates = [...byDate.keys()].sort();
		const start = new Date(`${sortedDates[0]}T00:00:00Z`).getTime();
		const end = new Date(`${sortedDates[sortedDates.length - 1]}T00:00:00Z`).getTime();
		const series: { date: string; value: number }[] = [];
		const dayMs = 24 * 60 * 60 * 1000;
		for (let t = start; t <= end; t += dayMs) {
			const iso = new Date(t).toISOString().slice(0, 10);
			series.push({ date: iso, value: byDate.get(iso) ?? 0 });
		}
		return series;
	}

	$: tokenSeries = buildDailySeries(history, (entry) => entry.total_tokens);
	$: costSeries = buildDailySeries(history, (entry) => Number(entry.total_cost_eur));

	async function loadHistory() {
		loading = true;
		loadError = '';
		try {
			const res = await fetch('/api/settings/ai-usage/history', { credentials: 'include' });
			if (!res.ok) throw new Error();
			history = await res.json();
		} catch {
			loadError = m.aiUsageHistory.loadError;
		} finally {
			loading = false;
		}
	}

	onMount(loadHistory);

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose();
	}

	function callCountLabel(count: number): string {
		return count === 1 ? m.aiUsageHistory.callCountSingular : m.aiUsageHistory.callCountPlural;
	}
</script>

<svelte:window on:keydown={handleKeydown} />

<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
<div
	transition:fade={{ duration: 150 }}
	class="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
	on:click={onClose}
	role="presentation"
></div>

<!-- Gleiches Modal-Muster wie ShareManagementModal.svelte (Flexbox-Zentrierung statt
     left/top-50%+translate, Bottom-Sheet auf Mobile). -->
<div class="fixed inset-0 z-50 flex items-end justify-center lg:items-center">
	<div
		transition:fly={{ y: 20, duration: 180 }}
		class="max-h-[92dvh] w-full overflow-auto rounded-t-[20px] border-t border-hifi-border bg-hifi-surface p-5 pb-[calc(1.25rem+env(safe-area-inset-bottom))] lg:max-h-[85vh] lg:w-[92vw] lg:max-w-lg lg:rounded-[20px] lg:border lg:pb-5"
		role="dialog"
		aria-modal="true"
		aria-label={m.aiUsageHistory.modalTitle}
	>
		<div class="mb-4 flex items-center justify-between">
			<h2 class="text-[13.5px] font-bold text-hifi-text">{m.aiUsageHistory.modalTitle}</h2>
			<button
				on:click={onClose}
				aria-label={m.aiUsageHistory.closeAriaLabel}
				class="flex h-11 w-11 items-center justify-center rounded-full text-hifi-text-muted hover:text-hifi-text"
			>
				✕
			</button>
		</div>

		{#if loading}
			<p class="text-xs text-hifi-text-muted">{m.aiUsageHistory.loading}</p>
		{:else if loadError}
			<p class="text-xs text-danger">{loadError}</p>
		{:else if history.length === 0}
			<p class="text-xs text-hifi-text-muted">{m.aiUsageHistory.emptyState}</p>
		{:else}
			<!-- Zwei separate Trendlinien (Tokens/Kosten) statt einem Chart mit zwei Y-Achsen —
			     Dual-Axis-Charts sind laut Dataviz-Konvention des Projekts ein Anti-Pattern
			     (irreführende gemeinsame Skala für unterschiedliche Größenordnungen). -->
			<div class="mb-4 flex flex-col gap-4 border-b border-hifi-border pb-4">
				<Sparkline data={tokenSeries} label={m.aiUsageHistory.tokenTrendLabel} formatValue={formatTokens} />
				<Sparkline data={costSeries} label={m.aiUsageHistory.costTrendLabel} formatValue={formatCostPrecise} />
			</div>
			<ul class="flex flex-col">
				{#each history as day (day.date)}
					<li class="flex items-center justify-between gap-3 border-b border-hifi-border py-2.5 text-xs last:border-0">
						<div class="min-w-0 flex-1">
							<div class="font-semibold text-hifi-text">{formatDate(day.date)}</div>
							<div class="text-hifi-text-faint">{day.call_count} {callCountLabel(day.call_count)}</div>
						</div>
						<div class="flex-none text-right">
							<div class="text-hifi-text">
								{formatTokens(day.total_tokens)}{#if day.has_unpriced_usage}<span
										title={m.aiUsageHistory.unpricedHint}>*</span
									>{/if}
							</div>
							<div class="text-hifi-text-faint">{formatCost(day.total_cost_eur)}</div>
						</div>
					</li>
				{/each}
			</ul>
		{/if}
	</div>
</div>
