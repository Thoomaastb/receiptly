<script lang="ts">
	import BucketPill from './BucketPill.svelte';

	export let id: string;
	export let receiptDate: string | null;
	export let totalAmount: number | null;
	export let currency: string;
	export let status: string;
	export let bucketName: string;
	export let bucketIsDefault: boolean;
	export let showBucketPill = true;
	export let onOpen: (id: string, cardEl: HTMLElement) => void;

	let cardEl: HTMLElement;
	let pressed = false;

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
		onOpen(id, cardEl);
	}
</script>

<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
<div
	bind:this={cardEl}
	role="button"
	tabindex="0"
	class="mb-3 inline-block w-full cursor-pointer rounded-xl border border-border bg-surface-raised p-4 transition-transform duration-150"
	class:scale-[0.97]={pressed}
	on:mousedown={() => (pressed = true)}
	on:mouseup={() => (pressed = false)}
	on:mouseleave={() => (pressed = false)}
	on:touchstart={() => (pressed = true)}
	on:touchend={() => (pressed = false)}
	on:click={open}
	on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), open())}
>
	<div class="mb-2 flex items-start justify-between">
		<span class="text-xs text-text-muted">{receiptDate ?? 'Datum folgt'}</span>
		{#if showBucketPill}
			<BucketPill name={bucketName} isDefault={bucketIsDefault} />
		{/if}
	</div>
	<div class="mb-2 text-lg font-medium">
		{totalAmount !== null ? `${totalAmount.toFixed(2)} ${currency}` : 'Betrag folgt'}
	</div>
	<span class="text-xs text-text-muted">{statusLabel(status)}</span>
</div>
