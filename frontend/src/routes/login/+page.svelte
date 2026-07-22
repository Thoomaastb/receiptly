<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { m } from '$lib/i18n';
	import {
		startAuthentication,
		browserSupportsWebAuthn,
		type PublicKeyCredentialRequestOptionsJSON
	} from '@simplewebauthn/browser';

	let mode: 'checking' | 'login' | 'setup' | 'totp' = 'checking';

	let username = '';
	let password = '';

	let householdName = '';
	let setupUsername = '';
	let setupEmail = '';
	let setupPassword = '';

	let errorMessage = '';
	let submitting = false;

	// Passkey-Login (Baustein 2, Phase 3) — Alternative zum Passwort, nutzt dasselbe
	// Username/E-Mail-Feld. Capability-Check einmalig, keine Laufzeitänderung möglich.
	const passkeySupported = browserSupportsWebAuthn();
	let passkeyError = '';
	let passkeySubmitting = false;

	// Zweiter Login-Schritt (Phase 2: TOTP/2FA) — das Pre-Auth-Cookie hält den Zustand
	// serverseitig, hier wird nur der Code abgefragt.
	let totpCode = '';
	let totpError = '';
	let totpSubmitting = false;

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

	// Gemeinsame Auswertung für Passwort- UND Passkey-Login — beide Endpunkte liefern laut
	// API-Vertrag exakt dieselbe Antwortform (volle UserResponse oder {requires_totp: true}),
	// der bestehende TOTP-Zweitschritt wird für beide Wege unverändert wiederverwendet.
	function handleAuthSuccessBody(body: { requires_totp?: boolean } | null) {
		if (body?.requires_totp) {
			totpCode = '';
			totpError = '';
			mode = 'totp';
		} else {
			goto('/');
		}
	}

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
				handleAuthSuccessBody(await res.json().catch(() => null));
			} else {
				const body = await res.json().catch(() => null);
				errorMessage = body?.detail ?? 'Anmeldung fehlgeschlagen.';
			}
		} finally {
			submitting = false;
		}
	}

	async function handlePasskeyLogin() {
		errorMessage = '';
		passkeyError = '';
		if (!username.trim()) {
			passkeyError = m.passkeyLogin.usernameRequired;
			return;
		}
		passkeySubmitting = true;
		try {
			const optionsRes = await fetch('/api/webauthn/authenticate/options', {
				method: 'POST',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ username: username.trim() })
			});
			// Bewusst generische Fehlermeldung bei jedem Fehlschlag ab hier (kein
			// body?.detail-Auslesen) — laut API-Vertrag darf ein unbekannter Username nicht
			// von einem falschen/abgelaufenen Passkey unterscheidbar sein.
			if (!optionsRes.ok) throw new Error(m.passkeyLogin.genericError);
			const { options, options_id } = await optionsRes.json();
			const optionsJSON: PublicKeyCredentialRequestOptionsJSON = JSON.parse(options);
			const credential = await startAuthentication({ optionsJSON });

			const verifyRes = await fetch('/api/webauthn/authenticate/verify', {
				method: 'POST',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ options_id, credential: JSON.stringify(credential) })
			});
			if (!verifyRes.ok) throw new Error(m.passkeyLogin.genericError);
			handleAuthSuccessBody(await verifyRes.json().catch(() => null));
		} catch (err) {
			if (err instanceof Error && err.name === 'NotAllowedError') {
				passkeyError = m.passkeyLogin.cancelledMessage;
			} else {
				passkeyError = err instanceof Error && err.message ? err.message : m.passkeyLogin.genericError;
			}
		} finally {
			passkeySubmitting = false;
		}
	}

	async function handleTotpSubmit() {
		totpError = '';
		totpSubmitting = true;
		try {
			const res = await fetch('/api/auth/login/totp', {
				method: 'POST',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ code: totpCode.trim() })
			});
			if (res.ok) {
				goto('/');
				return;
			}
			const body = await res.json().catch(() => null);
			if (res.status === 401) {
				// Pending-2FA-Zustand verworfen (zu viele Fehlversuche oder abgelaufen) —
				// zurück zu Schritt 1, Passwort muss erneut eingegeben werden.
				mode = 'login';
				password = '';
				totpCode = '';
				errorMessage = body?.detail ?? m.auth.totpStep.errorExpired;
			} else {
				totpError = body?.detail ?? m.auth.totpStep.errorInvalidCode;
			}
		} catch {
			totpError = m.auth.totpStep.genericError;
		} finally {
			totpSubmitting = false;
		}
	}

	function cancelTotp() {
		mode = 'login';
		totpCode = '';
		totpError = '';
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
		{:else if mode === 'totp'}
			<div class="mb-5">
				<div class="text-lg font-bold text-hifi-text">{m.auth.totpStep.title}</div>
				<p class="mt-1 text-sm leading-relaxed text-hifi-text-muted">{m.auth.totpStep.description}</p>
			</div>
			<form class="flex flex-col gap-3" on:submit|preventDefault={handleTotpSubmit}>
				<label class="block text-sm">
					<span class="mb-1 block text-hifi-text-muted">{m.auth.totpStep.codeLabel}</span>
					<input
						type="text"
						bind:value={totpCode}
						autocomplete="one-time-code"
						autocapitalize="characters"
						spellcheck="false"
						placeholder={m.auth.totpStep.codePlaceholder}
						class="w-full rounded-[10px] border border-hifi-border bg-hifi-bg p-2.5 text-center font-mono text-lg tracking-widest"
					/>
					<span class="mt-1 block text-[12.5px] text-hifi-text-faint">{m.auth.totpStep.codeHint}</span>
				</label>

				{#if totpError}
					<p class="text-sm text-danger">{totpError}</p>
				{/if}

				<button
					type="submit"
					disabled={totpSubmitting || !totpCode.trim()}
					class="mt-1 rounded-[10px] bg-hifi-accent px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
				>
					{totpSubmitting ? m.auth.totpStep.submitting : m.auth.totpStep.submit}
				</button>
				<button
					type="button"
					on:click={cancelTotp}
					class="self-center text-sm text-hifi-text-muted transition-colors hover:text-hifi-text"
				>
					{m.auth.totpStep.backToPassword}
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
					placeholder="Benutzername oder E-Mail"
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

			{#if passkeySupported}
				<div class="my-4 flex items-center gap-3">
					<div class="h-px flex-1 bg-hifi-border"></div>
					<span class="text-[11.5px] font-semibold uppercase tracking-[0.04em] text-hifi-text-faint">
						{m.passkeyLogin.divider}
					</span>
					<div class="h-px flex-1 bg-hifi-border"></div>
				</div>

				{#if passkeyError}
					<p class="mb-3 text-sm text-danger">{passkeyError}</p>
				{/if}

				<button
					type="button"
					on:click={handlePasskeyLogin}
					disabled={passkeySubmitting}
					class="w-full rounded-[10px] border border-hifi-border px-4 py-2.5 text-sm font-semibold text-hifi-text transition-colors hover:bg-hifi-accent-tint hover:text-hifi-accent-text disabled:opacity-50"
				>
					{passkeySubmitting ? m.passkeyLogin.buttonLoading : m.passkeyLogin.button}
				</button>
			{/if}
		{/if}
	</div>
</div>
