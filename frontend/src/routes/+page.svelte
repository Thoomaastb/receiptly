<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import UploadModal from '$lib/components/UploadModal.svelte';
	import { categoryLabel } from '$lib/categories';

	interface Receipt {
		id: string;
		bucket_id: string;
		status: string;
		receipt_date: string | null;
		total_amount: number | null;
		currency: string;
		created_at: string;
		warranty_expires_at?: string | null;
		merchant_name?: string | null;
		category?: string | null;
	}

	let allReceipts: Receipt[] = [];
	let loading = true;

	let uploadOpen = false;
	let uploadCaptureMode: 'camera' | 'file' = 'file';

	const thumbHeights = [92, 140, 110, 160, 100, 128];

	async function loadReceipts() {
		try {
			const res = await fetch('/api/receipts', { credentials: 'include' });
			if (res.ok) allReceipts = await res.json();
		} finally {
			loading = false;
		}
	}

	onMount(loadReceipts);

	$: recentReceipts = allReceipts.slice(0, 6);
	$: totalCount = allReceipts.length;
	$: expiringCount = allReceipts.filter((r) => {
		if (!r.warranty_expires_at) return false;
		const days = (new Date(r.warranty_expires_at).getTime() - Date.now()) / 86_400_000;
		return days <= 30;
	}).length;
	$: monthTotal = (() => {
		const now = new Date();
		const sum = allReceipts
			.filter((r) => {
				if (!r.total_amount || !r.receipt_date) return false;
				const d = new Date(r.receipt_date);
				return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
			})
			.reduce((s, r) => s + (r.total_amount ?? 0), 0);
		return sum > 0 ? `${sum.toFixed(2)} €` : '–';
	})();

	const todayLabel = new Date().toLocaleDateString('de-DE', {
		day: 'numeric',
		month: 'long',
		year: 'numeric'
	});

	function fileExt(status: string): string {
		// Platzhalter, solange file_path nicht Teil der Listen-Antwort ist
		return status === 'pending' ? '…' : 'DOC';
	}

	function openUpload(mode: 'camera' | 'file') {
		uploadCaptureMode = mode;
		uploadOpen = true;
	}

	function closeUpload() {
		uploadOpen = false;
		loadReceipts();
	}

	function goToReceipts() {
		goto('/receipts');
	}

	function openReceiptDetail(receiptId: string) {
		goto(`/receipts?open=${receiptId}`);
	}
</script>

<div class="mb-7">
	<div class="text-[26px] font-extrabold tracking-tight text-hifi-text">Übersicht</div>
	<div class="mt-1 text-sm text-hifi-text-muted">{todayLabel}</div>
</div>

<div class="mb-9">
	<button
		on:click={() => openUpload('camera')}
		class="box-border flex w-full flex-col gap-2.5 rounded-2xl bg-hifi-accent px-7 py-6 text-left text-white"
	>
		<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
			<rect x="3" y="7" width="18" height="13" rx="2" />
			<path d="M8 7l1.5-2.5h5L16 7" />
			<circle cx="12" cy="13.5" r="3.5" />
		</svg>
		<div class="text-[17px] font-bold">Scannen</div>
		<div class="text-[13.5px] text-white/75">Kamera direkt öffnen (mobil)</div>
	</button>
	<button
		on:click={() => openUpload('file')}
		class="mt-3 flex items-center gap-1.5 text-[13px] font-semibold text-hifi-text-muted hover:text-hifi-text"
	>
		<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
			<path d="M12 16V4M8 8l4-4 4 4" />
			<path d="M4 16v3a2 2 0 002 2h12a2 2 0 002-2v-3" />
		</svg>
		Oder Datei hochladen (PDF, JPG, PNG)
	</button>
</div>

{#if totalCount > 0}
	<div class="mb-9 grid grid-cols-3 gap-4">
		<div class="rounded-2xl border border-hifi-border bg-hifi-surface px-[22px] py-5">
			<div class="mb-2 text-[12.5px] font-semibold text-hifi-text-muted">Gesamt Belege</div>
			<div class="font-mono text-[28px] font-extrabold text-hifi-text">{totalCount}</div>
		</div>
		<div class="rounded-2xl border border-hifi-border bg-hifi-surface px-[22px] py-5">
			<div class="mb-2 text-[12.5px] font-semibold text-hifi-text-muted">Ablaufende Garantien</div>
			<div class="font-mono text-[28px] font-extrabold" style="color: {expiringCount > 0 ? 'var(--color-danger)' : 'var(--color-text-hifi)'}">
				{expiringCount}
			</div>
		</div>
		<div class="rounded-2xl border border-hifi-border bg-hifi-surface px-[22px] py-5">
			<div class="mb-2 text-[12.5px] font-semibold text-hifi-text-muted">Diesen Monat</div>
			<div class="font-mono text-[28px] font-extrabold text-hifi-text">{monthTotal}</div>
		</div>
	</div>
{/if}

<div class="mb-4 flex items-baseline justify-between">
	<div class="text-[15.5px] font-bold text-hifi-text">Zuletzt hinzugefügt</div>
	{#if recentReceipts.length > 0}
		<button on:click={goToReceipts} class="text-[13px] font-semibold text-hifi-accent">Alle anzeigen</button>
	{/if}
</div>

{#if loading}
	<p class="text-sm text-hifi-text-muted">Wird geladen …</p>
{:else if recentReceipts.length === 0}
	<button
		on:click={() => openUpload('file')}
		class="block w-full rounded-2xl border border-dashed border-hifi-border px-6 py-10 text-center transition-colors hover:bg-hifi-accent-tint"
	>
		<span class="text-sm text-hifi-text-muted">Noch keine Belege — lade den ersten hoch, um loszulegen.</span>
	</button>
{:else}
	<div style="columns: 3; column-gap: 16px;">
		{#each recentReceipts as receipt, i (receipt.id)}
			<button
				on:click={() => openReceiptDetail(receipt.id)}
				class="mb-4 block w-full overflow-hidden rounded-2xl border border-hifi-border bg-hifi-surface text-left"
				style="break-inside: avoid;"
			>
				<div
					class="flex items-center justify-center"
					style="height: {thumbHeights[i % thumbHeights.length]}px; background: repeating-linear-gradient(135deg, var(--color-stripe-thumb-a), var(--color-stripe-thumb-a) 8px, var(--color-stripe-thumb-b) 8px, var(--color-stripe-thumb-b) 16px);"
				>
					<span class="rounded-[5px] bg-hifi-surface/80 px-2 py-1 font-mono text-[11px] font-semibold tracking-wide text-hifi-accent-text">
						{fileExt(receipt.status)}
					</span>
				</div>
				<div class="px-4 py-3.5">
					<div class="mb-2 flex items-center justify-between gap-2">
						<span class="text-xs text-hifi-text-faint">{receipt.receipt_date ?? 'Datum folgt'}</span>
						{#if receipt.category}
							<span class="truncate text-[11px] font-semibold text-hifi-text-muted">{categoryLabel(receipt.category)}</span>
						{/if}
					</div>
					<div class="font-mono text-[13.5px] font-bold text-hifi-text">
						{receipt.total_amount !== null ? `${receipt.total_amount.toFixed(2)} ${receipt.currency}` : 'Betrag folgt'}
					</div>
					{#if receipt.merchant_name}
						<div class="mt-1 truncate text-[12.5px] text-hifi-text-muted">{receipt.merchant_name}</div>
					{/if}
				</div>
			</button>
		{/each}
	</div>
{/if}

{#if uploadOpen}
	<UploadModal onClose={closeUpload} captureMode={uploadCaptureMode} />
{/if}
