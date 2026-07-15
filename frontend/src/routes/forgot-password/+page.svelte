<script lang="ts">
	let email = '';
	let submitting = false;
	let submitted = false;
	let errorMessage = '';

	async function handleSubmit() {
		errorMessage = '';
		submitting = true;
		try {
			const res = await fetch('/api/auth/password-reset/request', {
				method: 'POST',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ email: email.trim() })
			});
			if (res.ok) {
				// Backend liefert bewusst immer 204, egal ob die E-Mail bekannt ist —
				// hier daher NIE unterschiedliche Meldungen je nach Ergebnis anzeigen.
				submitted = true;
			} else {
				errorMessage = 'Anfrage fehlgeschlagen — bitte später erneut versuchen.';
			}
		} catch {
			errorMessage = 'Anfrage fehlgeschlagen — bitte später erneut versuchen.';
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

		{#if submitted}
			<div class="mb-5">
				<div class="text-lg font-bold text-hifi-text">E-Mail unterwegs</div>
				<p class="mt-2 text-sm leading-relaxed text-hifi-text-muted">
					Falls die E-Mail-Adresse bei uns registriert ist, hast du in Kürze eine Nachricht mit
					einem Link zum Zurücksetzen erhalten.
				</p>
			</div>
			<a href="/login" class="text-sm text-hifi-accent-text">Zurück zur Anmeldung</a>
		{:else}
			<div class="mb-5">
				<div class="text-lg font-bold text-hifi-text">Passwort vergessen</div>
				<p class="mt-1 text-sm text-hifi-text-muted">
					Gib deine E-Mail-Adresse ein, wir senden dir einen Link zum Zurücksetzen.
				</p>
			</div>
			<form class="flex flex-col gap-3" on:submit|preventDefault={handleSubmit}>
				<input
					type="email"
					bind:value={email}
					required
					placeholder="E-Mail"
					class="rounded-[10px] border border-hifi-border bg-hifi-bg p-2.5 text-sm"
				/>
				{#if errorMessage}
					<p class="text-sm text-danger">{errorMessage}</p>
				{/if}
				<button
					type="submit"
					disabled={submitting}
					class="mt-1 rounded-[10px] bg-hifi-accent px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
				>
					{submitting ? 'Wird gesendet …' : 'Link anfordern'}
				</button>
				<a href="/login" class="self-center text-sm text-hifi-accent-text">Zurück zur Anmeldung</a>
			</form>
		{/if}
	</div>
</div>
