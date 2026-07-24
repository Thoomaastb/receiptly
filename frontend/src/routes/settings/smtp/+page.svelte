<script lang="ts">
	import { onMount } from 'svelte';
	import { m } from '$lib/i18n';
	import CustomSelect from '$lib/components/CustomSelect.svelte';
	import SecretField from '$lib/components/SecretField.svelte';

	type Encryption = 'starttls' | 'ssl';

	interface SmtpSettings {
		host: string | null;
		port: number;
		username: string | null;
		password_set: boolean;
		from_email: string | null;
		encryption: Encryption;
		locked_by_server: boolean;
		effective_host: string | null;
	}

	interface User {
		role: string;
	}

	const ENCRYPTION_OPTIONS: { value: Encryption; label: string }[] = [
		{ value: 'starttls', label: m.smtp.encryptionStarttls },
		{ value: 'ssl', label: m.smtp.encryptionSsl }
	];

	let isAdmin = false;
	let checkingAccess = true;

	let settings: SmtpSettings | null = null;
	let loading = true;

	let hostValue = '';
	let portValue = 587;
	let usernameValue = '';
	let passwordValue = '';
	let passwordEditing = true;
	let fromEmailValue = '';
	let encryptionValue: Encryption = 'starttls';

	let saving = false;
	let saveMessage = '';
	let errorMessage = '';

	let testLoading = false;
	let testMessage = '';
	let testError = '';

	// Testmail muss auch nutzbar bleiben, wenn das Formular per locked_by_server gesperrt
	// ist (fieldset disabled) — deshalb bewusst außerhalb des fieldset platziert und an den
	// zuletzt geladenen/gespeicherten Stand gebunden, nicht an unsaved Formularwerte.
	$: hostConfigured = !!settings && (settings.locked_by_server ? !!settings.effective_host : !!settings.host);

	function applySettings(next: SmtpSettings) {
		settings = next;
		hostValue = next.host ?? '';
		portValue = next.port ?? 587;
		usernameValue = next.username ?? '';
		fromEmailValue = next.from_email ?? '';
		encryptionValue = next.encryption ?? 'starttls';
		passwordValue = '';
		passwordEditing = !next.password_set;
	}

	onMount(async () => {
		try {
			const meRes = await fetch('/api/auth/me', { credentials: 'include' });
			if (!meRes.ok) throw new Error('Nicht angemeldet');
			const me: User = await meRes.json();
			isAdmin = me.role === 'admin';
			if (!isAdmin) return;

			const res = await fetch('/api/settings/smtp', { credentials: 'include' });
			if (!res.ok) throw new Error(`${m.smtp.loadError} (${res.status})`);
			applySettings(await res.json());
		} catch (err) {
			errorMessage = err instanceof Error ? err.message : m.smtp.loadError;
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
			const body: Record<string, unknown> = {
				host: hostValue.trim(),
				port: portValue,
				username: usernameValue.trim() ? usernameValue.trim() : null,
				from_email: fromEmailValue.trim(),
				encryption: encryptionValue
			};
			if (passwordEditing && passwordValue.trim()) {
				body.password = passwordValue.trim();
			}

			const res = await fetch('/api/settings/smtp', {
				method: 'PUT',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(body)
			});
			if (!res.ok) {
				const errBody = await res.json().catch(() => null);
				throw new Error(errBody?.detail ?? `${m.smtp.saveError} (${res.status})`);
			}

			applySettings(await res.json());
			saveMessage = m.smtp.saveSuccess;
		} catch (err) {
			errorMessage = err instanceof Error ? err.message : m.smtp.saveError;
		} finally {
			saving = false;
		}
	}

	async function handleTestEmail() {
		testLoading = true;
		testMessage = '';
		testError = '';
		try {
			const res = await fetch('/api/settings/smtp/test-email', {
				method: 'POST',
				credentials: 'include'
			});
			if (res.status !== 204) {
				const body = await res.json().catch(() => null);
				throw new Error(body?.detail ?? `${m.smtp.testError} (${res.status})`);
			}
			testMessage = m.smtp.testSuccess;
		} catch (err) {
			testError = err instanceof Error ? err.message : m.smtp.testError;
		} finally {
			testLoading = false;
		}
	}
</script>

{#if checkingAccess}
	<p class="text-sm text-hifi-text-muted">{m.common.checking}</p>
{:else if !isAdmin}
	<p class="text-sm text-hifi-text-muted">{m.smtp.accessDenied}</p>
{:else}
	<div class="grid max-w-4xl grid-cols-1 gap-6 lg:grid-cols-2 lg:items-start">
		<div class="rounded-[14px] border border-hifi-border bg-hifi-surface p-6">
			<h2 class="mb-1 text-[13.5px] font-bold text-hifi-text">{m.smtp.cardTitle}</h2>
			<p class="mb-4 text-sm text-hifi-text-muted">{m.smtp.cardDescription}</p>

			{#if loading}
				<p class="text-sm text-hifi-text-muted">Wird geladen …</p>
			{:else}
				{#if settings?.locked_by_server}
					<div class="mb-4 rounded-[14px] border border-status-warning-border bg-status-warning-bg p-3 text-sm">
						{m.smtp.lockedBannerPrefix} {settings.effective_host}
					</div>
				{/if}

				<fieldset disabled={!!settings?.locked_by_server} class="contents">
					<label class="mb-4 block text-sm">
						<span class="mb-1 block text-hifi-text-muted">{m.smtp.hostLabel}</span>
						<input
							type="text"
							bind:value={hostValue}
							placeholder="smtp.example.com"
							class="w-full rounded border border-hifi-border bg-hifi-surface p-2 disabled:opacity-50"
						/>
					</label>

					<label class="mb-4 block text-sm">
						<span class="mb-1 block text-hifi-text-muted">{m.smtp.portLabel}</span>
						<input
							type="number"
							bind:value={portValue}
							min="1"
							max="65535"
							class="w-full rounded border border-hifi-border bg-hifi-surface p-2 disabled:opacity-50"
						/>
					</label>

					<label class="mb-4 block text-sm">
						<span class="mb-1 block text-hifi-text-muted">{m.smtp.usernameLabel}</span>
						<input
							type="text"
							bind:value={usernameValue}
							class="w-full rounded border border-hifi-border bg-hifi-surface p-2 disabled:opacity-50"
						/>
					</label>

					<div class="mb-4">
						<span id="smtp-password-label" class="mb-1 block text-sm text-hifi-text-muted">
							{m.smtp.passwordLabel}
							{#if settings?.password_set}
								<span class="text-xs">({m.smtp.passwordSetHint})</span>
							{/if}
						</span>
						<SecretField
							isSet={!!settings?.password_set}
							bind:value={passwordValue}
							bind:editing={passwordEditing}
							disabled={!!settings?.locked_by_server}
							labelledBy="smtp-password-label"
							autocomplete="new-password"
							changeButtonLabel={m.smtp.passwordChangeButton}
							changeButtonAriaLabel={m.smtp.passwordChangeAriaLabel}
							cancelButtonLabel={m.smtp.passwordCancelButton}
						/>
					</div>

					<label class="mb-4 block text-sm">
						<span class="mb-1 block text-hifi-text-muted">{m.smtp.fromEmailLabel}</span>
						<input
							type="email"
							bind:value={fromEmailValue}
							placeholder="noreply@example.com"
							class="w-full rounded border border-hifi-border bg-hifi-surface p-2 disabled:opacity-50"
						/>
					</label>

					<div class="mb-4">
						<span id="smtp-encryption-label" class="mb-1 block text-sm text-hifi-text-muted">
							{m.smtp.encryptionLabel}
						</span>
						<CustomSelect
							bind:value={encryptionValue}
							disabled={!!settings?.locked_by_server}
							labelledBy="smtp-encryption-label"
							options={ENCRYPTION_OPTIONS}
						/>
					</div>
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
						{saving ? m.smtp.saveButtonSaving : m.smtp.saveButton}
					</button>
				{/if}
			{/if}
		</div>

		{#if !loading}
			<div class="rounded-[14px] border border-hifi-border bg-hifi-surface p-6">
				<h2 class="mb-1 text-[13.5px] font-bold text-hifi-text">{m.smtp.testCardTitle}</h2>
				<p class="mb-4 text-sm text-hifi-text-muted">{m.smtp.testCardDescription}</p>

				{#if testMessage}
					<p class="mb-3 text-sm text-hifi-accent-text">{testMessage}</p>
				{/if}
				{#if testError}
					<p class="mb-3 text-sm text-danger">{testError}</p>
				{/if}

				<button
					type="button"
					on:click={handleTestEmail}
					disabled={!hostConfigured || testLoading}
					class="rounded-[10px] border border-hifi-border px-3.5 py-2 text-[13px] font-medium text-hifi-text transition-colors hover:bg-hifi-accent-tint hover:text-hifi-accent-text disabled:opacity-50"
				>
					{testLoading ? m.smtp.testButtonSending : m.smtp.testButton}
				</button>

				{#if !hostConfigured}
					<p class="mt-2 text-[12.5px] text-hifi-text-faint">{m.smtp.testUnavailableHint}</p>
				{/if}
			</div>
		{/if}
	</div>
{/if}
