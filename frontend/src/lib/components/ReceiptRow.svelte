<script lang="ts">
	import BucketPill from './BucketPill.svelte';

	export let id: string;
	export let receiptDate: string | null;
	export let totalAmount: number | null;
	export let currency: string;
	export let status: string;
	export let merchantName: string | null = null;
	export let itemCount = 0;
	export let bucketName: string;
	export let bucketIsDefault: boolean;
	export let showBucketPill = true;
	export let thumbUrl: string | null = null;
	export let onOpen: (id: string) => void;

	// GET /thumb liefert 404, wenn kein serverseitiges Thumbnail existiert (alte Belege,
	// fehlgeschlagene Generierung) — der Browser feuert dann on:error auf dem <img>, und wir
	// fallen dauerhaft auf das SVG-Platzhalter-Icon zurück statt ein kaputtes Bild zu zeigen.
	let thumbFailed = false;
	$: showThumb = !!thumbUrl && !thumbFailed;

	function statusLabel(s: string): string {
		switch (s) {
			case 'pending':
				return 'Wird verarbeitet';
			case 'processed':
				return 'Verarbeitet';
			case 'needs_review':
				return 'Prüfung nötig';
			default:
				return s;
		}
	}

	function open() {
		onOpen(id);
	}
</script>

<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
<div
	role="button"
	tabindex="0"
	class="flex w-full items-center gap-4 border-b border-hifi-border px-2 py-3.5 text-left transition-colors hover:bg-hifi-accent-tint"
	on:click={open}
	on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), open())}
>
	{#if showThumb}
		<img
			src={thumbUrl}
			alt={merchantName ? `Beleg-Vorschau: ${merchantName}` : 'Beleg-Vorschau'}
			loading="lazy"
			class="h-9 w-9 flex-none rounded-[10px] border border-hifi-border object-cover"
			on:error={() => (thumbFailed = true)}
		/>
	{:else}
		<span class="flex h-9 w-9 flex-none items-center justify-center rounded-[10px] bg-hifi-accent-tint text-hifi-accent-text">
			<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<path d="M6 3h9l3 3v15H6z" />
				<path d="M9 9h6M9 13h6M9 17h3" />
			</svg>
		</span>
	{/if}

	<div class="min-w-0 flex-1">
		<div class="truncate text-[13.5px] font-bold text-hifi-text">{merchantName ?? 'Händler folgt'}</div>
		<div class="mt-0.5 flex items-center gap-2 text-xs text-hifi-text-muted">
			<span>{receiptDate ?? 'Datum folgt'}</span>
			{#if itemCount > 0}
				<span>· {itemCount} Artikel</span>
			{/if}
		</div>
	</div>

	<span class="hidden shrink-0 text-xs text-hifi-text-faint sm:inline">{statusLabel(status)}</span>

	{#if showBucketPill}
		<div class="shrink-0"><BucketPill name={bucketName} isDefault={bucketIsDefault} /></div>
	{/if}

	<span class="w-24 shrink-0 text-right font-mono text-[14px] font-bold text-hifi-text">
		{totalAmount !== null ? `${totalAmount.toFixed(2)} ${currency}` : '—'}
	</span>
</div>
