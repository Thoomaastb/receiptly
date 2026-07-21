<script lang="ts">
	import { m } from '$lib/i18n';
	import RecoveryCodesReveal from './RecoveryCodesReveal.svelte';

	// Kontextabhängiger Einleitungstext — Settings-Seite (optionale Einrichtung) und
	// Zwangs-Gate (verpflichtende Einrichtung) formulieren das unterschiedlich.
	export let description: string;
	// Wird aufgerufen, sobald die Recovery-Codes bestätigt wurden (Einrichtung fertig).
	export let onComplete: () => void;
	// Nur gesetzt, wenn ein Abbruch erlaubt ist (Settings-Kontext) — im Zwangs-Gate wird
	// keine Prop übergeben, wodurch der Abbrechen-Button gar nicht erst gerendert wird.
	export let onCancel: (() => void) | undefined = undefined;

	type Step = 'intro' | 'qr' | 'recovery';
	let step: Step = 'intro';

	let enrollLoading = false;
	let enrollError = '';
	let secret = '';
	let qrSvg = '';
	let secretCopied = false;

	let confirmCode = '';
	let confirmSubmitting = false;
	let confirmError = '';

	let recoveryCodes: string[] = [];

	async function startEnrollment() {
		enrollError = '';
		enrollLoading = true;
		try {
			const res = await fetch('/api/auth/totp/enroll', { method: 'POST', credentials: 'include' });
			if (!res.ok) {
				const body = await res.json().catch(() => null);
				throw new Error(body?.detail ?? m.totpSetup.enrollError);
			}
			const data = await res.json();
			secret = data.secret;
			qrSvg = data.qr_svg;
			step = 'qr';
		} catch (err) {
			enrollError = err instanceof Error ? err.message : m.totpSetup.enrollError;
		} finally {
			enrollLoading = false;
		}
	}

	async function copySecret() {
		try {
			await navigator.clipboard.writeText(secret);
			secretCopied = true;
			setTimeout(() => (secretCopied = false), 2000);
		} catch {
			// Clipboard-API evtl. nicht verfügbar — Schlüssel bleibt zum manuellen Abschreiben sichtbar
		}
	}

	async function confirmEnrollment() {
		confirmError = '';
		confirmSubmitting = true;
		try {
			const res = await fetch('/api/auth/totp/confirm', {
				method: 'POST',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ code: confirmCode.trim() })
			});
			if (!res.ok) {
				const body = await res.json().catch(() => null);
				throw new Error(body?.detail ?? m.totpSetup.confirmError);
			}
			const data = await res.json();
			recoveryCodes = data.recovery_codes;
			step = 'recovery';
		} catch (err) {
			confirmError = err instanceof Error ? err.message : m.totpSetup.confirmError;
		} finally {
			confirmSubmitting = false;
		}
	}

	function handleCancel() {
		step = 'intro';
		confirmCode = '';
		confirmError = '';
		onCancel?.();
	}
</script>

{#if step === 'intro'}
	<p class="mb-4 text-sm leading-relaxed text-hifi-text-muted">{description}</p>
	{#if enrollError}
		<p class="mb-3 text-sm text-danger">{enrollError}</p>
	{/if}
	<button
		type="button"
		on:click={startEnrollment}
		disabled={enrollLoading}
		class="rounded-[10px] bg-hifi-accent px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
	>
		{enrollLoading ? m.totpSetup.startButtonLoading : m.totpSetup.startButton}
	</button>
{:else if step === 'qr'}
	<p class="mb-3 text-sm leading-relaxed text-hifi-text-muted">{description}</p>
	<p class="mb-3 text-sm text-hifi-text-muted">{m.totpSetup.qrInstructions}</p>

	<!-- QR-Codes brauchen unabhängig vom Farbschema hohen Kontrast (Scan-Zuverlässigkeit) —
	     bewusste Ausnahme von Theme-Tokens, siehe Abschlussbericht. -->
	<div class="mb-4 flex justify-center rounded-[14px] border border-hifi-border bg-white p-4">
		{@html qrSvg}
	</div>

	<div class="mb-4">
		<div class="mb-1 text-[12.5px] font-medium text-hifi-text-muted">{m.totpSetup.manualKeyLabel}</div>
		<div class="flex items-center gap-2">
			<code class="flex-1 truncate rounded-[10px] border border-hifi-border bg-hifi-bg px-3 py-2 font-mono text-sm text-hifi-text">{secret}</code>
			<button
				type="button"
				on:click={copySecret}
				class="flex-none rounded-[10px] border border-hifi-border px-3 py-2 text-[13px] font-medium text-hifi-text transition-colors hover:bg-hifi-accent-tint hover:text-hifi-accent-text"
			>
				{secretCopied ? m.totpSetup.copyKeyButtonCopied : m.totpSetup.copyKeyButton}
			</button>
		</div>
	</div>

	<form class="flex flex-col gap-3" on:submit|preventDefault={confirmEnrollment}>
		<label class="block text-sm">
			<span class="mb-1 block text-hifi-text-muted">{m.totpSetup.confirmCodeLabel}</span>
			<input
				type="text"
				bind:value={confirmCode}
				inputmode="numeric"
				autocomplete="one-time-code"
				maxlength="6"
				class="w-full rounded-[10px] border border-hifi-border bg-hifi-bg p-2.5 text-center font-mono text-lg tracking-widest"
			/>
			<span class="mt-1 block text-[12.5px] text-hifi-text-faint">{m.totpSetup.confirmCodeHint}</span>
		</label>

		{#if confirmError}
			<p class="text-sm text-danger">{confirmError}</p>
		{/if}

		<div class="flex items-center gap-2">
			<button
				type="submit"
				disabled={confirmSubmitting || confirmCode.trim().length !== 6}
				class="rounded-[10px] bg-hifi-accent px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
			>
				{confirmSubmitting ? m.totpSetup.confirmSubmitting : m.totpSetup.confirmSubmit}
			</button>
			{#if onCancel}
				<button
					type="button"
					on:click={handleCancel}
					class="rounded-[10px] px-3.5 py-2 text-sm font-medium text-hifi-text-muted transition-colors hover:text-hifi-text"
				>
					{m.totpSetup.cancelButton}
				</button>
			{/if}
		</div>
	</form>
{:else}
	<div class="mb-3 text-[13.5px] font-bold text-hifi-text">{m.totpSetup.recoveryHeading}</div>
	<RecoveryCodesReveal codes={recoveryCodes} />
	<button
		type="button"
		on:click={onComplete}
		class="mt-4 rounded-[10px] bg-hifi-accent px-4 py-2.5 text-sm font-semibold text-white"
	>
		{m.totpSetup.recoveryDoneButton}
	</button>
{/if}
