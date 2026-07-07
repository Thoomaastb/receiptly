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
	export let onOpen: (id: string) => void;

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
	class="mb-3 inline-block w-full cursor-pointer rounded-xl border border-border bg-surface-raised p-4"
	on:click={open}
	on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), open())}
>
	<div class="mb-2 flex items-start justify-between">
		<span class="text-xs text-text-muted">{receiptDate ?? 'Datum folgt'}</span>
		{#if showBucketPill}
			<BucketPill name={bucketName} isDefault={bucketIsDefault} />
		{/if}
	</div>
	{#if merchantName}
		<div class="mb-1 truncate text-sm font-medium">{merchantName}</div>
	{/if}
	<div class="mb-2 text-lg font-medium">
		{totalAmount !== null ? `${totalAmount.toFixed(2)} ${currency}` : 'Betrag folgt'}
	</div>
	<div class="flex items-center gap-2 text-xs text-text-muted">
		<span>{statusLabel(status)}</span>
		{#if itemCount > 0}
			<span>· {itemCount} Artikel</span>
		{/if}
	</div>
</div>
