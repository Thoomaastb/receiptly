<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';

	let mode: 'checking' | 'login' | 'setup' = 'checking';

	let username = '';
	let password = '';

	let householdName = '';
	let setupUsername = '';
	let setupEmail = '';
	let setupPassword = '';

	let errorMessage = '';
	let submitting = false;

	onMount(async () => {
		try {
			const meRes = await fetch('/api/auth/me', { credentials: 'include' });
			if (meRes.ok) {
				goto('/');
				return;
			}
		} catch {
			// Backend nicht erreichbar — Login-Formular trotzdem zeigen, statt hier zu blockieren
		}

		try {
			const res = await fetch('/api/auth/setup-required', { credentials: 'include' });
			const body = res.ok ? await res.json() : { setup_required: false };
			mode = body.setup_required ? 'setup' : 'login';
		} catch {
			mode = 'login';
		}
	});

	async function handleLogin() {
		errorMessage = '';
		submitting = true;
		try {
			const res = await fetch('/api/auth/login', {
				method: 'POST',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ username, password })
			});
			if (res.ok) {
				goto('/');
			} else {
				const body = await res.json().catch(() => null);
				errorMessage = body?.detail ?? 'Anmeldung fehlgeschlagen.';
			}
		} finally {
			submitting = false;
		}
	}

	async function handleSetup() {
		errorMessage = '';
		if (
			!householdName.trim() ||
			!setupUsername.trim() ||
			!setupEmail.trim() ||
			setupPassword.length < 8
		) {
			errorMessage = 'Bitte alle Felder ausfüllen (Passwort mind. 8 Zeichen).';
			return;
		}
		submitting = true;
		try {
			const res = await fetch('/api/auth/register', {
				method: 'POST',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					household_name: householdName.trim(),
					username: setupUsername.trim(),
					email: setupEmail.trim(),
					password: setupPassword
				})
			});
			if (res.ok) {
				goto('/');
			} else {
				const body = await res.json().catch(() => null);
				errorMessage = body?.detail ?? 'Einrichtung fehlgeschlagen.';
			}
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

		{#if mode === 'checking'}
			<p class="text-sm text-hifi-text-muted">Wird geladen …</p>
		{:else if mode === 'setup'}
			<div class="mb-5">
				<div class="text-lg font-bold text-hifi-text">Haushalt einrichten</div>
				<p class="mt-1 text-sm text-hifi-text-muted">
					Noch kein Account vorhanden — lege den ersten (Admin) an.
				</p>
			</div>
			<form class="flex flex-col gap-3" on:submit|preventDefault={handleSetup}>
				<input
					type="text"
					bind:value={householdName}
					placeholder="Haushaltsname (z. B. Familie Müller)"
					class="rounded-[10px] border border-hifi-border bg-hifi-bg p-2.5 text-sm"
				/>
				<input
					type="text"
					bind:value={setupUsername}
					placeholder="Benutzername"
					class="rounded-[10px] border border-hifi-border bg-hifi-bg p-2.5 text-sm"
				/>
				<input
					type="email"
					bind:value={setupEmail}
					placeholder="E-Mail"
					class="rounded-[10px] border border-hifi-border bg-hifi-bg p-2.5 text-sm"
				/>
				<input
					type="password"
					bind:value={setupPassword}
					placeholder="Passwort (mind. 8 Zeichen)"
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
					{submitting ? 'Wird eingerichtet …' : 'Haushalt anlegen'}
				</button>
			</form>
		{:else}
			<div class="mb-5">
				<div class="text-lg font-bold text-hifi-text">Anmelden</div>
			</div>
			<form class="flex flex-col gap-3" on:submit|preventDefault={handleLogin}>
				<input
					type="text"
					bind:value={username}
					placeholder="Benutzername"
					class="rounded-[10px] border border-hifi-border bg-hifi-bg p-2.5 text-sm"
				/>
				<input
					type="password"
					bind:value={password}
					placeholder="Passwort"
					class="rounded-[10px] border border-hifi-border bg-hifi-bg p-2.5 text-sm"
				/>
				<a href="/forgot-password" class="self-end text-sm text-hifi-accent-text">
					Passwort vergessen?
				</a>
				{#if errorMessage}
					<p class="text-sm text-danger">{errorMessage}</p>
				{/if}
				<button
					type="submit"
					disabled={submitting}
					class="mt-1 rounded-[10px] bg-hifi-accent px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
				>
					{submitting ? 'Wird angemeldet …' : 'Anmelden'}
				</button>
			</form>
		{/if}
	</div>
</div>
