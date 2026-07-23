<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { m } from '$lib/i18n';
	import { runPasskeyAssertion } from '$lib/webauthn';
	import type { ReauthPayload, ReauthResult } from '$lib/reauth';

	// Wiederverwendbar für "TOTP deaktivieren" und "Recovery-Codes neu generieren" — der
	// eigentliche API-Aufruf (unterschiedlicher Endpoint je Aufrufer) liegt beim Aufrufer,
	// dieser Dialog kümmert sich nur um Methode-Wahl, Eingabe, Lade-/Fehlerzustand.
	export let title: string;
	export let description: string;
	export let submitLabel: string;
	export let onSubmit: (payload: ReauthPayload) => Promise<ReauthResult>;
	export let onClose: () => void;
	export let onSuccess: (data: unknown) => void;

	// v0.36.0 (Konto-Löschung): Passkey als dritte Re-Auth-Methode. allowPasskey steuert, ob
	// der dritte Tab überhaupt sichtbar ist (Aufrufer weiß, ob Passkey als Faktor sinnvoll
	// ist). forcePasskeyOnly ist eine bewusste UX-Entscheidung für den Fall, dass der
	// haushaltsweite Passkey-exklusive Login aktiv ist: dann ist "Passwort" gar kein gültiger
	// Faktor mehr (das Backend würde es ohnehin ablehnen) — der Passwort-Tab wird in diesem
	// Fall komplett ausgeblendet statt einen dritten Tab nur zusätzlich anzubieten, damit der
	// Nutzer nicht erst eine Methode probiert, die serverseitig gar nicht akzeptiert wird.
	export let allowPasskey = false;
	export let forcePasskeyOnly = false;

	type Method = 'password' | 'totp' | 'passkey';
	let method: Method = forcePasskeyOnly ? 'passkey' : 'password';
	let passwordValue = '';
	let codeValue = '';
	let submitting = false;
	let passkeySubmitting = false;
	let error = '';
	// Für Passwort/TOTP das jeweilige Eingabefeld, für Passkey der Bestätigen-Button — es
	// gibt bei der Passkey-Methode kein Eingabefeld, das fokussiert werden müsste, daher hier
	// bewusst auf das nächstsinnvolle interaktive Element erweitert statt den Fokus dort
	// einfach ausfallen zu lassen.
	let firstFieldEl: HTMLInputElement | HTMLButtonElement | undefined;

	async function selectMethod(next: Method) {
		if (method === next) return;
		method = next;
		error = '';
		await tick();
		firstFieldEl?.focus();
	}

	async function submitPayload(payload: ReauthPayload) {
		error = '';
		submitting = true;
		try {
			const result = await onSubmit(payload);
			if (result.ok) {
				onSuccess(result.data);
				onClose();
			} else {
				error = result.error;
			}
		} finally {
			submitting = false;
		}
	}

	async function handleSubmit() {
		const payload: ReauthPayload =
			method === 'password' ? { current_password: passwordValue } : { code: codeValue.trim() };
		await submitPayload(payload);
	}

	async function handlePasskeyConfirm() {
		error = '';
		passkeySubmitting = true;
		try {
			const { credential, options_id } = await runPasskeyAssertion(
				'/api/account/deletion/reauth/passkey-options'
			);
			await submitPayload({ passkey_credential: credential, passkey_options_id: options_id });
		} catch (err) {
			// NotAllowedError (User bricht die Browser-Ceremony ab) bleibt bewusst
			// aufrufer-spezifisch behandelt — hier, weil dieser Dialog der einzige Aufrufer
			// der Passkey-Methode ist (anders als beim Login gibt es keinen zweiten Kontext).
			error =
				err instanceof Error && err.name === 'NotAllowedError'
					? m.reauth.passkeyCancelledMessage
					: m.reauth.passkeyError;
		} finally {
			passkeySubmitting = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose();
	}

	onMount(() => {
		firstFieldEl?.focus();
	});
</script>

<svelte:window on:keydown={handleKeydown} />

<!-- Gleiches Dialog-Grundmuster wie UploadModal.svelte (Backdrop + role=dialog,
     Escape/Click-outside-to-close) — hier zusätzlich mit initialem Fokus und
     Fokus-Nachführung beim Methodenwechsel, da es sich um einen sicherheitskritischen
     Re-Auth-Flow handelt. -->
<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
<div class="fixed inset-0 z-40 bg-black opacity-50 backdrop-blur-sm" on:click={onClose} role="presentation"></div>

<div
	class="fixed left-1/2 top-1/2 z-50 w-[92vw] max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-[20px] border border-hifi-border bg-hifi-surface p-5"
	role="dialog"
	aria-modal="true"
	aria-labelledby="reauth-dialog-title"
>
	<div class="mb-4 flex items-center justify-between">
		<h2 id="reauth-dialog-title" class="text-[13.5px] font-bold text-hifi-text">{title}</h2>
		<button on:click={onClose} aria-label={m.reauth.closeAriaLabel} class="rounded-full p-1 text-hifi-text-muted hover:text-hifi-text">
			✕
		</button>
	</div>
	<p class="mb-4 text-sm leading-relaxed text-hifi-text-muted">{description}</p>

	<div class="mb-4 flex gap-1.5 rounded-[10px] border border-hifi-border p-1">
		{#if !forcePasskeyOnly}
			<button
				type="button"
				on:click={() => selectMethod('password')}
				class="flex-1 rounded-[7px] px-3 py-1.5 text-[13px] font-medium transition-colors"
				class:bg-hifi-accent-tint={method === 'password'}
				class:text-hifi-accent-text={method === 'password'}
				class:text-hifi-text-muted={method !== 'password'}
			>
				{m.reauth.methodPasswordLabel}
			</button>
		{/if}
		<button
			type="button"
			on:click={() => selectMethod('totp')}
			class="flex-1 rounded-[7px] px-3 py-1.5 text-[13px] font-medium transition-colors"
			class:bg-hifi-accent-tint={method === 'totp'}
			class:text-hifi-accent-text={method === 'totp'}
			class:text-hifi-text-muted={method !== 'totp'}
		>
			{m.reauth.methodTotpLabel}
		</button>
		{#if allowPasskey || forcePasskeyOnly}
			<button
				type="button"
				on:click={() => selectMethod('passkey')}
				class="flex-1 rounded-[7px] px-3 py-1.5 text-[13px] font-medium transition-colors"
				class:bg-hifi-accent-tint={method === 'passkey'}
				class:text-hifi-accent-text={method === 'passkey'}
				class:text-hifi-text-muted={method !== 'passkey'}
			>
				{m.reauth.methodPasskeyLabel}
			</button>
		{/if}
	</div>

	<form class="flex flex-col gap-3" on:submit|preventDefault={handleSubmit}>
		{#if method === 'password'}
			<label class="block text-sm">
				<span class="mb-1 block text-hifi-text-muted">{m.reauth.passwordFieldLabel}</span>
				<input
					type="password"
					bind:value={passwordValue}
					bind:this={firstFieldEl}
					autocomplete="current-password"
					class="w-full rounded-[10px] border border-hifi-border bg-hifi-bg p-2.5 text-sm"
				/>
			</label>
		{:else if method === 'totp'}
			<label class="block text-sm">
				<span class="mb-1 block text-hifi-text-muted">{m.reauth.codeFieldLabel}</span>
				<input
					type="text"
					bind:value={codeValue}
					bind:this={firstFieldEl}
					inputmode="numeric"
					autocomplete="one-time-code"
					maxlength="6"
					class="w-full rounded-[10px] border border-hifi-border bg-hifi-bg p-2.5 text-center font-mono text-lg tracking-widest"
				/>
			</label>
		{:else}
			<p class="text-sm text-hifi-text-muted">{m.reauth.passkeyDescription}</p>
		{/if}

		{#if error}
			<p class="text-sm text-danger">{error}</p>
		{/if}

		{#if method === 'passkey'}
			<button
				type="button"
				bind:this={firstFieldEl}
				on:click={handlePasskeyConfirm}
				disabled={passkeySubmitting}
				class="mt-1 rounded-[10px] bg-hifi-accent px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
			>
				{passkeySubmitting ? m.reauth.submitting : m.reauth.passkeyConfirmButton}
			</button>
		{:else}
			<button
				type="submit"
				disabled={submitting || (method === 'password' ? !passwordValue : codeValue.trim().length !== 6)}
				class="mt-1 rounded-[10px] bg-hifi-accent px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
			>
				{submitting ? m.reauth.submitting : submitLabel}
			</button>
		{/if}
	</form>
</div>
