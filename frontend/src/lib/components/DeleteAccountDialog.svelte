<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { m } from '$lib/i18n';
	import { runPasskeyAssertion } from '$lib/webauthn';

	// Erstes "Tipp-Bestätigung"-Modal im Projekt (Konzept 3.3/Q11) — Modal-Chrome nach dem
	// Muster von ReauthDialog.svelte (Backdrop, role=dialog, Escape-Handling,
	// Fokus-Management). Re-Auth-Faktor-Wahl UND Tipp-Bestätigung sind bewusst EIN
	// zusammenhängendes Formular in einem einzigen Dialog (kein verschachteltes zweites
	// Modal) — daher wird ReauthDialog hier NICHT eingebettet, sondern die Faktor-Auswahl
	// direkt inline nachgebaut. Ein struktureller Grund kommt hinzu: anders als bei
	// ReauthDialog (Passwort ODER TOTP als Alternativen) verlangt der Backend-Vertrag für
	// die Löschung Passwort ODER Passkey ALS PRIMÄRFAKTOR, PLUS zusätzlich TOTP, falls der
	// User es aktiv hat (app/services/account_deletion.py::verify_active_login_factor) —
	// beide Faktoren gleichzeitig, nicht alternativ. Das passt nicht in ReauthDialogs
	// 2/3-Wege-Tab-Modell.
	export let onClose: () => void;
	export let onDeleted: () => void;
	// Best-effort vom Aufrufer übergeben (z.B. aus GET /settings/security-policy) — dieser
	// Endpoint ist aber `require_admin`-geschützt, ein normaler Haushalts-Mitglied kann also
	// serverseitig NICHT im Voraus erfahren, ob passkey_exclusive_login aktiv ist. Für
	// Nicht-Admins bleibt der Prop entsprechend `false` (unbekannt) — siehe der adaptive
	// Fallback in handleDelete() weiter unten, der auf die serverseitige Ablehnung reagiert,
	// statt sich auf eine Vorab-Kenntnis zu verlassen, die es für diese User schlicht nicht
	// geben kann, ohne das Backend zu ändern (außerhalb des Auftragsumfangs).
	export let passkeyExclusiveActive = false;

	type Method = 'password' | 'passkey';
	let method: Method = passkeyExclusiveActive ? 'passkey' : 'password';

	let loading = true;
	let loadError = '';
	let username = '';
	let totpEnabled = false;

	let passwordValue = '';
	let totpCode = '';
	let confirmationText = '';
	let submitting = false;
	let passkeySubmitting = false;
	let error = '';
	let adaptiveNote = '';
	let firstFieldEl: HTMLInputElement | HTMLButtonElement | undefined;

	$: trimmedConfirmation = confirmationText.trim();
	$: confirmationValid =
		trimmedConfirmation.length > 0 &&
		(trimmedConfirmation === username || trimmedConfirmation === 'LÖSCHEN');
	$: confirmationHint = m.accountDeletion.confirmationHint.replace('{username}', username);
	$: canSubmit =
		!submitting &&
		!passkeySubmitting &&
		confirmationValid &&
		(method === 'passkey' || !!passwordValue) &&
		(!totpEnabled || totpCode.trim().length === 6);

	async function selectMethod(next: Method) {
		if (method === next) return;
		method = next;
		error = '';
		await tick();
		firstFieldEl?.focus();
	}

	async function loadContext() {
		loading = true;
		loadError = '';
		try {
			const res = await fetch('/api/auth/me', { credentials: 'include' });
			if (!res.ok) throw new Error();
			const me: { username: string; totp_enabled: boolean } = await res.json();
			username = me.username;
			totpEnabled = me.totp_enabled;
		} catch {
			loadError = m.accountDeletion.loadError;
		} finally {
			loading = false;
			await tick();
			firstFieldEl?.focus();
		}
	}

	async function handleDelete() {
		if (!canSubmit) return;
		error = '';
		adaptiveNote = '';
		submitting = true;
		try {
			let passkeyCredential: string | undefined;
			let passkeyOptionsId: string | undefined;

			if (method === 'passkey') {
				passkeySubmitting = true;
				try {
					const result = await runPasskeyAssertion('/api/account/deletion/reauth/passkey-options');
					passkeyCredential = result.credential;
					passkeyOptionsId = result.options_id;
				} catch (err) {
					error =
						err instanceof Error && err.name === 'NotAllowedError'
							? m.accountDeletion.passkeyCancelledMessage
							: m.accountDeletion.passkeyError;
					return;
				} finally {
					passkeySubmitting = false;
				}
			}

			const res = await fetch('/api/account/deletion', {
				method: 'POST',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					current_password: method === 'password' ? passwordValue : undefined,
					passkey_credential: passkeyCredential,
					passkey_options_id: passkeyOptionsId,
					totp_code: totpEnabled ? totpCode.trim() : undefined,
					confirmation_text: trimmedConfirmation
				})
			});

			if (res.ok) {
				onDeleted();
				return;
			}

			const body = await res.json().catch(() => null);
			const detail = typeof body?.detail === 'string' ? body.detail : null;

			if (
				res.status === 400 &&
				detail === 'Passkey-Bestätigung erforderlich' &&
				method === 'password' &&
				!passkeyExclusiveActive
			) {
				// Adaptiver Fallback für den oben beschriebenen Wissens-Gap bei Nicht-Admins:
				// statt den User mit einer für ihn kontextlosen 400-Meldung allein zu lassen,
				// wechselt die UI selbstständig auf die Passkey-Methode und erklärt warum.
				method = 'passkey';
				adaptiveNote = m.accountDeletion.passwordRejectedSwitchedToPasskey;
				await tick();
				firstFieldEl?.focus();
			} else {
				error = detail ?? m.accountDeletion.genericError;
			}
		} catch {
			error = m.accountDeletion.genericError;
		} finally {
			submitting = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose();
	}

	onMount(loadContext);
</script>

<svelte:window on:keydown={handleKeydown} />

<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
<div class="fixed inset-0 z-40 bg-black opacity-50 backdrop-blur-sm" on:click={onClose} role="presentation"></div>

<div
	class="fixed left-1/2 top-1/2 z-50 max-h-[85vh] w-[92vw] max-w-sm -translate-x-1/2 -translate-y-1/2 overflow-auto rounded-[20px] border border-hifi-border bg-hifi-surface p-5"
	role="dialog"
	aria-modal="true"
	aria-labelledby="delete-account-dialog-title"
>
	<div class="mb-4 flex items-center justify-between">
		<h2 id="delete-account-dialog-title" class="text-[13.5px] font-bold text-hifi-text">
			{m.accountDeletion.dialogTitle}
		</h2>
		<button
			on:click={onClose}
			aria-label={m.accountDeletion.closeAriaLabel}
			class="rounded-full p-1 text-hifi-text-muted hover:text-hifi-text"
		>
			✕
		</button>
	</div>
	<p class="mb-4 text-sm leading-relaxed text-hifi-text-muted">{m.accountDeletion.dialogDescription}</p>

	{#if loading}
		<p class="text-sm text-hifi-text-muted">{m.common.checking}</p>
	{:else if loadError}
		<p class="text-sm text-danger">{loadError}</p>
	{:else}
		<form class="flex flex-col gap-4" on:submit|preventDefault={handleDelete}>
			<div class="flex flex-col gap-3">
				{#if !passkeyExclusiveActive}
					<div class="flex gap-1.5 rounded-[10px] border border-hifi-border p-1">
						<button
							type="button"
							on:click={() => selectMethod('password')}
							class="flex-1 rounded-[7px] px-3 py-1.5 text-[13px] font-medium transition-colors"
							class:bg-hifi-accent-tint={method === 'password'}
							class:text-hifi-accent-text={method === 'password'}
							class:text-hifi-text-muted={method !== 'password'}
						>
							{m.accountDeletion.methodPasswordLabel}
						</button>
						<button
							type="button"
							on:click={() => selectMethod('passkey')}
							class="flex-1 rounded-[7px] px-3 py-1.5 text-[13px] font-medium transition-colors"
							class:bg-hifi-accent-tint={method === 'passkey'}
							class:text-hifi-accent-text={method === 'passkey'}
							class:text-hifi-text-muted={method !== 'passkey'}
						>
							{m.accountDeletion.methodPasskeyLabel}
						</button>
					</div>
				{/if}

				{#if adaptiveNote}
					<p class="text-[12.5px] leading-relaxed text-status-warning">{adaptiveNote}</p>
				{/if}

				{#if passkeyExclusiveActive}
					<p class="text-[12.5px] leading-relaxed text-status-warning">{m.accountDeletion.passkeyOnlyNote}</p>
				{/if}

				{#if method === 'password'}
					<label class="block text-sm">
						<span class="mb-1 block text-hifi-text-muted">{m.accountDeletion.passwordFieldLabel}</span>
						<input
							type="password"
							bind:value={passwordValue}
							bind:this={firstFieldEl}
							autocomplete="current-password"
							class="w-full rounded-[10px] border border-hifi-border bg-hifi-bg p-2.5 text-sm"
						/>
					</label>
				{:else}
					<p class="text-sm text-hifi-text-muted">{m.accountDeletion.passkeyDescription}</p>
				{/if}

				{#if totpEnabled}
					<label class="block text-sm">
						<span class="mb-1 block text-hifi-text-muted">{m.accountDeletion.totpFieldLabel}</span>
						<input
							type="text"
							bind:value={totpCode}
							inputmode="numeric"
							autocomplete="one-time-code"
							maxlength="6"
							class="w-full rounded-[10px] border border-hifi-border bg-hifi-bg p-2.5 text-center font-mono text-lg tracking-widest"
						/>
					</label>
				{/if}
			</div>

			<label class="block text-sm">
				<span class="mb-1 block text-hifi-text-muted">{m.accountDeletion.confirmationLabel}</span>
				<input
					type="text"
					bind:value={confirmationText}
					autocomplete="off"
					placeholder={m.accountDeletion.confirmationPlaceholder}
					class="w-full rounded-[10px] border border-hifi-border bg-hifi-bg p-2.5 text-sm"
				/>
				<span class="mt-1 block text-[12.5px] text-hifi-text-faint">{confirmationHint}</span>
			</label>

			{#if error}
				<p class="text-sm text-danger">{error}</p>
			{/if}

			{#if method === 'password'}
				<button
					type="submit"
					disabled={!canSubmit}
					class="rounded-[10px] bg-danger px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
				>
					{submitting ? m.accountDeletion.submitButtonLoading : m.accountDeletion.submitButton}
				</button>
			{:else}
				<!-- Passkey-Methode: kein Eingabefeld zum Fokussieren (siehe ReauthDialog-
				     Kommentar) — der eigentliche Aktions-Button übernimmt sowohl den initialen
				     Fokus als auch den Klick, der die WebAuthn-Ceremony auslöst und danach
				     automatisch den Löschantrag absendet. -->
				<button
					type="button"
					bind:this={firstFieldEl}
					on:click={handleDelete}
					disabled={!canSubmit}
					class="rounded-[10px] bg-danger px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
				>
					{passkeySubmitting || submitting
						? m.accountDeletion.passkeyConfirmButtonLoading
						: m.accountDeletion.passkeyConfirmButton}
				</button>
			{/if}
		</form>
	{/if}
</div>
