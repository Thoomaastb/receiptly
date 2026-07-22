<script lang="ts">
	import { onMount } from 'svelte';
	import { m } from '$lib/i18n';

	// v1-Typvokabular, dupliziert aus backend/app/services/notifications.py::NOTIFICATION_TYPES
	// (kein Codegen im Projekt, siehe categoryLabel() in $lib/categories als bestehendes
	// Vorbild für eine unabhängig gepflegte Parallel-Liste). Bei Drift gegen das Backend
	// liefert PUT einen 400er — dieser Fall zeigt saveError, kein Crash.
	const NOTIFICATION_TYPES: Record<string, string[]> = {
		garantie: ['warranty_expiring'],
		sicherheit: [
			'security_password_changed',
			'security_totp_enabled',
			'security_totp_disabled',
			'security_passkey_registered',
			'security_passkey_removed',
			'security_recovery_code_used',
			'security_session_terminated',
			'security_passkey_exclusive_login_toggled',
			'security_new_login'
		]
	};

	const CATEGORY_GROUP_LABELS: Record<string, string> = {
		garantie: m.notificationSettings.groupGarantie,
		sicherheit: m.notificationSettings.groupSicherheit
	};

	function typeLabel(type: string): string {
		return (m.notificationSettings.typeLabels as Record<string, string>)[type] ?? type;
	}

	let loading = true;
	let loadError = '';
	// Ein Boolean pro bekanntem Typ statt eines rohen string[] — vereinfacht das
	// Checkbox-Binding (bind:checked) gegenüber ständigem Array-Filtern bei jedem Klick.
	let optedIn: Record<string, boolean> = {};
	let saving = false;
	let saveMessage = '';
	let saveError = '';

	async function loadPreferences() {
		loading = true;
		loadError = '';
		try {
			const res = await fetch('/api/settings/notification-preferences', { credentials: 'include' });
			if (!res.ok) throw new Error(`${res.status}`);
			const data: { opted_in_types: string[] } = await res.json();
			const next: Record<string, boolean> = {};
			for (const types of Object.values(NOTIFICATION_TYPES)) {
				for (const type of types) {
					next[type] = data.opted_in_types.includes(type);
				}
			}
			optedIn = next;
		} catch {
			loadError = m.notificationSettings.loadError;
		} finally {
			loading = false;
		}
	}

	async function handleSave() {
		saving = true;
		saveMessage = '';
		saveError = '';
		try {
			const optedInTypes = Object.entries(optedIn)
				.filter(([, checked]) => checked)
				.map(([type]) => type);
			const res = await fetch('/api/settings/notification-preferences', {
				method: 'PUT',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ opted_in_types: optedInTypes })
			});
			if (!res.ok) {
				const body = await res.json().catch(() => null);
				throw new Error(body?.detail ?? m.notificationSettings.saveError);
			}
			saveMessage = m.notificationSettings.saveSuccess;
		} catch (err) {
			saveError = err instanceof Error ? err.message : m.notificationSettings.saveError;
		} finally {
			saving = false;
		}
	}

	onMount(() => {
		loadPreferences();
	});
</script>

<div class="flex max-w-2xl flex-col gap-6">
	<div class="rounded-[14px] border border-hifi-border bg-hifi-surface p-6">
		<h2 class="mb-1 text-[13.5px] font-bold text-hifi-text">{m.notificationSettings.cardTitle}</h2>
		<p class="mb-4 text-sm text-hifi-text-muted">{m.notificationSettings.cardDescription}</p>

		{#if loading}
			<p class="text-sm text-hifi-text-muted">Wird geladen …</p>
		{:else if loadError}
			<p class="text-sm text-danger">{loadError}</p>
		{:else}
			<div class="flex flex-col gap-5">
				{#each Object.entries(NOTIFICATION_TYPES) as [category, types] (category)}
					<div>
						<h3 class="mb-2 text-[11.5px] font-bold uppercase tracking-[0.04em] text-hifi-text-faint">
							{CATEGORY_GROUP_LABELS[category] ?? category}
						</h3>
						<div class="flex flex-col gap-2">
							{#each types as type (type)}
								<label class="flex cursor-pointer items-center gap-2.5 text-sm text-hifi-text">
									<span class="relative flex h-[18px] w-[18px] flex-none items-center justify-center">
										<input
											type="checkbox"
											bind:checked={optedIn[type]}
											class="peer absolute inset-0 h-full w-full cursor-pointer appearance-none rounded-[5px] border border-hifi-border bg-hifi-surface transition-colors checked:border-hifi-accent checked:bg-hifi-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-hifi-accent focus-visible:ring-offset-2"
										/>
										<svg
											class="pointer-events-none absolute h-3 w-3 text-white opacity-0 transition-opacity peer-checked:opacity-100"
											viewBox="0 0 16 16"
											fill="none"
											stroke="currentColor"
											stroke-width="2.5"
											stroke-linecap="round"
											stroke-linejoin="round"
											aria-hidden="true"
										>
											<path d="M3.5 8.5l3 3 6-7" />
										</svg>
									</span>
									{typeLabel(type)}
								</label>
							{/each}
						</div>
					</div>
				{/each}

				{#if saveMessage}
					<p class="text-sm text-hifi-accent-text">{saveMessage}</p>
				{/if}
				{#if saveError}
					<p class="text-sm text-danger">{saveError}</p>
				{/if}

				<button
					type="button"
					on:click={handleSave}
					disabled={saving}
					class="self-start rounded-[10px] bg-hifi-accent px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
				>
					{saving ? m.notificationSettings.saveButtonSaving : m.notificationSettings.saveButton}
				</button>
			</div>
		{/if}
	</div>
</div>
