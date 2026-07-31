<script lang="ts">
	import { onMount } from 'svelte';
	import { fade, fly } from 'svelte/transition';
	import { m } from '$lib/i18n';
	import { formatDate } from '$lib/formatDate';
	import { formatTokens, formatCost } from '$lib/formatAiUsage';

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
