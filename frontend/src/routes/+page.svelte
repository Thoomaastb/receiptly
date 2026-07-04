<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import ReceiptCard from '$lib/components/ReceiptCard.svelte';
	import UploadModal from '$lib/components/UploadModal.svelte';

	interface Receipt {
		id: string;
		bucket_id: string;
		status: string;
		receipt_date: string | null;
		total_amount: number | null;
		currency: string;
		created_at: string;
	}

	interface Bucket {
		id: string;
		name: string;
		is_default: boolean;
	}

	let recentReceipts: Receipt[] = [];
	let buckets: Bucket[] = [];
	let loading = true;

	let uploadOpen = false;
	let uploadOriginRect: DOMRect | null = null;

	async function loadReceipts() {
		try {
			const [receiptsRes, bucketsRes] = await Promise.all([
				fetch('/api/receipts', { credentials: 'include' }),
				fetch('/api/buckets', { credentials: 'include' })
			]);
			if (receiptsRes.ok) recentReceipts = (await receiptsRes.json()).slice(0, 3);
			if (bucketsRes.ok) buckets = await bucketsRes.json();
		} finally {
			loading = false;
		}
	}

	onMount(loadReceipts);

	function bucketFor(bucketId: string): Bucket | undefined {
		return buckets.find((b) => b.id === bucketId);
	}

	function openUpload(event: MouseEvent) {
		uploadOriginRect = (event.currentTarget as HTMLElement).getBoundingClientRect();
		uploadOpen = true;
	}

	function closeUpload() {
		uploadOpen = false;
		loadReceipts(); // "on-the-fly": neuer Beleg erscheint sofort, kein Reload nötig
	}

	function goToReceipts() {
		goto('/receipts');
	}
</script>

<section class="mb-10 grid max-h-[500px] grid-cols-1 gap-3 sm:grid-cols-2">
	<button
		on:click={openUpload}
		class="group rounded-xl border border-border bg-accent px-6 py-8 text-left text-accent-contrast transition-transform active:scale-[0.98]"
	>
		<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" class="mb-3 opacity-90" aria-hidden="true">
			<rect x="3" y="7" width="18" height="13" rx="2" />
			<path d="M8 7V5a2 2 0 012-2h4a2 2 0 012 2v2M12 11v5M9.5 13.5L12 11l2.5 2.5" stroke-linecap="round" stroke-linejoin="round" />
		</svg>
		<span class="block text-lg font-medium">Scannen</span>
		<span class="block text-sm opacity-80">Kamera-Scan folgt mit der Mobile-App</span>
	</button>
	<button
		on:click={openUpload}
		class="group rounded-xl border border-border bg-surface-raised px-6 py-8 text-left transition-transform active:scale-[0.98]"
	>
		<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" class="mb-3 text-text-muted" aria-hidden="true">
			<path d="M12 16V4M7 9l5-5 5 5" stroke-linecap="round" stroke-linejoin="round" />
			<path d="M4 16v3a2 2 0 002 2h12a2 2 0 002-2v-3" stroke-linecap="round" stroke-linejoin="round" />
		</svg>
		<span class="block text-lg font-medium">Hochladen</span>
		<span class="block text-sm text-text-muted">PDF, JPG, PNG</span>
	</button>
</section>

<div class="mb-4 flex items-center justify-between border-t border-border pt-4">
	<span class="text-sm font-medium text-text-muted">Zuletzt hinzugefügt</span>
	{#if recentReceipts.length > 0}
		<a href="/receipts" class="text-xs text-text-muted transition-colors hover:text-text">Alle ansehen →</a>
	{/if}
</div>

{#if loading}
	<p class="text-sm text-text-muted">Wird geladen …</p>
{:else if recentReceipts.length === 0}
	<button
		on:click={openUpload}
		class="block w-full rounded-xl border border-dashed border-border px-6 py-10 text-center transition-colors hover:bg-surface-raised"
	>
		<span class="block text-sm text-text-muted">
			Noch keine Belege — lade den ersten hoch, um loszulegen.
		</span>
	</button>
{:else}
	<div style="column-count: 3; column-gap: 12px;">
		{#each recentReceipts as receipt (receipt.id)}
			{@const bucket = bucketFor(receipt.bucket_id)}
			<ReceiptCard
				id={receipt.id}
				receiptDate={receipt.receipt_date}
				totalAmount={receipt.total_amount}
				currency={receipt.currency}
				status={receipt.status}
				bucketName={bucket?.name ?? '…'}
				bucketIsDefault={bucket?.is_default ?? false}
				onOpen={goToReceipts}
			/>
		{/each}
	</div>
{/if}

{#if uploadOpen && uploadOriginRect}
	<UploadModal originRect={uploadOriginRect} onClose={closeUpload} />
{/if}
