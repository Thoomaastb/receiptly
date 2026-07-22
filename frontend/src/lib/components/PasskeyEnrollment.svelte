<script lang="ts">
	import { m } from '$lib/i18n';
	import {
		startRegistration,
		browserSupportsWebAuthn,
		type PublicKeyCredentialCreationOptionsJSON
	} from '@simplewebauthn/browser';
	import type { PasskeyCredentialSummary } from '$lib/webauthn';

	// Kontextabhängiger Einleitungstext — Settings-Seite (optionale, wiederholbare
	// Einrichtung) und Zwangs-Gate (verpflichtende Ersteinrichtung neuer User) formulieren
	// das unterschiedlich. Nach jeder erfolgreichen Registrierung springt die Komponente
	// zurück zu 'intro', damit ein zweiter/dritter Passkey ohne Neu-Mount hinzugefügt
	// werden kann (siehe backupHint unten).
	export let description: string;
	// Wird mit dem neu angelegten Credential aufgerufen, sobald /register/verify
	// erfolgreich war. Settings hängt es an die eigene Liste an, das Gate lädt
	// currentUser neu (/auth/me), damit passkey_setup_required auf false wechselt.
	export let onComplete: (credential: PasskeyCredentialSummary) => void;
	// Nur gesetzt, wenn Abbrechen der Namensvergabe erlaubt ist (Settings-Kontext) — im
	// Zwangs-Gate wird keine Prop übergeben, wodurch der Abbrechen-Button gar nicht erst
	// gerendert wird (gleiches Muster wie TotpEnrollment.svelte).
	export let onCancel: (() => void) | undefined = undefined;

	type Step = 'intro' | 'label' | 'unsupported';
	// Einmalig geprüft statt bei jedem Rendern — browserSupportsWebAuthn() ist eine reine
	// Capability-Prüfung (window.PublicKeyCredential), ändert sich nicht zur Laufzeit.
	let step: Step = browserSupportsWebAuthn() ? 'intro' : 'unsupported';

	let registering = false;
	let introError = '';

	// JSON-String des Registrierungsergebnisses, zwischengehalten bis der Gerätename
	// feststeht — erst dann geht er an /register/verify. Bleibt bis dahin rein
	// client-seitig, kein Backend-Aufruf nötig, um einen Abbruch in diesem Schritt
	// aufzuräumen.
	let pendingCredentialJson = '';
	let deviceLabel = '';
	let labelSubmitting = false;
	let labelError = '';

	async function startPasskeyRegistration() {
		introError = '';
		registering = true;
		try {
			const optionsRes = await fetch('/api/webauthn/register/options', {
				method: 'POST',
				credentials: 'include'
			});
			if (!optionsRes.ok) {
				throw new Error(m.passkeySetup.startError);
			}
			const { options } = await optionsRes.json();
			const optionsJSON: PublicKeyCredentialCreationOptionsJSON = JSON.parse(options);
			const credential = await startRegistration({ optionsJSON });
			pendingCredentialJson = JSON.stringify(credential);
			deviceLabel = '';
			labelError = '';
			step = 'label';
		} catch (err) {
			// NotAllowedError deckt sowohl den User-Abbruch des Browser-Dialogs als auch ein
			// Timeout ab (siehe @simplewebauthn/browser identifyRegistrationError) — beides
			// ist kein technischer Fehler, sondern eine bewusste/zeitliche Nicht-Aktion.
			if (err instanceof Error && err.name === 'NotAllowedError') {
				introError = m.passkeySetup.cancelledMessage;
			} else {
				introError = err instanceof Error && err.message ? err.message : m.passkeySetup.startError;
			}
		} finally {
			registering = false;
		}
	}

	async function submitLabel() {
		labelError = '';
		if (!deviceLabel.trim()) return;
		labelSubmitting = true;
		try {
			const res = await fetch('/api/webauthn/register/verify', {
				method: 'POST',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ credential: pendingCredentialJson, device_label: deviceLabel.trim() })
			});
			if (!res.ok) {
				if (res.status === 409) throw new Error(m.passkeySetup.conflictError);
				const body = await res.json().catch(() => null);
				throw new Error(body?.detail ?? m.passkeySetup.submitError);
			}
			const created: PasskeyCredentialSummary = await res.json();
			pendingCredentialJson = '';
			deviceLabel = '';
			step = 'intro';
			onComplete(created);
		} catch (err) {
			labelError = err instanceof Error ? err.message : m.passkeySetup.submitError;
		} finally {
			labelSubmitting = false;
		}
	}

	function handleCancelLabel() {
		step = 'intro';
		pendingCredentialJson = '';
		deviceLabel = '';
		labelError = '';
		onCancel?.();
	}
</script>

{#if step === 'unsupported'}
	<p class="mb-3 text-sm leading-relaxed text-hifi-text-muted">{description}</p>
	<p class="rounded-[10px] border border-status-warning-border bg-status-warning-bg p-3 text-sm leading-relaxed">
		{m.passkeySetup.unsupportedMessage}
	</p>
{:else if step === 'intro'}
	<p class="mb-4 text-sm leading-relaxed text-hifi-text-muted">{description}</p>
	{#if introError}
		<p class="mb-3 text-sm text-danger">{introError}</p>
	{/if}
	<button
		type="button"
		on:click={startPasskeyRegistration}
		disabled={registering}
		class="rounded-[10px] bg-hifi-accent px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
	>
		{registering ? m.passkeySetup.addButtonLoading : m.passkeySetup.addButton}
	</button>
{:else}
	<p class="mb-1 text-[13.5px] font-bold text-hifi-text">{m.passkeySetup.labelHeading}</p>
	<p class="mb-3 text-sm leading-relaxed text-hifi-text-muted">{m.passkeySetup.labelDescription}</p>

	<div class="mb-4 rounded-[10px] bg-hifi-accent-tint p-3 text-[12.5px] leading-relaxed" style="color: var(--color-accent-text-muted);">
		{m.passkeySetup.backupHint}
	</div>

	<form class="flex flex-col gap-3" on:submit|preventDefault={submitLabel}>
		<label class="block text-sm">
			<span class="mb-1 block text-hifi-text-muted">{m.passkeySetup.labelFieldLabel}</span>
			<input
				type="text"
				bind:value={deviceLabel}
				placeholder={m.passkeySetup.labelPlaceholder}
				autocomplete="off"
				class="w-full rounded-[10px] border border-hifi-border bg-hifi-bg p-2.5 text-sm"
			/>
		</label>

		{#if labelError}
			<p class="text-sm text-danger">{labelError}</p>
		{/if}

		<div class="flex items-center gap-2">
			<button
				type="submit"
				disabled={labelSubmitting || !deviceLabel.trim()}
				class="rounded-[10px] bg-hifi-accent px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
			>
				{labelSubmitting ? m.passkeySetup.submitButtonLoading : m.passkeySetup.submitButton}
			</button>
			{#if onCancel}
				<button
					type="button"
					on:click={handleCancelLabel}
					class="rounded-[10px] px-3.5 py-2 text-sm font-medium text-hifi-text-muted transition-colors hover:text-hifi-text"
				>
					{m.passkeySetup.cancelButton}
				</button>
			{/if}
		</div>
	</form>
{/if}
