<script lang="ts">
	import { onMount } from 'svelte';
	import CustomSelect from '$lib/components/CustomSelect.svelte';

	interface AISettings {
		provider: string | null;
		has_api_key: boolean;
		endpoint_url: string | null;
		model_name: string | null;
		locked_by_server: boolean;
		effective_provider: string | null;
		effective_model: string | null;
	}

	interface User {
		role: string;
	}

	let isAdmin = false;
	let checkingAccess = true;

	let settings: AISettings | null = null;
	let provider = 'ollama';
	let apiKeyInput = '';
	let endpointUrl = '';
	let modelName = '';
	let loading = true;
	let saving = false;
	let saveMessage = '';
	let errorMessage = '';

	const providerLabels: Record<string, string> = {
		ollama: 'Ollama / Lokal',
		openai: 'OpenAI',
		anthropic: 'Anthropic',
		google: 'Google'
	};

	// Nur Platzhalter für das optionale Modell-Feld — der tatsächliche Default bei leerem
	// Feld wird serverseitig festgelegt (siehe ai_provider_client.py).
	const modelPlaceholders: Record<string, string> = {
		ollama: 'llama3.1',
		openai: 'gpt-4o-mini',
		anthropic: 'claude-3-5-haiku',
		google: 'gemini-2.5-flash'
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
			provider = settings!.provider ?? 'ollama';
			endpointUrl = settings!.endpoint_url ?? '';
			modelName = settings!.model_name ?? '';
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
			if (provider === 'ollama') {
				body.endpoint_url = endpointUrl.trim();
			}
			if (modelName.trim()) body.model_name = modelName.trim();

			const res = await fetch('/api/settings/ai-provider', {
				method: 'PUT',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(body)
			});
			if (!res.ok) {
				const errBody = await res.json().catch(() => null);
				throw new Error(errBody?.detail ?? `Speichern fehlgeschlagen (${res.status})`);
			}

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

<h1 class="mb-6 text-[26px] font-extrabold tracking-tight text-hifi-text">Einstellungen</h1>

{#if checkingAccess}
	<p class="text-sm text-hifi-text-muted">Wird geprüft …</p>
{:else if !isAdmin}
	<p class="text-sm text-hifi-text-muted">Diese Einstellungen sind nur für Admins sichtbar.</p>
{:else}
	<div class="max-w-lg rounded-[14px] border border-hifi-border bg-hifi-surface p-6">
		<h2 class="mb-1 text-[13.5px] font-bold text-hifi-text">KI-Provider</h2>
		<p class="mb-4 text-sm text-hifi-text-muted">
			Steuert, welcher Dienst Belegtexte für Struktur-Extraktion und Auto-Tagging verarbeitet.
		</p>

		{#if loading}
			<p class="text-sm text-hifi-text-muted">Wird geladen …</p>
		{:else}
			{#if settings?.locked_by_server}
				<div class="mb-4 rounded-[14px] border border-warning-border bg-warning-bg p-3 text-sm">
					Der KI-Anbieter ist serverseitig fest konfiguriert: {providerLabels[settings.effective_provider ?? ''] ?? settings.effective_provider}{#if settings.effective_model}
						· {settings.effective_model}{/if}
				</div>
			{/if}

			<fieldset disabled={!!settings?.locked_by_server} class="contents">
				<div class="mb-4">
					<span id="provider-select-label" class="mb-1 block text-sm text-hifi-text-muted">Anbieter</span>
					<CustomSelect
						bind:value={provider}
						disabled={!!settings?.locked_by_server}
						labelledBy="provider-select-label"
						options={Object.entries(providerLabels).map(([value, label]) => ({ value, label }))}
					/>
				</div>

				{#if provider === 'ollama'}
					<label class="mb-4 block text-sm">
						<span class="mb-1 block text-hifi-text-muted">Host</span>
						<input
							type="text"
							bind:value={endpointUrl}
							placeholder="http://ollama:11434"
							class="w-full rounded border border-hifi-border bg-hifi-surface p-2 disabled:opacity-50"
						/>
					</label>
					<label class="mb-4 block text-sm">
						<span class="mb-1 block text-hifi-text-muted">Modell</span>
						<input
							type="text"
							bind:value={modelName}
							placeholder={modelPlaceholders.ollama}
							class="w-full rounded border border-hifi-border bg-hifi-surface p-2 disabled:opacity-50"
						/>
					</label>
				{:else}
					<div class="mb-4 rounded-[14px] border border-warning-border bg-warning-bg p-3 text-sm">
						⚠️ Belegtexte werden extern gesendet. Das Originalbild verlässt dein Gerät weiterhin
						nie — aber der erkannte Text geht an {providerLabels[provider]}.
					</div>

					<label class="mb-4 block text-sm">
						<span class="mb-1 block text-hifi-text-muted">
							API-Key
							{#if settings?.has_api_key}
								<span class="text-xs">(bereits hinterlegt — leer lassen, um ihn zu behalten)</span>
							{/if}
						</span>
						<input
							type="password"
							bind:value={apiKeyInput}
							placeholder={settings?.has_api_key ? '••••••••••••' : 'sk-…'}
							class="w-full rounded border border-hifi-border bg-hifi-surface p-2 disabled:opacity-50"
						/>
					</label>

					<label class="mb-4 block text-sm">
						<span class="mb-1 block text-hifi-text-muted">Modell (optional)</span>
						<input
							type="text"
							bind:value={modelName}
							placeholder={modelPlaceholders[provider]}
							class="w-full rounded border border-hifi-border bg-hifi-surface p-2 disabled:opacity-50"
						/>
					</label>
				{/if}
			</fieldset>

			{#if saveMessage}
				<p class="mb-3 text-sm text-hifi-accent-text">{saveMessage}</p>
			{/if}
			{#if errorMessage}
				<p class="mb-3 text-sm text-danger">{errorMessage}</p>
			{/if}

			{#if !settings?.locked_by_server}
				<button
					on:click={handleSave}
					disabled={saving}
					class="rounded-[10px] bg-hifi-accent px-4 py-2 text-sm text-white disabled:opacity-50"
				>
					{saving ? 'Speichert …' : 'Speichern'}
				</button>
			{/if}
		{/if}
	</div>
{/if}
