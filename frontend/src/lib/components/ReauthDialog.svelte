<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { m } from '$lib/i18n';

	type ReauthPayload = { current_password: string } | { code: string };
	type ReauthResult = { ok: true; data?: unknown } | { ok: false; error: string };

	// Wiederverwendbar für "TOTP deaktivieren" und "Recovery-Codes neu generieren" — der
	// eigentliche API-Aufruf (unterschiedlicher Endpoint je Aufrufer) liegt beim Aufrufer,
	// dieser Dialog kümmert sich nur um Methode-Wahl, Eingabe, Lade-/Fehlerzustand.
	export let title: string;
	export let description: string;
	export let submitLabel: string;
	export let onSubmit: (payload: ReauthPayload) => Promise<ReauthResult>;
	export let onClose: () => void;
	export let onSuccess: (data: unknown) => void;

	type Method = 'password' | 'totp';
	let method: Method = 'password';
	let passwordValue = '';
	let codeValue = '';
	let submitting = false;
	let error = '';
	let firstFieldEl: HTMLInputElement | undefined;

	async function selectMethod(next: Method) {
		if (method === next) return;
		method = next;
		error = '';
		await tick();
		firstFieldEl?.focus();
	}

	async function handleSubmit() {
		error = '';
		const payload: ReauthPayload =
			method === 'password' ? { current_password: passwordValue } : { code: codeValue.trim() };
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
		{:else}
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
		{/if}

		{#if error}
			<p class="text-sm text-danger">{error}</p>
		{/if}

		<button
			type="submit"
			disabled={submitting || (method === 'password' ? !passwordValue : codeValue.trim().length !== 6)}
			class="mt-1 rounded-[10px] bg-hifi-accent px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
		>
			{submitting ? m.reauth.submitting : submitLabel}
		</button>
	</form>
</div>
