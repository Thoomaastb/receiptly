<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import ReceiptCard from '$lib/components/ReceiptCard.svelte';
	import ReceiptModal from '$lib/components/ReceiptModal.svelte';
	import SectionHeader from '$lib/components/SectionHeader.svelte';

	interface Receipt {
		id: string;
		bucket_id: string;
		status: string;
		receipt_date: string | null;
		total_amount: number | null;
		currency: string;
		thumb_path: string | null;
		created_at: string;
	}

	interface ReceiptDetail extends Receipt {
		ocr_raw_text: string | null;
		is_high_value: boolean;
		warranty_expires_at: string | null;
	}

	interface Bucket {
		id: string;
		name: string;
		type: string;
		visibility: string;
		is_default: boolean;
	}

	let receipts: Receipt[] = [];
	let buckets: Bucket[] = [];
	let loading = true;
	let errorMessage = '';
	let groupByBucket = false;
	let openReceipt: ReceiptDetail | null = null;

	onMount(async () => {
		try {
			const [receiptsRes, bucketsRes] = await Promise.all([
				fetch('/api/receipts', { credentials: 'include' }),
				fetch('/api/buckets', { credentials: 'include' })
			]);
			if (!receiptsRes.ok) throw new Error(`Belege konnten nicht geladen werden (${receiptsRes.status})`);
			if (!bucketsRes.ok) throw new Error(`Buckets konnten nicht geladen werden (${bucketsRes.status})`);
			receipts = await receiptsRes.json();
			buckets = await bucketsRes.json();
		} catch (err) {
			errorMessage = err instanceof Error ? err.message : 'Unbekannter Fehler.';
		} finally {
			loading = false;
		}
	});

	function bucketFor(bucketId: string): Bucket | undefined {
		return buckets.find((b) => b.id === bucketId);
	}

	$: bucketFilterId = $page.url.searchParams.get('bucket');
	$: bucketFilter = bucketFilterId ? bucketFor(bucketFilterId) : undefined;
	$: visibleReceipts = bucketFilterId
		? receipts.filter((r) => r.bucket_id === bucketFilterId)
		: receipts;

	function clearBucketFilter() {
		goto('/receipts');
	}

	// Reihenfolge exakt nach UI-Konzept: Household-Bucket zuerst, dann eigene Personal Buckets
	$: groupedSections = groupByBucket
		? buckets
				.slice()
				.sort((a, b) => Number(b.is_default) - Number(a.is_default))
				.map((bucket) => ({
					bucket,
					items: visibleReceipts.filter((r) => r.bucket_id === bucket.id)
				}))
				.filter((section) => section.items.length > 0)
		: [];

	async function openModal(id: string) {
		const res = await fetch(`/api/receipts/${id}`, { credentials: 'include' });
		if (!res.ok) return;
		openReceipt = await res.json();
	}

	function closeModal() {
		openReceipt = null;
	}
</script>

<h1 class="mb-4 text-xl font-semibold">Belege</h1>

{#if bucketFilter}
	<div class="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-surface-raised px-3 py-1 text-xs">
		<span>Bucket: {bucketFilter.name}</span>
		<button on:click={clearBucketFilter} aria-label="Filter entfernen" class="text-text-muted hover:text-text">✕</button>
	</div>
{/if}

{#if !loading && !errorMessage && visibleReceipts.length > 0}
	<button
		class="mb-4 block rounded-full border border-border px-3 py-1 text-xs text-text-muted hover:text-text"
		on:click={() => (groupByBucket = !groupByBucket)}
	>
		{groupByBucket ? 'Flach anzeigen' : 'Nach Bucket gruppieren'}
	</button>
{/if}

{#if loading}
	<p class="text-sm text-text-muted">Belege werden geladen …</p>
{:else if errorMessage}
	<p class="text-sm text-red-500">{errorMessage}</p>
{:else if visibleReceipts.length === 0}
	<p class="text-sm text-text-muted">Noch keine Belege hochgeladen.</p>
{:else if groupByBucket}
	{#each groupedSections as section (section.bucket.id)}
		<SectionHeader
			icon={section.bucket.is_default ? 'home' : 'lock'}
			name={section.bucket.name}
			count={section.items.length}
			sum={section.items.reduce((sum, r) => sum + (r.total_amount ?? 0), 0)}
		/>
		<div class="mb-6 mt-3" style="column-count: 2; column-gap: 12px;">
			{#each section.items as receipt (receipt.id)}
				<ReceiptCard
					id={receipt.id}
					receiptDate={receipt.receipt_date}
					totalAmount={receipt.total_amount}
					currency={receipt.currency}
					status={receipt.status}
					bucketName={section.bucket.name}
					bucketIsDefault={section.bucket.is_default}
					showBucketPill={false}
					onOpen={openModal}
				/>
			{/each}
		</div>
	{/each}
{:else}
	<div style="column-count: 2; column-gap: 12px;">
		{#each visibleReceipts as receipt (receipt.id)}
			{@const bucket = bucketFor(receipt.bucket_id)}
			<ReceiptCard
				id={receipt.id}
				receiptDate={receipt.receipt_date}
				totalAmount={receipt.total_amount}
				currency={receipt.currency}
				status={receipt.status}
				bucketName={bucket?.name ?? '…'}
				bucketIsDefault={bucket?.is_default ?? false}
				onOpen={openModal}
			/>
		{/each}
	</div>
{/if}

{#if openReceipt}
	<ReceiptModal
		receiptId={openReceipt.id}
		receiptDate={openReceipt.receipt_date}
		totalAmount={openReceipt.total_amount}
		currency={openReceipt.currency}
		status={openReceipt.status}
		ocrRawText={openReceipt.ocr_raw_text}
		isHighValue={openReceipt.is_high_value}
		warrantyExpiresAt={openReceipt.warranty_expires_at}
		onClose={closeModal}
	/>
{/if}
