<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { scale } from 'svelte/transition';
	import { cubicOut } from 'svelte/easing';
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
	import {
		unreadTotal,
		refreshUnreadCounts,
		startPolling,
		stopPolling,
		markAllRead
	} from '$lib/notifications';
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

	// Benachrichtigungs-Polling startet erst, sobald die App-Shell tatsächlich sichtbar wird
	// (gleiche Bedingung wie der {:else}-Zweig unten) — /api/notifications/* ist ohnehin durch
	// require_totp_enrolled gesperrt, ein früherer Start würde nur nutzlos fehlschlagende
	// Requests während TOTP-/Passkey-Gate erzeugen. pollingStarted verhindert mehrfaches
	// Neu-Aufsetzen bei jeder currentUser-Aktualisierung nach Navigation.
	let pollingStarted = false;
	$: if (currentUser && !totpSetupRequired && !passkeySetupRequired && !pollingStarted) {
		pollingStarted = true;
		startPolling();
		refreshUnreadCounts();
	}

	let authChecked = false;

	let appVersion = '';

	let userMenuOpen = false;
	let userMenuEl: HTMLDivElement;

	function toggleUserMenu() {
		userMenuOpen = !userMenuOpen;
	}

	interface NotificationItem {
		id: string;
		category: string;
		type: string;
		title: string;
		body: string;
		link: string | null;
		read_at: string | null;
		created_at: string;
	}

	// Kleine lokale Kategorie->Label-Map, NICHT categoryLabel() aus $lib/categories
	// wiederverwenden — jenes ist für Beleg-Kategorien (Elektronik, Lebensmittel, ...), ein
	// anderes Vokabular als die Benachrichtigungs-Kategorien hier.
	const NOTIFICATION_CATEGORY_LABELS: Record<string, string> = {
		garantie: 'Garantie',
		sicherheit: 'Sicherheit'
	};

	function notificationCategoryLabel(category: string): string {
		return NOTIFICATION_CATEGORY_LABELS[category] ?? category;
	}

	function formatNotificationTime(iso: string): string {
		return new Date(iso).toLocaleString('de-DE', { dateStyle: 'medium', timeStyle: 'short' });
	}

	let notificationsOpen = false;
	let notificationsEl: HTMLDivElement;
	let notifications: NotificationItem[] = [];
	let notificationsLoading = false;
	let activeNotificationTab = 'all';

	// Tab-Angebot aus der bereits geladenen Gesamtliste abgeleitet (distinct categories),
	// nicht aus $unreadByCategory — Letzteres enthält nur Kategorien mit mindestens einer
	// UNGELESENEN Zeile und würde eine Kategorie ausblenden, sobald ihre Historie vollständig
	// gelesen ist, obwohl der Nutzer sie hier weiterhin durchblättern können soll.
	$: notificationTabs = Array.from(new Set(notifications.map((n) => n.category)));
	$: filteredNotifications =
		activeNotificationTab === 'all'
			? notifications
			: notifications.filter((n) => n.category === activeNotificationTab);

	async function loadNotifications() {
		notificationsLoading = true;
		try {
			const res = await fetch('/api/notifications?limit=50', { credentials: 'include' });
			if (res.ok) {
				notifications = await res.json();
			}
		} catch {
			// Rein lesendes Panel — bei Fehlern lieber leer/ungeändert lassen als kaputt wirken,
			// gleicher Silent-fail-Stil wie der Ungelesen-Zähler
		} finally {
			notificationsLoading = false;
		}
	}

	function toggleNotifications() {
		notificationsOpen = !notificationsOpen;
		if (notificationsOpen) loadNotifications();
	}

	let markingAllRead = false;

	async function handleMarkAllRead() {
		markingAllRead = true;
		try {
			await markAllRead();
			await loadNotifications();
		} finally {
			markingAllRead = false;
		}
	}

	async function openNotification(n: NotificationItem) {
		await fetch(`/api/notifications/${n.id}/read`, { method: 'POST', credentials: 'include' });
		await refreshUnreadCounts();
		notificationsOpen = false;
		if (n.link) goto(n.link);
	}

	function handleUserMenuClickOutside(e: MouseEvent) {
		if (userMenuOpen && !userMenuEl?.contains(e.target as Node)) {
			userMenuOpen = false;
		}
		if (notificationsOpen && !notificationsEl?.contains(e.target as Node)) {
			notificationsOpen = false;
		}
	}

	function handleUserMenuKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			userMenuOpen = false;
			notificationsOpen = false;
		}
	}

	async function logout() {
		userMenuOpen = false;
		stopPolling();
		pollingStarted = false;
		await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
		goto('/login');
	}

	// Routen ohne App-Shell/Session-Prüfung: Login sowie der Self-Service-
	// Passwort-Reset-Flow, den auch ausgeloggte Nutzer über einen E-Mail-Link erreichen.
	const AUTH_ROUTES = ['/login', '/forgot-password', '/reset-password'];

	// Gemeinsames Prädikat statt zweier getrennter Checks (Exact-Match-Array +
	// dupliziertes Inline-if unten in afterNavigate) — /share/[token] ist eine dynamische
	// Route ohne festen Pfad und braucht einen Prefix-Check, kann also nicht einfach ins
	// AUTH_ROUTES-Array aufgenommen werden. Gilt auch für einen im selben Tab bereits
	// eingeloggten Nutzer, der einen eigenen Share-Link testet — rein pfadbasiert, keine
	// Ausnahme für vorhandene Session.
	function isAuthPath(pathname: string): boolean {
		return AUTH_ROUTES.includes(pathname) || pathname.startsWith('/share/');
	}
	$: isAuthRoute = isAuthPath($page.url.pathname);
	$: isSettingsRoute = $page.url.pathname.startsWith('/settings');

	async function refreshCurrentUser() {
		// Security first (Nutzervorgabe 2026-07-23, nach dem Migrations-Vorfall): JEDER
		// nicht-erfolgreiche Ausgang (auch ein unerwarteter 5xx, auch ein Netzwerkfehler)
		// muss zu einem sichtbaren Grund + Redirect zum Login führen — nie zu einer
		// stillschweigend degradierten Oberfläche mit veraltetem/leerem currentUser. Lieber
		// einmal zu oft neu anmelden als einmal zu wenig.
		try {
			const meRes = await fetch('/api/auth/me', { credentials: 'include' });
			if (meRes.ok) {
				currentUser = await meRes.json();
			} else {
				currentUser = null;
				goto(`/login?reason=${meRes.status === 401 ? 'expired' : 'error'}`);
			}
		} catch {
			currentUser = null;
			goto('/login?reason=connection');
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
		if (isAuthPath($page.url.pathname)) {
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

	onDestroy(() => {
		stopPolling();
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
		class="flex h-[72px] flex-none items-center justify-between border-b border-hifi-border bg-hifi-surface px-4 lg:grid lg:grid-cols-[1fr_auto_1fr] lg:px-8"
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

		<!-- Primärnavigation redundant zur Bottom-Tab-Bar unter lg -> dort ausgeblendet
		     statt zusätzlich gequetscht (adaptive-navigation: große Screens Sidebar/Topbar-Nav,
		     kleine Screens Bottom-Nav). -->
		<div class="hidden items-center gap-2 justify-self-center lg:flex">
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
			<!-- Redundant zum "Suche"-Tab der Bottom-Nav unter lg -> dort ausgeblendet statt
			     zusätzlich in die schmale Topbar gequetscht (overflow-menu-Guideline). -->
			<a
				href="/receipts"
				aria-label="Suche"
				class="hidden h-11 w-11 items-center justify-center rounded-[10px] text-hifi-text-muted transition-colors hover:bg-hifi-accent-tint hover:text-hifi-accent-text lg:flex"
			>
				<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<circle cx="10" cy="10" r="6" />
					<path d="M20 20l-5.5-5.5" />
				</svg>
			</a>
			<div class="relative" bind:this={notificationsEl}>
				<button
					on:click={toggleNotifications}
					aria-label={m.notifications.bellAriaLabel}
					aria-expanded={notificationsOpen}
					class="relative flex h-11 w-11 items-center justify-center rounded-[10px] text-hifi-text-muted transition-colors hover:bg-hifi-accent-tint hover:text-hifi-accent-text"
				>
					<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						<path d="M6 10a6 6 0 0112 0v4l2 3H4l2-3z" />
						<path d="M10 20a2 2 0 004 0" />
					</svg>
					{#if $unreadTotal > 0}
						<span
							aria-hidden="true"
							class="absolute -right-0.5 -top-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-danger px-1 text-[10px] font-bold leading-none text-white"
						>
							{$unreadTotal > 9 ? '9+' : $unreadTotal}
						</span>
					{/if}
				</button>
				{#if notificationsOpen}
					<!-- SPRECHBLASEN-FLYOUT (designer-Durchgang v0.34): weichere Elevation via
					     --shadow-popover + größerer Radius (rounded-2xl) heben es bewusst vom flachen
					     Benutzermenü ab. Der Zeiger-Pfeil ist ein um 45° rotiertes Quadrat mit
					     durchlaufendem Hairline-Border (border-l/-t), sodass Bubble-Kontur + Pfeil als
					     eine Form lesen. Horizontale Position: Panel ist right-0 unter der rechtsbündigen
					     Topbar, die Glocke ist 44px breit (Touch-Target-Anhebung) → ihre Mitte liegt 22px
					     vom rechten Rand. Pfeil (10px-Raute) bei right-[17px] → Rauten-Mitte 17+5=22px =
					     exakt Glocken-Mitte, unabhängig von der absoluten Bell-Position (rein
					     rechtsbündig verankert). max-w-[calc(100vw-2rem)] als Sicherheitsnetz gegen
					     Viewport-Überlauf auf sehr schmalen Geräten (320px). -->
					<div
						transition:scale={{ duration: 130, start: 0.96, easing: cubicOut }}
						class="absolute right-0 top-12 z-30 w-80 max-w-[calc(100vw-2rem)] origin-top-right rounded-2xl border border-hifi-border bg-hifi-surface p-1.5 shadow-popover"
					>
						<span
							aria-hidden="true"
							class="absolute -top-[6px] right-[17px] h-2.5 w-2.5 rotate-45 rounded-tl-[3px] border-l border-t border-hifi-border bg-hifi-surface"
						></span>
						{#if $unreadTotal > 0}
							<div class="flex justify-end px-1.5 pt-1">
								<button
									type="button"
									on:click={handleMarkAllRead}
									disabled={markingAllRead}
									class="flex items-center gap-1 rounded-[7px] px-2 py-1 text-[12px] font-semibold text-hifi-accent-text transition-colors hover:bg-hifi-accent-tint disabled:opacity-50"
								>
									<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
										<path d="M2 12l4 4L15 7" />
										<path d="M8 12l4 4L23 5" />
									</svg>
									{markingAllRead ? m.notifications.markAllReadButtonLoading : m.notifications.markAllReadButton}
								</button>
							</div>
						{/if}
						<div class="flex flex-wrap gap-1.5 px-1.5 pb-2 pt-1">
							<button
								type="button"
								on:click={() => (activeNotificationTab = 'all')}
								class="rounded-full px-3.5 py-1.5 text-[13px] font-semibold transition-colors"
								class:bg-hifi-accent-tint={activeNotificationTab === 'all'}
								class:text-hifi-accent-text={activeNotificationTab === 'all'}
								class:bg-hifi-surface={activeNotificationTab !== 'all'}
								class:border={activeNotificationTab !== 'all'}
								class:border-hifi-border={activeNotificationTab !== 'all'}
								class:text-hifi-text-muted={activeNotificationTab !== 'all'}
							>
								{m.notifications.tabAll}
							</button>
							{#each notificationTabs as cat (cat)}
								<button
									type="button"
									on:click={() => (activeNotificationTab = cat)}
									class="rounded-full px-3.5 py-1.5 text-[13px] font-semibold transition-colors"
									class:bg-hifi-accent-tint={activeNotificationTab === cat}
									class:text-hifi-accent-text={activeNotificationTab === cat}
									class:bg-hifi-surface={activeNotificationTab !== cat}
									class:border={activeNotificationTab !== cat}
									class:border-hifi-border={activeNotificationTab !== cat}
									class:text-hifi-text-muted={activeNotificationTab !== cat}
								>
									{notificationCategoryLabel(cat)}
								</button>
							{/each}
						</div>
						<div class="mb-1 h-px bg-hifi-border"></div>
						<div class="max-h-96 overflow-y-auto">
							{#if notificationsLoading}
								<p class="px-3 py-4 text-center text-[13px] text-hifi-text-muted">{m.notifications.loading}</p>
							{:else if filteredNotifications.length === 0}
								<p class="px-3 py-4 text-center text-[13px] text-hifi-text-muted">{m.notifications.empty}</p>
							{:else}
								<ul class="flex flex-col">
									{#each filteredNotifications as n (n.id)}
										<li>
											<button
												type="button"
												on:click={() => openNotification(n)}
												class="flex w-full items-start gap-2.5 rounded-[9px] px-3 py-2.5 text-left transition-colors hover:bg-hifi-accent-tint"
											>
												<span
													aria-hidden="true"
													class="mt-1.5 h-2 w-2 flex-none rounded-full"
													class:bg-hifi-accent={!n.read_at}
												></span>
												<span class="min-w-0 flex-1">
													<span class="block truncate text-[13px] font-semibold text-hifi-text">{n.title}</span>
													<span class="mt-0.5 block text-[12.5px] leading-relaxed text-hifi-text-muted">{n.body}</span>
													<span class="mt-1 block text-[11.5px] text-hifi-text-faint">{formatNotificationTime(n.created_at)}</span>
												</span>
											</button>
										</li>
									{/each}
								</ul>
							{/if}
						</div>
					</div>
				{/if}
			</div>
			<ThemeToggle />
			<div class="mx-1.5 h-[22px] w-px bg-hifi-border"></div>
			<!-- Redundant zum "Einstellungen"-Tab der Bottom-Nav unter lg -> dort ausgeblendet. -->
			<a
				href="/settings"
				aria-label="Einstellungen"
				class="hidden h-11 w-11 items-center justify-center rounded-[10px] text-hifi-text-muted transition-colors hover:bg-hifi-accent-tint hover:text-hifi-accent-text lg:flex"
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
						class="flex h-11 w-11 flex-none items-center justify-center rounded-full bg-hifi-accent-tint text-[12px] font-bold text-hifi-accent-text"
					>
						{userInitial}
					</button>
					{#if userMenuOpen}
						<div
							transition:scale={{ duration: 130, start: 0.96, easing: cubicOut }}
							class="absolute right-0 top-[52px] z-30 w-56 origin-top-right rounded-[14px] border border-hifi-border bg-hifi-surface p-1.5"
						>
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
		<!-- Sidebar (Kategorien bzw. SettingsNav-Desktop-Variante) nur ab lg -- darunter kein
		     Hamburger-Drawer (siehe Plan): Kategorien sind auf /receipts ohnehin als Chips
		     erreichbar, SettingsNav bekommt stattdessen das eigene Mobile-Dropdown unten in
		     <main>. -->
		<aside class="hidden w-[232px] flex-none flex-col overflow-hidden border-r border-hifi-border bg-hifi-surface p-4 py-6 lg:flex">
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

		<main class="min-w-0 flex-1 overflow-y-auto px-4 pb-24 pt-6 sm:px-6 sm:pt-8 lg:px-10 lg:pb-16 lg:pt-9">
			{#if isSettingsRoute}
				<!-- Negative Margins lassen das Dropdown randlos über die volle Breite laufen,
				     trotz des Paddings von <main> -- lg:hidden, weil die Desktop-Sidebar
				     (SettingsNav variant="desktop" oben im <aside>) ab lg dieselbe Aufgabe übernimmt. -->
				<div class="-mx-4 -mt-6 mb-6 border-b border-hifi-border bg-hifi-surface p-4 sm:-mx-6 sm:-mt-8 lg:hidden">
					<SettingsNav {isAdmin} variant="mobile" />
				</div>
			{/if}
			<slot />
		</main>
	</div>

	<!-- Bottom-Tab-Bar: einzige Primärnavigation unter lg (ersetzt die ausgeblendeten
	     Topbar-Links/-Icons), max. 5 Items je bottom-nav-limit-Guideline. Sitzt fest am
	     unteren Rand, env(safe-area-inset-bottom) hält sie über Home-Indicator/Notch
	     (Capacitor-native-App + iOS-Browser) frei. -->
	<nav
		aria-label="Hauptnavigation"
		class="fixed inset-x-0 bottom-0 z-30 flex items-stretch border-t border-hifi-border bg-hifi-surface pb-[env(safe-area-inset-bottom)] lg:hidden"
	>
		<a
			href="/"
			aria-current={$page.url.pathname === '/' ? 'page' : undefined}
			class="flex flex-1 flex-col items-center justify-center gap-0.5 py-2 text-[11px] font-medium transition-colors"
			class:text-hifi-accent-text={$page.url.pathname === '/'}
			class:text-hifi-text-muted={$page.url.pathname !== '/'}
		>
			<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<path d="M3 12l9-9 9 9M5 10v10h14V10" />
			</svg>
			Start
		</a>
		<a
			href="/receipts"
			aria-current={$page.url.pathname.startsWith('/receipts') ? 'page' : undefined}
			class="flex flex-1 flex-col items-center justify-center gap-0.5 py-2 text-[11px] font-medium transition-colors"
			class:text-hifi-accent-text={$page.url.pathname.startsWith('/receipts')}
			class:text-hifi-text-muted={!$page.url.pathname.startsWith('/receipts')}
		>
			<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<circle cx="10" cy="10" r="6" />
				<path d="M20 20l-5.5-5.5" />
			</svg>
			Suche
		</a>
		<a
			href="/upload"
			aria-current={$page.url.pathname.startsWith('/upload') ? 'page' : undefined}
			class="flex flex-1 flex-col items-center justify-center gap-0.5 py-2 text-[11px] font-medium transition-colors"
			class:text-hifi-accent-text={$page.url.pathname.startsWith('/upload')}
			class:text-hifi-text-muted={!$page.url.pathname.startsWith('/upload')}
		>
			<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<path d="M12 16V4M8 8l4-4 4 4" />
				<path d="M4 16v3a2 2 0 002 2h12a2 2 0 002-2v-3" />
			</svg>
			Hochladen
		</a>
		<a
			href="/buckets"
			aria-current={$page.url.pathname.startsWith('/buckets') ? 'page' : undefined}
			class="flex flex-1 flex-col items-center justify-center gap-0.5 py-2 text-[11px] font-medium transition-colors"
			class:text-hifi-accent-text={$page.url.pathname.startsWith('/buckets')}
			class:text-hifi-text-muted={!$page.url.pathname.startsWith('/buckets')}
		>
			<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<path d="M5 8h14l-1.5 11a2 2 0 01-2 1.8H8.5a2 2 0 01-2-1.8L5 8z" />
				<path d="M8 8a4 4 0 018 0" />
			</svg>
			Buckets
		</a>
		<a
			href="/settings"
			aria-current={isSettingsRoute ? 'page' : undefined}
			class="flex flex-1 flex-col items-center justify-center gap-0.5 py-2 text-[11px] font-medium transition-colors"
			class:text-hifi-accent-text={isSettingsRoute}
			class:text-hifi-text-muted={!isSettingsRoute}
		>
			<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<circle cx="12" cy="12" r="3" />
				<path
					d="M19.4 15a1.7 1.7 0 00.34 1.87l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.7 1.7 0 00-1.87-.34 1.7 1.7 0 00-1 1.55V21a2 2 0 01-4 0v-.09a1.7 1.7 0 00-1-1.55 1.7 1.7 0 00-1.87.34l-.06.06a2 2 0 11-2.83-2.83l.06-.06A1.7 1.7 0 004.6 15a1.7 1.7 0 00-1.55-1H3a2 2 0 010-4h.09A1.7 1.7 0 004.6 9a1.7 1.7 0 00-.34-1.87l-.06-.06a2 2 0 112.83-2.83l.06.06A1.7 1.7 0 009 4.6a1.7 1.7 0 001-1.55V3a2 2 0 014 0v.09a1.7 1.7 0 001 1.55 1.7 1.7 0 001.87-.34l.06-.06a2 2 0 112.83 2.83l-.06.06A1.7 1.7 0 0019.4 9a1.7 1.7 0 001.55 1H21a2 2 0 010 4h-.09a1.7 1.7 0 00-1.55 1z"
					stroke-linecap="round"
					stroke-linejoin="round"
				/>
			</svg>
			Einstellungen
		</a>
	</nav>
</div>
{/if}
