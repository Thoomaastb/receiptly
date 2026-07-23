<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { m } from '$lib/i18n';
	import DeleteAccountDialog from '$lib/components/DeleteAccountDialog.svelte';

	// Kein Admin-Gate — jeder User verwaltet sein eigenes Konto (Konzept Q10: reine
	// Selbstlöschung in v1). isAdmin wird trotzdem geladen, weil nur Admins die
	// Sicherheitsrichtlinien lesen dürfen (GET /settings/security-policy ist
	// require_admin-geschützt) — siehe der ausführliche Kommentar dazu in
	// DeleteAccountDialog.svelte für die daraus folgende UX-Einschränkung bei Nicht-Admins.
	let checkingContext = true;
	let passkeyExclusiveActive = false;

	let dialogOpen = false;

	async function loadContext() {
		checkingContext = true;
		try {
			const meRes = await fetch('/api/auth/me', { credentials: 'include' });
			if (!meRes.ok) return;
			const me: { role: string } = await meRes.json();
			if (me.role !== 'admin') return;

			const policyRes = await fetch('/api/settings/security-policy', { credentials: 'include' });
			if (!policyRes.ok) return;
			const policy: { passkey_exclusive_login: boolean } = await policyRes.json();
			passkeyExclusiveActive = policy.passkey_exclusive_login;
		} catch {
			// Best effort — bei Fehlschlag bleibt passkeyExclusiveActive false, der Dialog
			// zeigt dann beide Faktor-Tabs (adaptiver Fallback greift bei Bedarf).
		} finally {
			checkingContext = false;
		}
	}

	function openDeleteDialog() {
		dialogOpen = true;
	}

	function closeDeleteDialog() {
		dialogOpen = false;
	}

	function handleDeleted() {
		// Backend hat beim Löschantrag bereits ALLE Sessions invalidiert (auch die aktuelle)
		// — die SPA muss also selbst zum Login navigieren, keine eigene Session mehr zum
		// Aufräumen.
		goto('/login');
	}

	onMount(loadContext);
</script>

<div class="flex max-w-2xl flex-col gap-6">
	<div class="rounded-[14px] border border-hifi-border bg-hifi-surface p-6">
		<h2 class="mb-1 text-[13.5px] font-bold text-hifi-text">{m.dataExport.cardTitle}</h2>
		<p class="mb-4 text-sm leading-relaxed text-hifi-text-muted">{m.dataExport.cardDescription}</p>
		<a
			href="/api/account/export"
			download
			class="inline-flex self-start rounded-[10px] border border-hifi-border px-4 py-2.5 text-sm font-semibold text-hifi-text transition-colors hover:bg-hifi-accent-tint hover:text-hifi-accent-text"
		>
			{m.dataExport.downloadButton}
		</a>
	</div>

	<div class="rounded-[14px] border border-danger-border bg-hifi-surface p-6">
		<h2 class="mb-1 text-[13.5px] font-bold text-hifi-text">{m.accountDeletion.cardTitle}</h2>
		<p class="mb-4 text-sm leading-relaxed text-hifi-text-muted">{m.accountDeletion.cardDescription}</p>
		<button
			type="button"
			on:click={openDeleteDialog}
			disabled={checkingContext}
			class="rounded-[10px] bg-danger px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
		>
			{m.accountDeletion.openButton}
		</button>
	</div>
</div>

{#if dialogOpen}
	<DeleteAccountDialog onClose={closeDeleteDialog} onDeleted={handleDeleted} {passkeyExclusiveActive} />
{/if}
