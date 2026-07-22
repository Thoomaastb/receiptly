<script lang="ts">
	import { onMount } from 'svelte';
	import '../app.css';
	import { page } from '$app/stores';
	import { goto, afterNavigate } from '$app/navigation';
	import SettingsNav from '$lib/components/SettingsNav.svelte';
	import ThemeToggle from '$lib/components/ThemeToggle.svelte';
	import AiUsageBadge from '$lib/components/AiUsageBadge.svelte';
	import TotpEnrollment from '$lib/components/TotpEnrollment.svelte';
	import PasskeyEnrollment from '$lib/components/PasskeyEnrollment.svelte';
	import { initThemeSync } from '$lib/theme';
	import { categoryColor, categoryLabel } from '$lib/categories';
	import { m } from '$lib/i18n';

	let categories: { value: string; name: string; color: string; count: number }[] = [];
	let categoriesLoading = true;

	interface CurrentUser {
		username: string;
		email: string;
		role: string;
		totp_enabled: boolean;
		passkey_setup_required: boolean;
	}

	let currentUser: CurrentUser | null = null;
	$: userInitial = (currentUser?.username?.[0] ?? '?').toUpperCase();
	$: isAdmin = currentUser?.role === 'admin';

	// KRITISCH (Security-Hardening Phase 2): Admins ohne abgeschlossene TOTP-Einrichtung
	// bekommen serverseitig bewusst trotzdem eine volle Session (kein Lockout-Risiko beim
	// initialen Login) — das Frontend ist hier die einzige Durchsetzung der Admin-Pflicht,
	// bis Phase 3/4 (Passkeys) das serverseitig nachschärfen. Muss auf jedem
	// authentifizierten Seitenaufruf greifen, nicht nur direkt nach der Registrierung.
	$: totpSetupRequired = currentUser?.role === 'admin' && currentUser?.totp_enabled === false;

	// KRITISCH (Security-Hardening Phase 3, Baustein 3): analog zum TOTP-Gate oben, aber
	// für normale (Nicht-Admin-)User ohne registrierten Passkey — betrifft auch bestehende
	// Accounts nach diesem Deploy, nicht nur frische Registrierungen. Serverseitig liefert
	// /auth/me passkey_setup_required bereits ausschließlich für diese Zielgruppe (nie für
	// Admins), die Bedingung hier prüft es trotzdem nicht exklusiv gegen totpSetupRequired,
	// da beide Gates unterschiedliche Rollen betreffen und sich so nie überschneiden.
	$: passkeySetupRequired = currentUser?.passkey_setup_required === true;

	let authChecked = false;

	let appVersion = '';

	let userMenuOpen = false;
	let userMenuEl: HTMLDivElement;

	function toggleUserMenu() {
		userMenuOpen = !userMenuOpen;
	}

	function handleUserMenuClickOutside(e: MouseEvent) {
		if (!userMenuOpen) return;
		if (!userMenuEl?.contains(e.target as Node)) {
			userMenuOpen = false;
		}
	}

	function handleUserMenuKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') userMenuOpen = false;
	}

	async function logout() {
		userMenuOpen = false;
		await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
		goto('/login');
	}

	// Routen ohne App-Shell/Session-Prüfung: Login sowie der Self-Service-
	// Passwort-Reset-Flow, den auch ausgeloggte Nutzer über einen E-Mail-Link erreichen.
	const AUTH_ROUTES = ['/login', '/forgot-password', '/reset-password'];
	$: isAuthRoute = AUTH_ROUTES.includes($page.url.pathname);
	$: isSettingsRoute = $page.url.pathname.startsWith('/settings');

	async function refreshCurrentUser() {
		try {
			const meRes = await fetch('/api/auth/me', { credentials: 'include' });
			if (meRes.ok) {
				currentUser = await meRes.json();
			} else if (meRes.status === 401) {
				currentUser = null;
				goto('/login');
			}
		} catch {
			// currentUser/Gate-Status bleibt beim letzten bekannten Stand, wenn das Backend
			// kurz nicht erreichbar ist — kein Fehler-UI nötig für dieses Detail
		} finally {
			authChecked = true;
		}
	}

	// Läuft nach JEDER Navigation, nicht nur beim allerersten Laden: das Root-Layout bleibt
	// über client-seitige goto()-Navigationen hinweg gemountet (z.B. Login -> "/"), onMount
	// würde den TOTP-Gate-Check sonst nur beim initialen Seitenaufruf ausführen und ihn nach
	// einem frischen Login im selben Tab verpassen — genau der in Punkt 3 beschriebene
	// kritische Fall.
	afterNavigate(() => {
		if (AUTH_ROUTES.includes($page.url.pathname)) {
			currentUser = null;
			authChecked = false;
			return;
		}
		refreshCurrentUser();
	});

	onMount(async () => {
		initThemeSync();

		if (isAuthRoute) return;

		try {
			const healthRes = await fetch('/api/health');
			if (healthRes.ok) {
				const health = await healthRes.json();
				appVersion = health.version ?? '';
			}
		} catch {
			// Versionsanzeige ist rein informativ — kein Fehler-UI nötig für dieses Detail
		}

		// Kategorien-Sidebar wird auf /settings durch SettingsNav ersetzt — der Fetch
		// wäre dort verschwendet.
		if (isSettingsRoute) return;

		try {
			const res = await fetch('/api/receipts', { credentials: 'include' });
			if (res.ok) {
				const receipts: { category?: string | null }[] = await res.json();
				const counts = new Map<string, number>();
				for (const r of receipts) {
					if (!r.category) continue;
					counts.set(r.category, (counts.get(r.category) ?? 0) + 1);
				}
				categories = Array.from(counts.entries())
					.map(([value, count]) => ({
						value,
						name: categoryLabel(value) ?? value,
						color: categoryColor(value),
						count
					}))
					.sort((a, b) => b.count - a.count);
			}
		} finally {
			categoriesLoading = false;
		}
	});
</script>

<svelte:window on:click={handleUserMenuClickOutside} on:keydown={handleUserMenuKeydown} />

{#if isAuthRoute}
	<slot />
{:else if !authChecked}
	<!-- Verhindert einen kurzen Flash der App-Shell, bevor der TOTP-Gate-Check (unten)
	     abgeschlossen ist — animate-spin respektiert prefers-reduced-motion global über
	     die Regel in app.css. -->
	<div class="flex min-h-screen items-center justify-center bg-hifi-bg">
		<div
			class="h-8 w-8 animate-spin rounded-full border-2 border-hifi-border border-t-hifi-accent"
			role="status"
			aria-label={m.common.checking}
		></div>
	</div>
{:else if totpSetupRequired}
	<!-- KRITISCH: ersetzt die App-Shell vollständig (keine Navigation, keine Slot-Kinder) —
	     Admins ohne totp_enabled kommen an dieser Stelle nicht weiter, bis /auth/totp/confirm
	     erfolgreich war und refreshCurrentUser() das bestätigt. Gleiches Karten-Layout wie
	     /login und /reset-password, damit der Screen als receiptly-eigen erkennbar bleibt
	     und nicht wie eine Fehlerseite wirkt. -->
	<div class="flex min-h-screen items-center justify-center bg-hifi-bg px-4 py-10">
		<div class="w-full max-w-md rounded-2xl border border-hifi-border bg-hifi-surface p-8">
			<div class="mb-6 flex items-center gap-3">
				<span class="flex h-9 w-9 flex-none items-center justify-center rounded-[10px] bg-hifi-accent">
					<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						<path d="M6 3h9l3 3v15H6z" />
						<path d="M9 9h6M9 13h6M9 17h3" />
					</svg>
				</span>
				<span class="text-[19px] font-extrabold tracking-tight text-hifi-text">receiptly</span>
			</div>
			<div class="mb-5">
				<div class="text-lg font-bold text-hifi-text">{m.gate.heading}</div>
				<p class="mt-2 text-sm leading-relaxed text-hifi-text-muted">{m.gate.description}</p>
			</div>
			<TotpEnrollment description={m.totpSetup.gateIntroDescription} onComplete={refreshCurrentUser} />
		</div>
	</div>
{:else if passkeySetupRequired}
	<!-- KRITISCH: gleiches Muster wie das TOTP-Gate oben — App-Shell vollständig ersetzt,
	     keine Navigation möglich. User ohne registrierten Passkey kommen hier nicht weiter,
	     bis /webauthn/register/verify erfolgreich war und refreshCurrentUser() bestätigt,
	     dass passkey_setup_required auf false gewechselt ist. -->
	<div class="flex min-h-screen items-center justify-center bg-hifi-bg px-4 py-10">
		<div class="w-full max-w-md rounded-2xl border border-hifi-border bg-hifi-surface p-8">
			<div class="mb-6 flex items-center gap-3">
				<span class="flex h-9 w-9 flex-none items-center justify-center rounded-[10px] bg-hifi-accent">
					<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						<path d="M6 3h9l3 3v15H6z" />
						<path d="M9 9h6M9 13h6M9 17h3" />
					</svg>
				</span>
				<span class="text-[19px] font-extrabold tracking-tight text-hifi-text">receiptly</span>
			</div>
			<div class="mb-5">
				<div class="text-lg font-bold text-hifi-text">{m.passkeyGate.heading}</div>
				<p class="mt-2 text-sm leading-relaxed text-hifi-text-muted">{m.passkeyGate.description}</p>
			</div>
			<PasskeyEnrollment description={m.passkeySetup.gateIntroDescription} onComplete={refreshCurrentUser} />
		</div>
	</div>
{:else}
<div class="flex h-screen flex-col overflow-hidden bg-hifi-bg font-ui text-hifi-text">
	<div
		class="grid h-[72px] flex-none grid-cols-[1fr_auto_1fr] items-center border-b border-hifi-border bg-hifi-surface px-8"
	>
		<a href="/" class="flex items-center gap-3 justify-self-start">
			<span class="flex h-9 w-9 flex-none items-center justify-center rounded-[10px] bg-hifi-accent">
				<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<path d="M6 3h9l3 3v15H6z" />
					<path d="M9 9h6M9 13h6M9 17h3" />
				</svg>
			</span>
			<span class="text-[19px] font-extrabold tracking-tight">receiptly</span>
		</a>

		<div class="flex items-center gap-2 justify-self-center">
			<a
				href="/"
				class="rounded-[10px] px-4 py-2 text-[14.5px] font-semibold transition-colors"
				class:bg-hifi-accent-tint={$page.url.pathname === '/'}
				class:text-hifi-accent-text={$page.url.pathname === '/'}
				class:text-hifi-text-muted={$page.url.pathname !== '/'}
			>
				Übersicht
			</a>
			<a
				href="/receipts"
				class="rounded-[10px] px-4 py-2 text-[14.5px] font-semibold transition-colors"
				class:bg-hifi-accent-tint={$page.url.pathname.startsWith('/receipts')}
				class:text-hifi-accent-text={$page.url.pathname.startsWith('/receipts')}
				class:text-hifi-text-muted={!$page.url.pathname.startsWith('/receipts')}
			>
				Suche & Filter
			</a>
			<a
				href="/buckets"
				class="rounded-[10px] px-4 py-2 text-[14.5px] font-semibold transition-colors"
				class:bg-hifi-accent-tint={$page.url.pathname.startsWith('/buckets')}
				class:text-hifi-accent-text={$page.url.pathname.startsWith('/buckets')}
				class:text-hifi-text-muted={!$page.url.pathname.startsWith('/buckets')}
			>
				Buckets
			</a>
		</div>

		<div class="flex items-center gap-1.5 justify-self-end">
			<a
				href="/receipts"
				aria-label="Suche"
				class="flex h-[38px] w-[38px] items-center justify-center rounded-[10px] text-hifi-text-muted transition-colors hover:bg-hifi-accent-tint hover:text-hifi-accent-text"
			>
				<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<circle cx="10" cy="10" r="6" />
					<path d="M20 20l-5.5-5.5" />
				</svg>
			</a>
			<button
				aria-label="Benachrichtigungen"
				class="flex h-[38px] w-[38px] items-center justify-center rounded-[10px] text-hifi-text-muted transition-colors hover:bg-hifi-accent-tint hover:text-hifi-accent-text"
			>
				<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<path d="M6 10a6 6 0 0112 0v4l2 3H4l2-3z" />
					<path d="M10 20a2 2 0 004 0" />
				</svg>
			</button>
			<ThemeToggle />
			<div class="mx-1.5 h-[22px] w-px bg-hifi-border"></div>
			<a
				href="/settings"
				aria-label="Einstellungen"
				class="flex h-[38px] w-[38px] items-center justify-center rounded-[10px] text-hifi-text-muted transition-colors hover:bg-hifi-accent-tint hover:text-hifi-accent-text"
			>
				<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<circle cx="12" cy="12" r="3" />
					<path
						d="M19.4 15a1.7 1.7 0 00.34 1.87l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.7 1.7 0 00-1.87-.34 1.7 1.7 0 00-1 1.55V21a2 2 0 01-4 0v-.09a1.7 1.7 0 00-1-1.55 1.7 1.7 0 00-1.87.34l-.06.06a2 2 0 11-2.83-2.83l.06-.06A1.7 1.7 0 004.6 15a1.7 1.7 0 00-1.55-1H3a2 2 0 010-4h.09A1.7 1.7 0 004.6 9a1.7 1.7 0 00-.34-1.87l-.06-.06a2 2 0 112.83-2.83l.06.06A1.7 1.7 0 009 4.6a1.7 1.7 0 001-1.55V3a2 2 0 014 0v.09a1.7 1.7 0 001 1.55 1.7 1.7 0 001.87-.34l.06-.06a2 2 0 112.83 2.83l-.06.06A1.7 1.7 0 0019.4 9a1.7 1.7 0 001.55 1H21a2 2 0 010 4h-.09a1.7 1.7 0 00-1.55 1z"
						stroke-linecap="round"
						stroke-linejoin="round"
					/>
				</svg>
			</a>
			{#if currentUser}
				<div class="relative ml-1" bind:this={userMenuEl}>
					<button
						on:click={toggleUserMenu}
						aria-label="Benutzermenü"
						aria-expanded={userMenuOpen}
						class="flex h-[30px] w-[30px] flex-none items-center justify-center rounded-full bg-hifi-accent-tint text-[12px] font-bold text-hifi-accent-text"
					>
						{userInitial}
					</button>
					{#if userMenuOpen}
						<div class="absolute right-0 top-[38px] z-30 w-56 rounded-[14px] border border-hifi-border bg-hifi-surface p-1.5">
							<div class="px-3 py-2.5">
								<div class="truncate text-[13.5px] font-bold text-hifi-text">{currentUser.username}</div>
								<div class="truncate text-[12px] text-hifi-text-muted">{currentUser.email}</div>
							</div>
							<div class="my-1 h-px bg-hifi-border"></div>
							<button
								on:click={logout}
								class="flex w-full items-center gap-2 rounded-[9px] px-3 py-2 text-left text-[13px] font-medium text-hifi-text transition-colors hover:bg-hifi-accent-tint"
							>
								<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
									<path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
									<path d="M16 17l5-5-5-5" />
									<path d="M21 12H9" />
								</svg>
								Abmelden
							</button>
							{#if appVersion}
								<div class="my-1 h-px bg-hifi-border"></div>
								<div class="px-3 pt-1 pb-1.5 text-[11px] text-hifi-text-faint">Version {appVersion}</div>
							{/if}
						</div>
					{/if}
				</div>
			{/if}
		</div>
	</div>

	<div class="flex min-h-0 flex-1">
		<aside class="flex w-[232px] flex-none flex-col overflow-hidden border-r border-hifi-border bg-hifi-surface p-4 py-6">
			<div class="flex min-h-0 flex-1 flex-col gap-6">
			{#if isSettingsRoute}
				<SettingsNav {isAdmin} />
			{:else}
				<div class="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto">
					<div class="px-3 pb-2 text-[11.5px] font-bold uppercase tracking-[0.04em] text-hifi-text-faint">
						Kategorien
					</div>
					{#if categoriesLoading}
						<div class="px-3 py-2 text-[13px] text-hifi-text-faint">Wird geladen …</div>
					{:else if categories.length === 0}
						<div class="px-3 py-2 text-[12.5px] leading-relaxed text-hifi-text-faint">
							Noch keine Kategorien — sobald ein Beleg eine Kategorie hat, taucht sie hier auf.
						</div>
					{:else}
						{#each categories as cat (cat.value)}
							<button
								on:click={() => goto(`/receipts?category=${encodeURIComponent(cat.value)}`)}
								class="flex flex-none items-center gap-2.5 rounded-[9px] px-3 py-2 text-left text-[13.5px] font-medium text-hifi-text transition-colors hover:bg-hifi-accent-tint"
							>
								<span class="h-2 w-2 flex-none rounded-full" style="background: {cat.color}"></span>
								<span class="flex-1 truncate">{cat.name}</span>
								<span class="font-mono text-xs text-hifi-text-faint">{cat.count}</span>
							</button>
						{/each}
					{/if}
				</div>

			{/if}
			</div>

			{#if isAdmin}
				<div class="flex-none pt-3">
					<AiUsageBadge />
				</div>
			{/if}
		</aside>

		<main class="min-w-0 flex-1 overflow-y-auto px-10 pb-16 pt-9">
			<slot />
		</main>
	</div>
</div>
{/if}
