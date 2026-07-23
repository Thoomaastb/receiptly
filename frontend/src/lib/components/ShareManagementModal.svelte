<script lang="ts">
	import { onMount } from 'svelte';
	import { m } from '$lib/i18n';

	export let receiptId: string;
	export let onClose: () => void;

	type ShareStatus = 'active' | 'consumed' | 'expired' | 'revoked';

	interface ShareListItem {
		id: string;
		single_use: boolean;
		expires_at: string | null;
		accessed_at: string | null;
		access_count: number;
		created_at: string;
		label: string | null;
		status: ShareStatus;
	}

	type ExpiryPreset = '7d' | '30d' | '90d' | 'unlimited';

	// Anzeige-Label je Status (Server-berechnet, siehe GET /shares).
	const STATUS_LABELS: Record<ShareStatus, string> = {
		active: m.shareManage.statusActive,
		consumed: m.shareManage.statusConsumed,
		expired: m.shareManage.statusExpired,
		revoked: m.shareManage.statusRevoked
	};

	// Badge-Farben: aktiv = Akzent (gleiche Sprache wie der ausgewählte Typ-Radio unten),
	// verbraucht/abgelaufen = gedämpft (kein Fehler, nur nicht mehr nutzbar), widerrufen =
	// Danger-Ton (explizite Nutzeraktion, analog zum Widerrufen-Button-Hover-Zustand).
	const STATUS_BADGE_CLASSES: Record<ShareStatus, string> = {
		active: 'bg-hifi-accent-tint text-hifi-accent-text',
		consumed: 'bg-hifi-bg text-hifi-text-faint',
		expired: 'bg-hifi-bg text-hifi-text-faint',
		revoked: 'bg-danger-bg text-danger'
	};

	// Muss mit EXPIRY_PRESETS-Keys aus backend/app/services/receipt_shares.py übereinstimmen.
	const EXPIRY_OPTIONS: { value: ExpiryPreset; label: string }[] = [
		{ value: '7d', label: m.shareManage.expiry7d },
		{ value: '30d', label: m.shareManage.expiry30d },
		{ value: '90d', label: m.shareManage.expiry90d },
		{ value: 'unlimited', label: m.shareManage.expiryUnlimited }
	];

	// Hartes Limit des Backends (siehe ShareLimitExceededError) — Formular wird bereits
	// hier ausgeblendet, damit der Nutzer nicht erst auf den 400-Fehler läuft.
	const SHARE_LIMIT = 10;

	// Datum+Uhrzeit-Formatierung analog zu formatLastSeen in
	// settings/security/+page.svelte (bislang einziger Präzedenzfall für Zeitstempel mit
	// Uhrzeit-Anteil im Projekt) — $lib/formatDate.ts formatiert bewusst nur das Datum.
	function formatDateTime(iso: string): string {
		return new Date(iso).toLocaleString('de-DE', { dateStyle: 'medium', timeStyle: 'short' });
	}

	let list: ShareListItem[] = [];
	let listLoading = true;
	let listError = '';

	async function loadShares() {
		listLoading = true;
		listError = '';
		try {
			const res = await fetch(`/api/receipts/${receiptId}/shares`, { credentials: 'include' });
			if (!res.ok) throw new Error();
			list = await res.json();
		} catch {
			// Reines Lade-Fehlschlagen blockiert nicht den Rest des Modals (Erstellen bleibt
			// möglich) — nur die Liste zeigt einen Fehlerzustand statt leer zu wirken.
			listError = m.shareManage.listLoadError;
		} finally {
			listLoading = false;
		}
	}

	onMount(loadShares);

	// --- Erstellen-Formular ---
	let singleUse = false;
	let expiryPreset: ExpiryPreset = '30d';
	let label = '';
	let creating = false;
	let createError = '';
	let createdUrl = '';
	let copied = false;

	// "Einmal-Link" schlägt "7 Tage" als Vorauswahl vor (Konzept-Default), bleibt aber
	// änderbar — Einmal-Link + "Unbegrenzt" ist eine gültige, nur nicht vorausgewählte
	// Kombination (orthogonale Dimensionen: Verbrauch vs. Ablaufdatum).
	function selectType(value: boolean) {
		singleUse = value;
		if (value) expiryPreset = '7d';
	}

	async function createShare() {
		createError = '';
		createdUrl = '';
		copied = false;
		creating = true;
		try {
			const res = await fetch(`/api/receipts/${receiptId}/shares`, {
				method: 'POST',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ single_use: singleUse, expiry_preset: expiryPreset, label })
			});
			if (!res.ok) {
				const body = await res.json().catch(() => null);
				throw new Error(body?.detail ?? m.shareManage.createError);
			}
			const created = await res.json();
			createdUrl = created.url;
			list = [
				...list,
				{
					id: created.id,
					single_use: created.single_use,
					expires_at: created.expires_at,
					accessed_at: null,
					access_count: 0,
					created_at: created.created_at,
					label: created.label ?? null,
					status: 'active'
				}
			];
		} catch (err) {
			createError = err instanceof Error ? err.message : m.shareManage.createError;
		} finally {
			creating = false;
		}
	}

	async function copyUrl() {
		await navigator.clipboard.writeText(createdUrl);
		copied = true;
	}

	// --- Widerrufen ---
	let revokingId: string | null = null;
	let revokeError = '';

	async function revokeShare(shareId: string) {
		revokeError = '';
		revokingId = shareId;
		try {
			const res = await fetch(`/api/receipts/${receiptId}/shares/${shareId}`, {
				method: 'DELETE',
				credentials: 'include'
			});
			if (!res.ok && res.status !== 204) {
				const body = await res.json().catch(() => null);
				throw new Error(body?.detail ?? m.shareManage.revokeError);
			}
			// Entfernt den Eintrag nicht mehr aus der Liste (die jetzt die volle Historie
			// zeigt) — nur der Status wechselt auf "revoked", der Eintrag bleibt sichtbar.
			list = list.map((s) => (s.id === shareId ? { ...s, status: 'revoked' } : s));
		} catch (err) {
			revokeError = err instanceof Error ? err.message : m.shareManage.revokeError;
		} finally {
			revokingId = null;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose();
	}

	// Das Cap zählt nur aktive Links — die Liste selbst enthält jetzt die volle Historie
	// (siehe GET /shares), darf also nicht 1:1 als Nenner für die Kappe dienen.
	$: activeCount = list.filter((s) => s.status === 'active').length;
	$: limitReached = activeCount >= SHARE_LIMIT;
</script>

<svelte:window on:keydown={handleKeydown} />

<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
<div class="fixed inset-0 z-40 bg-black opacity-50 backdrop-blur-sm" on:click={onClose} role="presentation"></div>

<div
	class="fixed left-1/2 top-1/2 z-50 max-h-[85vh] w-[92vw] max-w-lg -translate-x-1/2 -translate-y-1/2 overflow-auto rounded-[20px] border border-hifi-border bg-hifi-surface p-5"
	role="dialog"
	aria-modal="true"
	aria-label={m.shareManage.modalTitle}
>
	<div class="mb-4 flex items-center justify-between">
		<h2 class="text-[13.5px] font-bold text-hifi-text">{m.shareManage.modalTitle}</h2>
		<button on:click={onClose} aria-label={m.shareManage.closeAriaLabel} class="rounded-full p-1 text-hifi-text-muted hover:text-hifi-text">
			✕
		</button>
	</div>

	{#if !limitReached}
		<div class="mb-5 rounded-[14px] border border-hifi-border p-4">
			<h3 class="mb-3 text-xs font-semibold uppercase tracking-wide text-hifi-text-faint">
				{m.shareManage.createHeading}
			</h3>

			<fieldset class="mb-3">
				<legend class="mb-1.5 text-xs text-hifi-text-muted">{m.shareManage.typeLabel}</legend>
				<div class="flex gap-2">
					<label
						class="flex flex-1 cursor-pointer items-center justify-center rounded-[10px] border px-3 py-2 text-xs font-medium"
						class:border-hifi-accent={!singleUse}
						class:bg-hifi-accent-tint={!singleUse}
						class:text-hifi-accent-text={!singleUse}
						class:border-hifi-border={singleUse}
						class:text-hifi-text-muted={singleUse}
					>
						<input
							type="radio"
							name="share-type"
							class="sr-only"
							checked={!singleUse}
							on:change={() => selectType(false)}
						/>
						{m.shareManage.typeMultiUse}
					</label>
					<label
						class="flex flex-1 cursor-pointer items-center justify-center rounded-[10px] border px-3 py-2 text-xs font-medium"
						class:border-hifi-accent={singleUse}
						class:bg-hifi-accent-tint={singleUse}
						class:text-hifi-accent-text={singleUse}
						class:border-hifi-border={!singleUse}
						class:text-hifi-text-muted={!singleUse}
					>
						<input
							type="radio"
							name="share-type"
							class="sr-only"
							checked={singleUse}
							on:change={() => selectType(true)}
						/>
						{m.shareManage.typeSingleUse}
					</label>
				</div>
			</fieldset>

			<label class="mb-3 block text-xs">
				<span class="mb-1.5 block text-hifi-text-muted">{m.shareManage.expiryLabel}</span>
				<select bind:value={expiryPreset} class="w-full rounded-[10px] border border-hifi-border bg-hifi-bg p-2 text-sm">
					{#each EXPIRY_OPTIONS as option (option.value)}
						<option value={option.value}>{option.label}</option>
					{/each}
				</select>
			</label>

			<label class="mb-3 block text-xs">
				<span class="mb-1.5 block text-hifi-text-muted">{m.shareManage.labelInputLabel}</span>
				<input
					type="text"
					maxlength="100"
					bind:value={label}
					placeholder={m.shareManage.labelInputPlaceholder}
					class="w-full rounded-[10px] border border-hifi-border bg-hifi-bg p-2 text-sm"
				/>
			</label>

			{#if createError}
				<p class="mb-3 text-xs text-danger">{createError}</p>
			{/if}

			{#if createdUrl}
				<div class="mb-3 rounded-[10px] border border-hifi-border bg-hifi-bg p-3">
					<p class="mb-1.5 text-xs font-semibold text-hifi-text">{m.shareManage.createdUrlLabel}</p>
					<div class="flex items-center gap-2">
						<code class="min-w-0 flex-1 truncate rounded bg-hifi-surface px-2 py-1.5 text-xs text-hifi-text">{createdUrl}</code>
						<button
							type="button"
							on:click={copyUrl}
							class="flex-none rounded-[10px] border border-hifi-border px-2.5 py-1.5 text-xs font-medium text-hifi-text hover:bg-hifi-accent-tint hover:text-hifi-accent-text"
						>
							{copied ? m.shareManage.copyButtonCopied : m.shareManage.copyButton}
						</button>
					</div>
					<p class="mt-1.5 text-xs text-hifi-text-muted">{m.shareManage.createdUrlNote}</p>
				</div>
			{/if}

			<button
				type="button"
				on:click={createShare}
				disabled={creating}
				class="rounded-[10px] bg-hifi-accent px-3.5 py-2 text-xs font-semibold text-white disabled:opacity-50"
			>
				{creating ? m.shareManage.createButtonLoading : m.shareManage.createButton}
			</button>
		</div>
	{:else}
		<p class="mb-5 rounded-[14px] border border-status-warning-border bg-status-warning-bg p-3 text-xs text-status-warning">
			{m.shareManage.limitReachedNote}
		</p>
	{/if}

	<div>
		<h3 class="mb-3 text-xs font-semibold uppercase tracking-wide text-hifi-text-faint">
			{m.shareManage.activeListHeading}
		</h3>

		{#if revokeError}
			<p class="mb-3 text-xs text-danger">{revokeError}</p>
		{/if}

		{#if listLoading}
			<p class="text-xs text-hifi-text-muted">{m.shareManage.listLoading}</p>
		{:else if listError}
			<p class="text-xs text-danger">{listError}</p>
		{:else if list.length === 0}
			<p class="text-xs text-hifi-text-muted">{m.shareManage.emptyState}</p>
		{:else}
			<ul class="flex flex-col">
				{#each list as share (share.id)}
					<li class="flex items-center justify-between gap-3 border-b border-hifi-border py-3 last:border-0">
						<div class="min-w-0 flex-1 text-xs">
							{#if share.label}
								<div class="truncate text-[13px] font-semibold text-hifi-text">{share.label}</div>
							{/if}
							<div
								class="mt-0.5 flex flex-wrap items-center gap-1.5"
								class:font-semibold={!share.label}
								class:text-hifi-text={!share.label}
								class:text-hifi-text-faint={!!share.label}
							>
								<span>{share.single_use ? m.shareManage.typeSingleUse : m.shareManage.typeMultiUse}</span>
								<span
									class="inline-flex items-center rounded-full px-2.5 py-0.5 text-[11.5px] font-medium {STATUS_BADGE_CLASSES[
										share.status
									]}"
								>
									{STATUS_LABELS[share.status]}
								</span>
							</div>
							<div class="mt-0.5 text-hifi-text-faint">
								{m.shareManage.createdLabel} {formatDateTime(share.created_at)}
							</div>
							<div class="text-hifi-text-faint">
								{m.shareManage.expiresLabel}: {share.expires_at ? formatDateTime(share.expires_at) : m.shareManage.expiresUnlimited}
							</div>
							<div class="text-hifi-text-faint">
								{share.accessed_at
									? `${m.shareManage.lastAccessLabel}: ${formatDateTime(share.accessed_at)} (${share.access_count} ${m.shareManage.accessCountLabel})`
									: m.shareManage.neverAccessedLabel}
							</div>
						</div>
						{#if share.status === 'active'}
							<button
								type="button"
								on:click={() => revokeShare(share.id)}
								disabled={revokingId === share.id}
								class="flex-none rounded-[10px] border border-hifi-border px-2.5 py-1.5 text-xs font-medium text-hifi-text-muted hover:border-danger-border hover:text-danger disabled:opacity-50"
							>
								{revokingId === share.id ? m.shareManage.revokeButtonLoading : m.shareManage.revokeButton}
							</button>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	</div>
</div>
