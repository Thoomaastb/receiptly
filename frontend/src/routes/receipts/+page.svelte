<script lang="ts">
	import { onMount } from 'svelte';

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

	let receipts: Receipt[] = [];
	let loading = true;
	let errorMessage = '';

	onMount(async () => {
		try {
			const res = await fetch('/api/receipts', { credentials: 'include' });
			if (!res.ok) throw new Error(`Belege konnten nicht geladen werden (${res.status})`);
			receipts = await res.json();
		} catch (err) {
			errorMessage = err instanceof Error ? err.message : 'Unbekannter Fehler.';
		} finally {
			loading = false;
		}
	});

	function statusLabel(status: string): string {
		switch (status) {
			case 'pending':
				return 'Wird verarbeitet';
			case 'processed':
				return 'Verarbeitet';
			case 'needs_review':
				return 'Prüfung nötig';
			default:
				return status;
		}
	}
</script>

<h1 class="mb-6 text-xl font-semibold">Belege</h1>

{#if loading}
	<p class="text-sm text-text-muted">Belege werden geladen …</p>
{:else if errorMessage}
	<p class="text-sm text-red-500">{errorMessage}</p>
{:else if receipts.length === 0}
	<p class="text-sm text-text-muted">Noch keine Belege hochgeladen.</p>
{:else}
	<!-- Einfache Liste als Zwischenstand — das Mosaik-Feed aus dem UI-Konzept
	     (Masonry, Bucket-Pills, Card-to-Modal) kommt mit dem UI-Feinschliff-Paket -->
	<ul class="flex flex-col gap-3">
		{#each receipts as receipt (receipt.id)}
			<li class="rounded-lg border border-border bg-surface-raised p-4">
				<div class="flex items-center justify-between">
					<span class="text-sm">
						{receipt.receipt_date ?? 'Datum folgt (OCR/KI)'}
					</span>
					<span class="text-xs text-text-muted">{statusLabel(receipt.status)}</span>
				</div>
				<div class="mt-1 text-lg font-medium">
					{receipt.total_amount !== null
						? `${receipt.total_amount.toFixed(2)} ${receipt.currency}`
						: 'Betrag folgt (OCR/KI)'}
				</div>
			</li>
		{/each}
	</ul>
{/if}
