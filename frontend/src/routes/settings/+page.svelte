<script lang="ts">
	import { onMount } from 'svelte';

	interface AISettings {
		provider: string;
		has_api_key: boolean;
		custom_endpoint: string | null;
	}

	interface User {
		role: string;
	}

	let isAdmin = false;
	let checkingAccess = true;

	let settings: AISettings | null = null;
	let provider = 'ollama';
	let apiKeyInput = '';
	let customEndpoint = '';
	let loading = true;
	let saving = false;
	let saveMessage = '';
	let errorMessage = '';

	const providerLabels: Record<string, string> = {
		ollama: 'Ollama (lokal, Standard)',
		openai: 'OpenAI',
		anthropic: 'Anthropic',
		custom: 'Custom / OpenAI-kompatibel'
	};

	onMount(async () => {
		try {
			const meRes = await fetch('/api/auth/me', { credentials: 'include' });
			if (!meRes.ok) throw new Error('Nicht angemeldet');
			const me: User = await meRes.json();
			isAdmin = me.role === 'admin';
			if (!isAdmin) return;

			const res = await fetch('/api/settings/ai-provider', { credentials: 'include' });
			if (!res.ok) throw new Error(`Einstellungen konnten nicht geladen werden (${res.status})`);
			settings = await res.json();
			provider = settings!.provider;
			customEndpoint = settings!.custom_endpoint ?? '';
		} catch (err) {
			errorMessage = err instanceof Error ? err.message : 'Unbekannter Fehler.';
		} finally {
			checkingAccess = false;
			loading = false;
		}
	});

	async function handleSave() {
		saving = true;
		saveMessage = '';
		errorMessage = '';

		try {
			const body: Record<string, string> = { provider };
			if (apiKeyInput.trim()) body.api_key = apiKeyInput.trim();
			if (provider === 'custom') body.custom_endpoint = customEndpoint.trim();

			const res = await fetch('/api/settings/ai-provider', {
				method: 'PUT',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(body)
			});
			if (!res.ok) throw new Error(`Speichern fehlgeschlagen (${res.status})`);

			settings = await res.json();
			apiKeyInput = '';
			saveMessage = 'Gespeichert.';
		} catch (err) {
			errorMessage = err instanceof Error ? err.message : 'Unbekannter Fehler beim Speichern.';
		} finally {
			saving = false;
		}
	}
</script>

<h1 class="mb-6 text-xl font-semibold">Einstellungen</h1>

{#if checkingAccess}
	<p class="text-sm text-text-muted">Wird geprüft …</p>
{:else if !isAdmin}
	<p class="text-sm text-text-muted">Diese Einstellungen sind nur für Admins sichtbar.</p>
{:else}
	<div class="max-w-lg rounded-lg border border-border bg-surface-raised p-6">
		<h2 class="mb-1 text-base font-medium">KI-Provider</h2>
		<p class="mb-4 text-sm text-text-muted">
			Steuert, welcher Dienst Belegtexte für Struktur-Extraktion und Auto-Tagging verarbeitet.
		</p>

		{#if loading}
			<p class="text-sm text-text-muted">Wird geladen …</p>
		{:else}
			<label class="mb-4 block text-sm">
				<span class="mb-1 block text-text-muted">Anbieter</span>
				<select bind:value={provider} class="w-full rounded border border-border bg-surface p-2">
					{#each Object.entries(providerLabels) as [value, label] (value)}
						<option {value}>{label}</option>
					{/each}
				</select>
			</label>

			{#if provider !== 'ollama'}
				<div class="mb-4 rounded-lg border border-warning-border bg-warning-bg p-3 text-sm">
					⚠️ Belegtexte werden extern gesendet. Das Originalbild verlässt dein Gerät weiterhin
					nie — aber der erkannte Text geht an {providerLabels[provider]}.
				</div>

				<label class="mb-4 block text-sm">
					<span class="mb-1 block text-text-muted">
						API-Key
						{#if settings?.has_api_key}
							<span class="text-xs">(bereits hinterlegt — leer lassen, um ihn zu behalten)</span>
						{/if}
					</span>
					<input
						type="password"
						bind:value={apiKeyInput}
						placeholder={settings?.has_api_key ? '••••••••••••' : 'sk-…'}
						class="w-full rounded border border-border bg-surface p-2"
					/>
				</label>

				{#if provider === 'custom'}
					<label class="mb-4 block text-sm">
						<span class="mb-1 block text-text-muted">Endpoint-URL</span>
						<input
							type="text"
							bind:value={customEndpoint}
							placeholder="https://api.example.com/v1"
							class="w-full rounded border border-border bg-surface p-2"
						/>
					</label>
				{/if}
			{/if}

			{#if saveMessage}
				<p class="mb-3 text-sm text-accent">{saveMessage}</p>
			{/if}
			{#if errorMessage}
				<p class="mb-3 text-sm text-red-500">{errorMessage}</p>
			{/if}

			<button
				on:click={handleSave}
				disabled={saving}
				class="rounded-lg bg-accent px-4 py-2 text-sm text-accent-contrast disabled:opacity-50"
			>
				{saving ? 'Speichert …' : 'Speichern'}
			</button>
		{/if}
	</div>
{/if}
