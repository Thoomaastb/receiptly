<script lang="ts">
	import { onMount } from 'svelte';
	import { parseUserAgent } from '$lib/userAgent';

	interface SessionInfo {
		session_id: string;
		user_agent: string;
		ip: string;
		created_at: string;
		last_seen_at: string;
		is_current: boolean;
	}

	// Passwort ändern
	let currentPassword = '';
	let newPassword = '';
	let confirmPassword = '';
	let validationError = '';
	let requestError = '';
	let submitting = false;
	let changeSuccess = false;

	// Sitzungen
	let sessions: SessionInfo[] = [];
	let sessionsLoading = true;
	let sessionsError = '';
	let terminatingId: string | null = null;

	function validate(): boolean {
		if (newPassword.length < 8) {
			validationError = 'Das neue Passwort muss mind. 8 Zeichen lang sein.';
			return false;
		}
		if (newPassword !== confirmPassword) {
			validationError = 'Die Passwörter stimmen nicht überein.';
			return false;
		}
		validationError = '';
		return true;
	}

	async function handleChangePassword() {
		requestError = '';
		changeSuccess = false;
		if (!validate()) return;

		submitting = true;
		try {
			const res = await fetch('/api/auth/change-password', {
				method: 'POST',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					current_password: currentPassword,
					new_password: newPassword
				})
			});
			if (!res.ok) {
				const body = await res.json().catch(() => null);
				throw new Error(body?.detail ?? `Passwort ändern fehlgeschlagen (${res.status})`);
			}

			changeSuccess = true;
			currentPassword = '';
			newPassword = '';
			confirmPassword = '';
			loadSessions();
		} catch (err) {
			requestError = err instanceof Error ? err.message : 'Passwort ändern fehlgeschlagen.';
		} finally {
			submitting = false;
		}
	}

	function formatLastSeen(iso: string): string {
		return new Date(iso).toLocaleString('de-DE', { dateStyle: 'medium', timeStyle: 'short' });
	}

	async function loadSessions() {
		sessionsLoading = true;
		sessionsError = '';
		try {
			const res = await fetch('/api/auth/sessions', { credentials: 'include' });
			if (!res.ok) throw new Error(`Sitzungen konnten nicht geladen werden (${res.status})`);
			sessions = await res.json();
		} catch (err) {
			sessionsError = err instanceof Error ? err.message : 'Sitzungen konnten nicht geladen werden.';
		} finally {
			sessionsLoading = false;
		}
	}

	async function terminateSession(sessionId: string) {
		terminatingId = sessionId;
		sessionsError = '';
		try {
			const res = await fetch(`/api/auth/sessions/${sessionId}`, {
				method: 'DELETE',
				credentials: 'include'
			});
			if (!res.ok) {
				const body = await res.json().catch(() => null);
				throw new Error(body?.detail ?? `Sitzung konnte nicht beendet werden (${res.status})`);
			}
			await loadSessions();
		} catch (err) {
			sessionsError = err instanceof Error ? err.message : 'Sitzung konnte nicht beendet werden.';
		} finally {
			terminatingId = null;
		}
	}

	onMount(loadSessions);
</script>

<div class="flex max-w-2xl flex-col gap-6">
	<div class="rounded-[14px] border border-hifi-border bg-hifi-surface p-6">
		<h2 class="mb-1 text-[13.5px] font-bold text-hifi-text">Passwort ändern</h2>
		<p class="mb-4 text-sm text-hifi-text-muted">
			Nach dem Ändern bleibt diese Sitzung aktiv, alle anderen Sitzungen werden abgemeldet.
		</p>

		<form class="flex flex-col gap-3" on:submit|preventDefault={handleChangePassword}>
			<label class="block text-sm">
				<span class="mb-1 block text-hifi-text-muted">Aktuelles Passwort</span>
				<input
					type="password"
					bind:value={currentPassword}
					autocomplete="current-password"
					class="w-full rounded-[10px] border border-hifi-border bg-hifi-bg p-2.5 text-sm"
				/>
			</label>
			<label class="block text-sm">
				<span class="mb-1 block text-hifi-text-muted">Neues Passwort (mind. 8 Zeichen)</span>
				<input
					type="password"
					bind:value={newPassword}
					autocomplete="new-password"
					class="w-full rounded-[10px] border border-hifi-border bg-hifi-bg p-2.5 text-sm"
				/>
			</label>
			<label class="block text-sm">
				<span class="mb-1 block text-hifi-text-muted">Neues Passwort wiederholen</span>
				<input
					type="password"
					bind:value={confirmPassword}
					autocomplete="new-password"
					class="w-full rounded-[10px] border border-hifi-border bg-hifi-bg p-2.5 text-sm"
				/>
			</label>

			{#if validationError}
				<p class="text-sm text-danger">{validationError}</p>
			{/if}
			{#if requestError}
				<p class="text-sm text-danger">{requestError}</p>
			{/if}
			{#if changeSuccess}
				<p class="text-sm text-hifi-accent-text">Passwort wurde geändert.</p>
			{/if}

			<button
				type="submit"
				disabled={submitting}
				class="mt-1 self-start rounded-[10px] bg-hifi-accent px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
			>
				{submitting ? 'Wird gespeichert …' : 'Passwort ändern'}
			</button>
		</form>
	</div>

	<div class="rounded-[14px] border border-hifi-border bg-hifi-surface p-6">
		<h2 class="mb-1 text-[13.5px] font-bold text-hifi-text">Aktive Sitzungen</h2>
		<p class="mb-4 text-sm text-hifi-text-muted">
			Geräte und Browser, die aktuell bei deinem Konto angemeldet sind.
		</p>

		{#if sessionsError}
			<p class="mb-3 text-sm text-danger">{sessionsError}</p>
		{/if}

		{#if sessionsLoading}
			<p class="text-sm text-hifi-text-muted">Wird geladen …</p>
		{:else if sessions.length === 0}
			<p class="text-sm text-hifi-text-muted">Keine aktiven Sitzungen gefunden.</p>
		{:else}
			<ul class="flex flex-col">
				{#each sessions as session (session.session_id)}
					{@const parsed = parseUserAgent(session.user_agent)}
					<li class="flex items-center justify-between gap-4 border-b border-hifi-border py-3 last:border-0">
						<div class="min-w-0">
							<div class="flex items-center gap-2">
								<span class="truncate text-sm font-semibold text-hifi-text">
									{parsed.browser} auf {parsed.os}
								</span>
								{#if session.is_current}
									<span class="inline-flex flex-none items-center rounded-full bg-hifi-accent-tint px-2.5 py-0.5 text-[11.5px] font-medium text-hifi-accent-text">
										Aktuelle Sitzung
									</span>
								{/if}
							</div>
							<div class="mt-0.5 text-[12.5px] text-hifi-text-faint">
								{session.ip} · zuletzt aktiv {formatLastSeen(session.last_seen_at)}
							</div>
						</div>
						{#if !session.is_current}
							<button
								on:click={() => terminateSession(session.session_id)}
								disabled={terminatingId === session.session_id}
								class="flex-none rounded-[10px] border border-hifi-border px-3 py-1.5 text-[13px] font-medium text-hifi-text transition-colors hover:bg-danger-bg hover:text-danger disabled:opacity-50"
							>
								{terminatingId === session.session_id ? 'Wird beendet …' : 'Beenden'}
							</button>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	</div>
</div>
