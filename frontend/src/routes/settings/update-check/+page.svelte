<script lang="ts">
	import { onMount } from 'svelte';
	import { m } from '$lib/i18n';

	interface UpdateCheckSettings {
		enabled: boolean;
	}

	let checkingAccess = true;
	let isAdmin = false;

	let loading = true;
	let loadError = '';
	let enabled = false;
	let toggleError = '';
	let toggling = false;

	async function loadAccess(): Promise<boolean> {
		try {
			const meRes = await fetch('/api/auth/me', { credentials: 'include' });
			if (!meRes.ok) return false;
			const me: { role: string } = await meRes.json();
			return me.role === 'admin';
		} catch {
			return false;
		}
	}

	async function loadSettings() {
		loading = true;
		loadError = '';
		try {
			const res = await fetch('/api/settings/update-check', { credentials: 'include' });
			if (!res.ok) throw new Error(`${res.status}`);
			const settings: UpdateCheckSettings = await res.json();
			enabled = settings.enabled;
		} catch {
			loadError = m.updateCheck.loadError;
		} finally {
			loading = false;
		}
	}

	// Einzelner Schalter ohne weitere Formularfelder auf dieser Seite — deshalb bewusst
	// optimistisch mit sofortigem PUT statt des Batch-"Speichern"-Musters aus
	// security-policy/+page.svelte (dort mehrere Felder, ein gemeinsamer Save-Klick).
	// Bei Fehler wird der Zustand vor dem Klick zurückgerollt.
	async function handleToggle() {
		const previous = enabled;
		enabled = !enabled;
		toggleError = '';
		toggling = true;
		try {
			const res = await fetch('/api/settings/update-check', {
				method: 'PUT',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ enabled })
			});
			if (!res.ok) throw new Error(`${res.status}`);
		} catch {
			enabled = previous;
			toggleError = m.updateCheck.saveError;
		} finally {
			toggling = false;
		}
	}

	onMount(async () => {
		isAdmin = await loadAccess();
		checkingAccess = false;
		if (!isAdmin) return;
		loadSettings();
	});
</script>

{#if checkingAccess}
	<p class="text-sm text-hifi-text-muted">{m.common.checking}</p>
{:else if !isAdmin}
	<p class="text-sm text-hifi-text-muted">{m.updateCheck.accessDenied}</p>
{:else}
	<div class="max-w-2xl">
		<div class="rounded-[14px] border border-hifi-border bg-hifi-surface p-6">
			<h2 class="mb-1 text-[13.5px] font-bold text-hifi-text">{m.updateCheck.cardTitle}</h2>
			<p class="mb-4 text-sm text-hifi-text-muted">{m.updateCheck.cardDescription}</p>

			{#if loading}
				<p class="text-sm text-hifi-text-muted">Wird geladen …</p>
			{:else if loadError}
				<p class="text-sm text-danger">{loadError}</p>
			{:else}
				<div class="flex items-center justify-between gap-4">
					<div class="min-w-0">
						<div class="text-sm font-semibold text-hifi-text">{m.updateCheck.toggleLabel}</div>
						<div class="mt-0.5 text-[12.5px] leading-relaxed text-hifi-text-muted">
							{m.updateCheck.toggleDescription}
						</div>
					</div>
					<button
						type="button"
						role="switch"
						aria-checked={enabled}
						aria-label={m.updateCheck.toggleLabel}
						disabled={toggling}
						on:click={handleToggle}
						class="relative h-6 w-11 flex-none rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-hifi-accent focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 {enabled
							? 'bg-hifi-accent'
							: 'bg-hifi-border'}"
					>
						<span
							class="absolute left-0 top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform {enabled
								? 'translate-x-[22px]'
								: 'translate-x-0.5'}"
						></span>
					</button>
				</div>

				{#if toggleError}
					<p class="mt-3 text-sm text-danger">{toggleError}</p>
				{/if}
			{/if}
		</div>
	</div>
{/if}
