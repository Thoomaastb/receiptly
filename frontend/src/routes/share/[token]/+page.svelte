<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { page } from '$app/stores';
	import { formatDate } from '$lib/formatDate';
	import { m } from '$lib/i18n';

	// Erste anonyme Fetch-Stelle im Projekt: BEWUSST ohne credentials: 'include' — der
	// Endpoint ist unauthentifiziert und ignoriert Cookies ohnehin, es gibt aber keinen
	// Grund, sie trotzdem mitzuschicken (alle ~17 bestehenden Fetch-Stellen zielen auf
	// authentifizierte Endpoints und senden Credentials mit, das wäre hier leicht
	// copy-paste-fehleranfällig gewesen).

	interface PublicReceiptShare {
		merchant_name: string | null;
		receipt_date: string | null;
		total_amount: number | null;
		currency: string;
		content_type: string;
	}

	$: token = $page.params.token;

	let loading = true;
	let error = false;
	let share: PublicReceiptShare | null = null;
	let fileUrl: string | null = null;

	$: isImage = share?.content_type.startsWith('image/') ?? false;

	// Der Datei-Endpoint konsumiert Einmal-Links beim ERSTEN erfolgreichen Request (siehe
	// Backend). Ein <img src="..."> UND ein separater Download-Link, die beide direkt auf
	// /api/share/{token}/file zeigen, wären zwei unabhängige Requests — der zweite (Klick
	// auf "Herunterladen") träfe dann bereits einen verbrauchten Link. Deshalb wird die
	// Datei genau EINMAL als Blob geholt und darüber eine einzige Object-URL erzeugt, die
	// sowohl <img>/PDF-Link als auch der Download-Link referenzieren — kein zweiter
	// Netzwerk-Request gegen den Datei-Endpoint, unabhängig vom Content-Type.
	async function loadFileBlob() {
		try {
			const res = await fetch(`/api/share/${token}/file`);
			if (!res.ok) {
				error = true;
				return;
			}
			const blob = await res.blob();
			fileUrl = URL.createObjectURL(blob);
		} catch {
			error = true;
		}
	}

	onMount(async () => {
		try {
			const res = await fetch(`/api/share/${token}`);
			if (!res.ok) {
				error = true;
				return;
			}
			share = await res.json();
			await loadFileBlob();
		} catch {
			error = true;
		} finally {
			loading = false;
		}
	});

	onDestroy(() => {
		if (fileUrl) URL.revokeObjectURL(fileUrl);
	});
</script>

<div class="flex min-h-screen items-center justify-center bg-hifi-bg px-4 py-10">
	{#if loading}
		<p class="text-sm text-hifi-text-muted">{m.sharePublic.loading}</p>
	{:else if error || !share}
		<p class="text-sm text-hifi-text-muted">{m.sharePublic.invalidLink}</p>
	{:else}
		<div class="w-full max-w-lg rounded-2xl border border-hifi-border bg-hifi-surface p-6">
			<h1 class="text-lg font-bold text-hifi-text">{share.merchant_name ?? m.sharePublic.fallbackTitle}</h1>
			{#if share.receipt_date}
				<p class="mt-1 text-sm text-hifi-text-muted">{formatDate(share.receipt_date)}</p>
			{/if}
			{#if share.total_amount !== null}
				<p class="mt-1 text-sm text-hifi-text-muted">
					{m.sharePublic.amountLabel}: {share.total_amount.toFixed(2)} {share.currency}
				</p>
			{/if}

			<div class="mt-4">
				{#if isImage}
					<img src={fileUrl ?? ''} alt={m.sharePublic.previewAlt} class="max-h-[520px] w-full rounded-xl object-contain" />
				{:else}
					<!-- fileUrl ist eine blob:-URL (siehe loadFileBlob) — ein <a target="_blank">
					     auf eine blob:-URL wird von manchen Browsern als Download statt als
					     Inline-Vorschau behandelt (im Gegensatz zu einer echten HTTP-URL mit
					     Content-Disposition: inline). Ein eingebettetes <iframe> zwingt den
					     Browser-eigenen PDF-Viewer zum Rendern innerhalb der Seite, unabhängig
					     von dieser Download-Heuristik — deshalb hier bewusst doch ein <iframe>,
					     anders als die authentifizierte Vorschau in ReceiptDetailView.svelte
					     (die auf eine echte URL verlinkt, nicht auf einen Blob). -->
					<iframe src={fileUrl ?? ''} title={m.sharePublic.previewAlt} class="h-[520px] w-full rounded-xl border border-hifi-border"></iframe>
				{/if}
			</div>

			<div class="mt-4">
				<a href={fileUrl ?? ''} download class="font-medium text-hifi-accent-text underline">{m.sharePublic.download}</a>
			</div>
		</div>
	{/if}
</div>
