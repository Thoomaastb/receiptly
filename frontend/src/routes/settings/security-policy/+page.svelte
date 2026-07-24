<script lang="ts">
	import { onMount } from 'svelte';
	import { m } from '$lib/i18n';
	import { parseUserAgent } from '$lib/userAgent';
	import CustomSelect from '$lib/components/CustomSelect.svelte';

	type RetentionDays = 30 | 90 | 180 | 365;

	interface SecurityPolicy {
		totp_required_for_household: boolean;
		audit_retention_days: RetentionDays;
		log_attempted_username: boolean;
		passkey_exclusive_login: boolean;
	}

	// Live-Precondition-Status für den Passkey-Exklusiv-Schalter (Phase 4) — eigener
	// GET-Endpoint, unabhängig von einem Aktivierungsversuch abrufbar (siehe
	// backend/app/schemas/security_settings.py::PasskeyExclusiveGateStatus). Das PUT liefert
	// bei Ablehnung dasselbe Shape im detail-Objekt (plus `message`), daher hier
	// wiederverwendet statt einer eigenen zweiten Interface-Definition.
	interface PasskeyExclusiveGateStatus {
		eligible: boolean;
		total_members: number;
		missing_count: number;
		missing_usernames: string[];
	}

	// Eigene, kleine Kopie der Event-Label/Ton-Logik aus settings/security/+page.svelte
	// (Eigensicht-Aktivität, Phase 1) — jene Datei bleibt bewusst unverändert, daher hier
	// dupliziert statt geteilt extrahiert. Bei einem dritten Verwendungsort wäre eine
	// gemeinsame lib/-Hilfsfunktion sinnvoll.
	interface HouseholdAuditLogEntry {
		id: string;
		event_type: string;
		ip: string | null;
		user_agent: string | null;
		attempted_username: string | null;
		event_metadata: Record<string, unknown> | null;
		created_at: string;
		user_id: string | null;
		username: string | null;
	}

	const EVENT_TYPE_LABELS: Record<string, string> = {
		login_success: 'Erfolgreiche Anmeldung',
		login_failed: 'Fehlgeschlagene Anmeldung',
		logout: 'Abmeldung',
		password_changed: 'Passwort geändert',
		password_reset_confirmed: 'Passwort per Reset-Link geändert',
		session_terminated: 'Sitzung beendet',
		rate_limit_triggered: 'Rate-Limit ausgelöst',
		// Neu in Phase 2 (TOTP) — gegen den echten Stand in backend/app/api/{auth,totp}.py
		// verifiziert (golden-path-Test gegen einen frisch aufgesetzten Testhaushalt).
		totp_login_success: 'Anmeldung mit TOTP bestätigt',
		recovery_code_used: 'Anmeldung mit Recovery-Code bestätigt',
		totp_login_failed: 'Fehlgeschlagene TOTP-Bestätigung',
		totp_enabled: 'Zwei-Faktor-Authentifizierung aktiviert',
		totp_disabled: 'Zwei-Faktor-Authentifizierung deaktiviert',
		recovery_codes_regenerated: 'Recovery-Codes neu generiert',
		// Neu in Phase 3 (Passkeys) — gegen backend/app/api/webauthn.py verifiziert.
		passkey_registered: 'Passkey registriert',
		passkey_removed: 'Passkey entfernt',
		passkey_login_success: 'Anmeldung mit Passkey',
		passkey_login_failed: 'Fehlgeschlagene Anmeldung mit Passkey'
	};

	const EVENT_TONE: Record<string, 'success' | 'danger' | 'warning' | 'muted'> = {
		login_success: 'success',
		login_failed: 'danger',
		logout: 'muted',
		password_changed: 'success',
		password_reset_confirmed: 'success',
		session_terminated: 'muted',
		rate_limit_triggered: 'warning',
		totp_login_success: 'success',
		recovery_code_used: 'warning',
		totp_login_failed: 'danger',
		totp_enabled: 'success',
		totp_disabled: 'warning',
		recovery_codes_regenerated: 'success',
		passkey_registered: 'success',
		passkey_removed: 'muted',
		passkey_login_success: 'success',
		passkey_login_failed: 'danger'
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

	function formatLastSeen(iso: string): string {
		return new Date(iso).toLocaleString('de-DE', { dateStyle: 'medium', timeStyle: 'short' });
	}

	const RETENTION_OPTIONS: { value: string; label: string }[] = [
		{ value: '30', label: m.securityPolicy.retentionOption30 },
		{ value: '90', label: m.securityPolicy.retentionOption90 },
		{ value: '180', label: m.securityPolicy.retentionOption180 },
		{ value: '365', label: m.securityPolicy.retentionOption365 }
	];

	let checkingAccess = true;
	let isAdmin = false;

	let policyLoading = true;
	let policyLoadError = '';
	let totpRequiredForHousehold = false;
	let retentionValue = '90';
	let logAttemptedUsername = true;
	let passkeyExclusiveLogin = false;
	let saving = false;
	let saveMessage = '';
	let saveError = '';

	// Eigener Ladezustand statt Teil von policyLoading — die Gate-Auskunft kommt aus einem
	// zweiten, unabhängigen Endpoint (parallel zu GET .../security-policy geladen) und darf
	// dessen Fehler-/Ladeanzeige nicht verkoppeln.
	let gateLoading = true;
	let gateError = '';
	let gateEligible = false;
	let gateTotalMembers = 0;
	let gateMissingCount = 0;
	let gateMissingUsernames: string[] = [];

	// Aktivieren ist gesperrt, solange die Precondition nicht (bestätigt) erfüllt ist —
	// Deaktivieren bleibt in jedem Fall möglich (Rettungsweg bei Passkey-Verlust, Konzept Q18).
	$: passkeyToggleDisabled =
		!passkeyExclusiveLogin && (gateLoading || gateError !== '' || !gateEligible);

	async function loadAccess(): Promise<boolean> {
		try {
			const meRes = await fetch('/api/auth/me', { credentials: 'include' });
			if (!meRes.ok) return false;
			const me: { role: string } = await meRes.json();
			return me.role === 'admin';
		} catch {
			return false;
		}
	}

	async function loadPolicy() {
		policyLoading = true;
		policyLoadError = '';
		try {
			const res = await fetch('/api/settings/security-policy', { credentials: 'include' });
			if (!res.ok) throw new Error(`${res.status}`);
			const policy: SecurityPolicy = await res.json();
			totpRequiredForHousehold = policy.totp_required_for_household;
			retentionValue = String(policy.audit_retention_days);
			logAttemptedUsername = policy.log_attempted_username;
			passkeyExclusiveLogin = policy.passkey_exclusive_login;
		} catch {
			policyLoadError = m.securityPolicy.loadError;
		} finally {
			policyLoading = false;
		}
	}

	async function loadPasskeyExclusiveGate() {
		gateLoading = true;
		gateError = '';
		try {
			const res = await fetch('/api/settings/security-policy/passkey-exclusive-gate', {
				credentials: 'include'
			});
			if (!res.ok) throw new Error(`${res.status}`);
			const gate: PasskeyExclusiveGateStatus = await res.json();
			gateEligible = gate.eligible;
			gateTotalMembers = gate.total_members;
			gateMissingCount = gate.missing_count;
			gateMissingUsernames = gate.missing_usernames;
		} catch {
			gateError = m.securityPolicy.exclusiveGateLoadError;
		} finally {
			gateLoading = false;
		}
	}

	// Kein Templating-Mechanismus im schlanken i18n-Katalog (lib/i18n/de.ts ist reine
	// Key->String-Zuordnung, siehe restliche Datei) — einfache {missing}/{total}-Platzhalter
	// statt dafür eine neue Interpolations-Bibliothek einzuführen.
	function formatGateBlockedMessage(missing: number, total: number): string {
		return m.securityPolicy.exclusiveGateBlocked
			.replace('{missing}', String(missing))
			.replace('{total}', String(total));
	}

	// PUT liefert bei Precondition-Verstoß (Race Condition zwischen Laden und Speichern, z.B.
	// ein Mitglied hat seinen einzigen Passkey zwischenzeitlich gelöscht) ein strukturiertes
	// detail-Objekt statt eines reinen Strings — dessen Gate-Zahlen direkt übernehmen, damit
	// die Live-Anzeige ohne zusätzlichen Request aktuell bleibt.
	function extractSaveErrorMessage(detail: unknown): string {
		if (typeof detail === 'string') return detail;
		if (detail && typeof detail === 'object' && 'message' in detail && 'eligible' in detail) {
			const gateDetail = detail as PasskeyExclusiveGateStatus & { message: string };
			gateEligible = gateDetail.eligible;
			gateTotalMembers = gateDetail.total_members;
			gateMissingCount = gateDetail.missing_count;
			gateMissingUsernames = gateDetail.missing_usernames;
			return gateDetail.message;
		}
		return m.securityPolicy.saveError;
	}

	async function handleSave() {
		saving = true;
		saveMessage = '';
		saveError = '';
		try {
			const res = await fetch('/api/settings/security-policy', {
				method: 'PUT',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					totp_required_for_household: totpRequiredForHousehold,
					audit_retention_days: Number(retentionValue),
					log_attempted_username: logAttemptedUsername,
					passkey_exclusive_login: passkeyExclusiveLogin
				})
			});
			if (!res.ok) {
				const body = await res.json().catch(() => null);
				throw new Error(extractSaveErrorMessage(body?.detail));
			}
			saveMessage = m.securityPolicy.saveSuccess;
		} catch (err) {
			saveError = err instanceof Error ? err.message : m.securityPolicy.saveError;
		} finally {
			saving = false;
		}
	}

	const AUDIT_PAGE_SIZE = 20;
	let auditEvents: HouseholdAuditLogEntry[] = [];
	let auditLoading = true;
	let auditLoadingMore = false;
	let auditError = '';
	let auditHasMore = true;

	async function loadHouseholdAuditEvents() {
		const offset = auditEvents.length;
		if (offset === 0) {
			auditLoading = true;
		} else {
			auditLoadingMore = true;
		}
		auditError = '';
		try {
			const res = await fetch(`/api/audit-log?scope=household&limit=${AUDIT_PAGE_SIZE}&offset=${offset}`, {
				credentials: 'include'
			});
			if (!res.ok) throw new Error(`${res.status}`);
			const nextPage: HouseholdAuditLogEntry[] = await res.json();
			auditEvents = [...auditEvents, ...nextPage];
			auditHasMore = nextPage.length === AUDIT_PAGE_SIZE;
		} catch {
			auditError = m.securityPolicy.auditLoadError;
		} finally {
			auditLoading = false;
			auditLoadingMore = false;
		}
	}

	onMount(async () => {
		isAdmin = await loadAccess();
		checkingAccess = false;
		if (!isAdmin) return;
		loadPolicy();
		loadPasskeyExclusiveGate();
		loadHouseholdAuditEvents();
	});
</script>

{#if checkingAccess}
	<p class="text-sm text-hifi-text-muted">{m.common.checking}</p>
{:else if !isAdmin}
	<p class="text-sm text-hifi-text-muted">{m.securityPolicy.accessDenied}</p>
{:else}
	<div class="grid max-w-5xl grid-cols-1 gap-6 lg:grid-cols-2 lg:items-start">
		<div class="rounded-[14px] border border-hifi-border bg-hifi-surface p-6">
			<h2 class="mb-1 text-[13.5px] font-bold text-hifi-text">{m.securityPolicy.policyCardTitle}</h2>
			<p class="mb-4 text-sm text-hifi-text-muted">{m.securityPolicy.policyCardDescription}</p>

			{#if policyLoading}
				<p class="text-sm text-hifi-text-muted">Wird geladen …</p>
			{:else if policyLoadError}
				<p class="text-sm text-danger">{policyLoadError}</p>
			{:else}
				<div class="flex flex-col gap-5">
					<div class="flex items-center justify-between gap-4">
						<div class="min-w-0">
							<div class="text-sm font-semibold text-hifi-text">{m.securityPolicy.totpRequiredLabel}</div>
							<div class="mt-0.5 text-[12.5px] leading-relaxed text-hifi-text-muted">
								{m.securityPolicy.totpRequiredDescription}
							</div>
						</div>
						<button
							type="button"
							role="switch"
							aria-checked={totpRequiredForHousehold}
							aria-label={m.securityPolicy.totpRequiredLabel}
							on:click={() => (totpRequiredForHousehold = !totpRequiredForHousehold)}
							class="relative h-6 w-11 flex-none rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-hifi-accent focus-visible:ring-offset-2 {totpRequiredForHousehold
								? 'bg-hifi-accent'
								: 'bg-hifi-border'}"
						>
							<span
								class="absolute left-0 top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform {totpRequiredForHousehold
									? 'translate-x-[22px]'
									: 'translate-x-0.5'}"
							></span>
						</button>
					</div>

					<div>
						<span id="retention-select-label" class="mb-1 block text-sm font-semibold text-hifi-text">
							{m.securityPolicy.retentionLabel}
						</span>
						<p class="mb-2 text-[12.5px] leading-relaxed text-hifi-text-muted">
							{m.securityPolicy.retentionDescription}
						</p>
						<div class="max-w-[220px]">
							<CustomSelect bind:value={retentionValue} labelledBy="retention-select-label" options={RETENTION_OPTIONS} />
						</div>
					</div>

					<div class="flex items-center justify-between gap-4">
						<div class="min-w-0">
							<div class="text-sm font-semibold text-hifi-text">{m.securityPolicy.logUsernameLabel}</div>
							<div class="mt-0.5 text-[12.5px] leading-relaxed text-hifi-text-muted">
								{m.securityPolicy.logUsernameDescription}
							</div>
						</div>
						<button
							type="button"
							role="switch"
							aria-checked={logAttemptedUsername}
							aria-label={m.securityPolicy.logUsernameLabel}
							on:click={() => (logAttemptedUsername = !logAttemptedUsername)}
							class="relative h-6 w-11 flex-none rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-hifi-accent focus-visible:ring-offset-2 {logAttemptedUsername
								? 'bg-hifi-accent'
								: 'bg-hifi-border'}"
						>
							<span
								class="absolute left-0 top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform {logAttemptedUsername
									? 'translate-x-[22px]'
									: 'translate-x-0.5'}"
							></span>
						</button>
					</div>

					<div class="rounded-[14px] border border-status-warning-border p-4">
						<h3 class="mb-1 text-[11.5px] font-bold uppercase tracking-[0.04em] text-status-warning">
							{m.securityPolicy.exclusiveSectionTitle}
						</h3>
						<p class="mb-3 text-[12.5px] leading-relaxed text-hifi-text-muted">
							{m.securityPolicy.exclusiveWarning}
						</p>

						{#if gateError}
							<p class="mb-3 text-sm text-danger">{gateError}</p>
						{:else if !gateLoading && !gateEligible}
							<div class="mb-3 rounded-[10px] border border-status-warning-border bg-status-warning-bg p-3 text-[12.5px] leading-relaxed">
								<p>{formatGateBlockedMessage(gateMissingCount, gateTotalMembers)}</p>
								{#if gateMissingUsernames.length > 0}
									<p class="mt-1.5 font-semibold">{m.securityPolicy.exclusiveGateMissingUsernamesLabel}</p>
									<ul class="mt-0.5 list-disc pl-4">
										{#each gateMissingUsernames as username (username)}
											<li>{username}</li>
										{/each}
									</ul>
								{/if}
							</div>
						{/if}

						<div class="flex items-center justify-between gap-4">
							<div class="min-w-0">
								<div class="text-sm font-semibold text-hifi-text">{m.securityPolicy.exclusiveLabel}</div>
								<div class="mt-0.5 text-[12.5px] leading-relaxed text-hifi-text-muted">
									{m.securityPolicy.exclusiveDescription}
								</div>
							</div>
							<button
								type="button"
								role="switch"
								aria-checked={passkeyExclusiveLogin}
								aria-label={m.securityPolicy.exclusiveLabel}
								disabled={passkeyToggleDisabled}
								on:click={() => (passkeyExclusiveLogin = !passkeyExclusiveLogin)}
								class="relative h-6 w-11 flex-none rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-hifi-accent focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 {passkeyExclusiveLogin
									? 'bg-hifi-accent'
									: 'bg-hifi-border'}"
							>
								<span
									class="absolute left-0 top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform {passkeyExclusiveLogin
										? 'translate-x-[22px]'
										: 'translate-x-0.5'}"
								></span>
							</button>
						</div>
					</div>

					{#if saveMessage}
						<p class="text-sm text-hifi-accent-text">{saveMessage}</p>
					{/if}
					{#if saveError}
						<p class="text-sm text-danger">{saveError}</p>
					{/if}

					<button
						type="button"
						on:click={handleSave}
						disabled={saving}
						class="self-start rounded-[10px] bg-hifi-accent px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
					>
						{saving ? m.securityPolicy.saveButtonSaving : m.securityPolicy.saveButton}
					</button>
				</div>
			{/if}
		</div>

		<div class="rounded-[14px] border border-hifi-border bg-hifi-surface p-6">
			<h2 class="mb-1 text-[13.5px] font-bold text-hifi-text">{m.securityPolicy.auditCardTitle}</h2>
			<p class="mb-4 text-sm text-hifi-text-muted">{m.securityPolicy.auditCardDescription}</p>

			{#if auditError}
				<p class="mb-3 text-sm text-danger">{auditError}</p>
			{/if}

			{#if auditLoading}
				<p class="text-sm text-hifi-text-muted">Wird geladen …</p>
			{:else if auditEvents.length === 0 && !auditError}
				<p class="text-sm text-hifi-text-muted">{m.securityPolicy.auditEmpty}</p>
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
									{#if entry.username}
										<span class="flex-none rounded-full bg-hifi-accent-tint px-2 py-0.5 text-[11.5px] font-medium text-hifi-accent-text">
											{entry.username}
										</span>
									{/if}
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
						on:click={loadHouseholdAuditEvents}
						disabled={auditLoadingMore}
						class="mt-3 self-start rounded-[10px] border border-hifi-border px-3 py-1.5 text-[13px] font-medium text-hifi-text transition-colors hover:bg-hifi-accent-tint hover:text-hifi-accent-text disabled:opacity-50"
					>
						{auditLoadingMore ? 'Wird geladen …' : m.securityPolicy.auditLoadMore}
					</button>
				{/if}
			{/if}
		</div>
	</div>
{/if}
