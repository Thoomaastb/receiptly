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

	interface AuditLogEntry {
		id: string;
		event_type: string;
		ip: string | null;
		user_agent: string | null;
		attempted_username: string | null;
		event_metadata: Record<string, unknown> | null;
		created_at: string;
	}

	// Menschenlesbare Labels für rohe event_type-Werte des Backends. Unbekannte/künftige
	// Werte fallen auf eine automatische snake_case-Umwandlung zurück (siehe eventTypeLabel),
	// damit ein neuer Event-Typ nicht als kryptischer Rohstring auftaucht.
	const EVENT_TYPE_LABELS: Record<string, string> = {
		login_success: 'Erfolgreiche Anmeldung',
		login_failed: 'Fehlgeschlagene Anmeldung',
		logout: 'Abmeldung',
		password_changed: 'Passwort geändert',
		password_reset_confirmed: 'Passwort per Reset-Link geändert',
		session_terminated: 'Sitzung beendet',
		rate_limit_triggered: 'Rate-Limit ausgelöst'
	};

	// Sicherheitsrelevante Events optisch hervorheben (dezenter Punkt vor dem Label),
	// damit fehlgeschlagene Logins/Rate-Limit-Treffer beim Überfliegen der Liste auffallen.
	const EVENT_TONE: Record<string, 'success' | 'danger' | 'warning' | 'muted'> = {
		login_success: 'success',
		login_failed: 'danger',
		logout: 'muted',
		password_changed: 'success',
		password_reset_confirmed: 'success',
		session_terminated: 'muted',
		rate_limit_triggered: 'warning'
	};

	function eventTypeLabel(eventType: string): string {
		return (
			EVENT_TYPE_LABELS[eventType] ??
			eventType
				.split('_')
				.map((part) => part.charAt(0).toUpperCase() + part.slice(1))
				.join(' ')
		);
	}

	function eventTone(eventType: string): 'success' | 'danger' | 'warning' | 'muted' {
		return EVENT_TONE[eventType] ?? 'muted';
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

	// Aktivität (Audit-Log)
	const AUDIT_PAGE_SIZE = 20;
	let auditEvents: AuditLogEntry[] = [];
	let auditLoading = true;
	let auditLoadingMore = false;
	let auditError = '';
	let auditHasMore = true;

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

	// Lädt die nächste Seite eigener Audit-Events und hängt sie an ("Mehr laden" statt
	// Endless-Scroll — passend zur begrenzten Höhe eines Settings-Abschnitts).
	async function loadAuditEvents() {
		const offset = auditEvents.length;
		if (offset === 0) {
			auditLoading = true;
		} else {
			auditLoadingMore = true;
		}
		auditError = '';
		try {
			const res = await fetch(`/api/audit-log?limit=${AUDIT_PAGE_SIZE}&offset=${offset}`, {
				credentials: 'include'
			});
			if (!res.ok) throw new Error(`Aktivität konnte nicht geladen werden (${res.status})`);
			const nextPage: AuditLogEntry[] = await res.json();
			auditEvents = [...auditEvents, ...nextPage];
			auditHasMore = nextPage.length === AUDIT_PAGE_SIZE;
		} catch (err) {
			auditError = err instanceof Error ? err.message : 'Aktivität konnte nicht geladen werden.';
		} finally {
			auditLoading = false;
			auditLoadingMore = false;
		}
	}

	onMount(() => {
		loadSessions();
		loadAuditEvents();
	});
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

	<div class="rounded-[14px] border border-hifi-border bg-hifi-surface p-6">
		<h2 class="mb-1 text-[13.5px] font-bold text-hifi-text">Aktivität</h2>
		<p class="mb-4 text-sm text-hifi-text-muted">
			Sicherheitsrelevante Ereignisse deines Kontos — Anmeldungen, Passwortänderungen und
			beendete Sitzungen.
		</p>

		{#if auditError}
			<p class="mb-3 text-sm text-danger">{auditError}</p>
		{/if}

		{#if auditLoading}
			<p class="text-sm text-hifi-text-muted">Wird geladen …</p>
		{:else if auditEvents.length === 0 && !auditError}
			<p class="text-sm text-hifi-text-muted">Noch keine Aktivität.</p>
		{:else}
			<ul class="flex flex-col">
				{#each auditEvents as entry (entry.id)}
					{@const parsed = entry.user_agent ? parseUserAgent(entry.user_agent) : null}
					{@const tone = eventTone(entry.event_type)}
					<li class="flex flex-col gap-0.5 border-b border-hifi-border py-3 last:border-0">
						<div class="flex items-center justify-between gap-4">
							<span class="flex min-w-0 items-center gap-2 text-sm font-semibold text-hifi-text">
								<span
									aria-hidden="true"
									class="inline-block h-2 w-2 flex-none rounded-full"
									class:bg-success={tone === 'success'}
									class:bg-danger={tone === 'danger'}
									class:bg-status-warning={tone === 'warning'}
									class:bg-hifi-text-faint={tone === 'muted'}
								></span>
								<span class="truncate">{eventTypeLabel(entry.event_type)}</span>
							</span>
							<span class="flex-none text-[12.5px] text-hifi-text-faint">
								{formatLastSeen(entry.created_at)}
							</span>
						</div>
						{#if parsed || entry.ip || entry.attempted_username}
							<div class="text-[12.5px] text-hifi-text-faint">
								{[
									parsed ? `${parsed.browser} auf ${parsed.os}` : null,
									entry.ip,
									entry.attempted_username ? `Versuch: ${entry.attempted_username}` : null
								]
									.filter(Boolean)
									.join(' · ')}
							</div>
						{/if}
					</li>
				{/each}
			</ul>

			{#if auditHasMore}
				<button
					on:click={loadAuditEvents}
					disabled={auditLoadingMore}
					class="mt-3 self-start rounded-[10px] border border-hifi-border px-3 py-1.5 text-[13px] font-medium text-hifi-text transition-colors hover:bg-hifi-accent-tint hover:text-hifi-accent-text disabled:opacity-50"
				>
					{auditLoadingMore ? 'Wird geladen …' : 'Mehr laden'}
				</button>
			{/if}
		{/if}
	</div>
</div>
