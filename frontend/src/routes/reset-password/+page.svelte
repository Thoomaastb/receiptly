<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';

	$: token = $page.url.searchParams.get('token');

	let newPassword = '';
	let confirmPassword = '';
	let validationError = '';
	let requestError = '';
	let submitting = false;
	let success = false;

	function validate(): boolean {
		if (newPassword.length < 8) {
			validationError = 'Das Passwort muss mind. 8 Zeichen lang sein.';
			return false;
		}
		if (newPassword !== confirmPassword) {
			validationError = 'Die Passwörter stimmen nicht überein.';
			return false;
		}
		validationError = '';
		return true;
	}

	async function handleSubmit() {
		requestError = '';
		if (!validate() || !token) return;

		submitting = true;
		try {
			const res = await fetch('/api/auth/password-reset/confirm', {
				method: 'POST',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ token, new_password: newPassword })
			});
			if (res.ok) {
				success = true;
				setTimeout(() => goto('/login'), 1500);
			} else if (res.status === 400) {
				const body = await res.json().catch(() => null);
				requestError = body?.detail ?? 'Link ungültig oder abgelaufen — bitte neu anfordern.';
			} else {
				requestError = 'Zurücksetzen fehlgeschlagen — bitte später erneut versuchen.';
			}
		} catch {
			requestError = 'Zurücksetzen fehlgeschlagen — bitte später erneut versuchen.';
		} finally {
			submitting = false;
		}
	}
</script>

<div class="flex min-h-screen items-center justify-center bg-hifi-bg px-4">
	<div class="w-full max-w-sm rounded-2xl border border-hifi-border bg-hifi-surface p-8">
		<div class="mb-6 flex items-center gap-3">
			<span class="flex h-9 w-9 flex-none items-center justify-center rounded-[10px] bg-hifi-accent">
				<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<path d="M6 3h9l3 3v15H6z" />
					<path d="M9 9h6M9 13h6M9 17h3" />
				</svg>
			</span>
			<span class="text-[19px] font-extrabold tracking-tight text-hifi-text">receiptly</span>
		</div>

		{#if !token}
			<div class="mb-5">
				<div class="text-lg font-bold text-hifi-text">Link unvollständig</div>
				<p class="mt-2 text-sm leading-relaxed text-hifi-text-muted">
					Dieser Link enthält kein gültiges Reset-Token. Bitte fordere einen neuen Link an.
				</p>
			</div>
			<a href="/forgot-password" class="text-sm text-hifi-accent-text">Neuen Link anfordern</a>
		{:else if success}
			<div class="mb-5">
				<div class="text-lg font-bold text-hifi-text">Passwort geändert</div>
				<p class="mt-2 text-sm leading-relaxed text-hifi-text-muted">
					Dein Passwort wurde erfolgreich zurückgesetzt. Du wirst zur Anmeldung weitergeleitet …
				</p>
			</div>
		{:else}
			<div class="mb-5">
				<div class="text-lg font-bold text-hifi-text">Neues Passwort festlegen</div>
			</div>
			<form class="flex flex-col gap-3" on:submit|preventDefault={handleSubmit}>
				<input
					type="password"
					bind:value={newPassword}
					placeholder="Neues Passwort (mind. 8 Zeichen)"
					class="rounded-[10px] border border-hifi-border bg-hifi-bg p-2.5 text-sm"
				/>
				<input
					type="password"
					bind:value={confirmPassword}
					placeholder="Passwort wiederholen"
					class="rounded-[10px] border border-hifi-border bg-hifi-bg p-2.5 text-sm"
				/>
				{#if validationError}
					<p class="text-sm text-danger">{validationError}</p>
				{/if}
				{#if requestError}
					<p class="text-sm text-danger">{requestError}</p>
					<a href="/forgot-password" class="text-sm text-hifi-accent-text">Neuen Link anfordern</a>
				{/if}
				<button
					type="submit"
					disabled={submitting}
					class="mt-1 rounded-[10px] bg-hifi-accent px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
				>
					{submitting ? 'Wird gespeichert …' : 'Passwort zurücksetzen'}
				</button>
			</form>
		{/if}
	</div>
</div>
