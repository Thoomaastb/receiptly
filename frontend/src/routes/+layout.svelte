<script lang="ts">
	import { onMount } from 'svelte';
	import '../app.css';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';

	// Kategorien kommen aus merchant.category — aktuell noch leer, da Auto-Tagging
	// (KI-Provider-Paket) noch nicht gebaut ist. Ehrlicher Leer-Zustand statt Fake-Daten.
	let categories: { name: string; color: string; count: number }[] = [];
	let expiringWarrantiesCount = 0;
	let categoriesLoading = true;

	let currentUser: { username: string; email: string; role: string } | null = null;
	$: userInitial = (currentUser?.username?.[0] ?? '?').toUpperCase();

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

	$: isAuthRoute = $page.url.pathname === '/login';

	onMount(async () => {
		if (isAuthRoute) return;

		try {
			const meRes = await fetch('/api/auth/me', { credentials: 'include' });
			if (meRes.ok) {
				currentUser = await meRes.json();
			} else if (meRes.status === 401) {
				goto('/login');
				return;
			}
		} catch {
			// Avatar bleibt leer, wenn nicht eingeloggt — kein Fehler-UI nötig für dieses Detail
		}

		try {
			const healthRes = await fetch('/api/health');
			if (healthRes.ok) {
				const health = await healthRes.json();
				appVersion = health.version ?? '';
			}
		} catch {
			// Versionsanzeige ist rein informativ — kein Fehler-UI nötig für dieses Detail
		}

		try {
			const res = await fetch('/api/receipts', { credentials: 'include' });
			if (res.ok) {
				const receipts = await res.json();
				// Garantie-Ablauf-Zählung: real berechnet, aber aktuell immer 0,
				// da warranty_expires_at noch nirgends befüllt wird (Dokumente-&-Garantie-Paket offen)
				const now = Date.now();
				expiringWarrantiesCount = receipts.filter((r: { warranty_expires_at?: string }) => {
					if (!r.warranty_expires_at) return false;
					const days = (new Date(r.warranty_expires_at).getTime() - now) / 86_400_000;
					return days <= 30;
				}).length;
			}
		} finally {
			categoriesLoading = false;
		}
	});
</script>

<svelte:window on:click={handleUserMenuClickOutside} on:keydown={handleUserMenuKeydown} />

{#if isAuthRoute}
	<slot />
{:else}
<div class="flex min-h-screen flex-col bg-hifi-bg font-ui text-hifi-text" style="color-scheme: light;">
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
			<a href="/buckets" class="rounded-[10px] px-4 py-2 text-[14.5px] font-semibold text-hifi-text-muted transition-colors hover:text-hifi-text">
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
							<a
								href="/settings"
								on:click={() => (userMenuOpen = false)}
								class="flex w-full items-center gap-2 rounded-[9px] px-3 py-2 text-left text-[13px] font-medium text-hifi-text transition-colors hover:bg-hifi-accent-tint"
							>
								<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
									<circle cx="12" cy="12" r="3" />
									<path
										d="M19.4 15a1.7 1.7 0 00.34 1.87l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.7 1.7 0 00-1.87-.34 1.7 1.7 0 00-1 1.55V21a2 2 0 01-4 0v-.09a1.7 1.7 0 00-1-1.55 1.7 1.7 0 00-1.87.34l-.06.06a2 2 0 11-2.83-2.83l.06-.06A1.7 1.7 0 004.6 15a1.7 1.7 0 00-1.55-1H3a2 2 0 010-4h.09A1.7 1.7 0 004.6 9a1.7 1.7 0 00-.34-1.87l-.06-.06a2 2 0 112.83-2.83l.06.06A1.7 1.7 0 009 4.6a1.7 1.7 0 001-1.55V3a2 2 0 014 0v.09a1.7 1.7 0 001 1.55 1.7 1.7 0 001.87-.34l.06-.06a2 2 0 112.83 2.83l-.06.06A1.7 1.7 0 0019.4 9a1.7 1.7 0 001.55 1H21a2 2 0 010 4h-.09a1.7 1.7 0 00-1.55 1z"
										stroke-linecap="round"
										stroke-linejoin="round"
									/>
								</svg>
								Einstellungen
							</a>
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
		<aside class="flex w-[232px] flex-none flex-col gap-6 border-r border-hifi-border bg-hifi-surface p-4 py-6">
			<div class="flex flex-col gap-0.5">
				<div class="px-3 pb-2 text-[11.5px] font-bold uppercase tracking-[0.04em] text-hifi-text-faint">
					Kategorien
				</div>
				{#if categoriesLoading}
					<div class="px-3 py-2 text-[13px] text-hifi-text-faint">Wird geladen …</div>
				{:else if categories.length === 0}
					<div class="px-3 py-2 text-[12.5px] leading-relaxed text-hifi-text-faint">
						Noch keine Kategorien — die kommen automatisch, sobald die KI-Auto-Verschlagwortung
						läuft.
					</div>
				{:else}
					{#each categories as cat (cat.name)}
						<button class="flex items-center gap-2.5 rounded-[9px] px-3 py-2 text-left text-[13.5px] font-medium text-hifi-text transition-colors hover:bg-hifi-accent-tint">
							<span class="h-2 w-2 flex-none rounded-full" style="background: {cat.color}"></span>
							<span class="flex-1">{cat.name}</span>
							<span class="font-mono text-xs text-hifi-text-faint">{cat.count}</span>
						</button>
					{/each}
				{/if}
			</div>

			<div class="mt-auto flex flex-col gap-1.5 rounded-[14px] bg-hifi-accent-tint p-3.5">
				<div class="flex items-center gap-1.5 text-[12.5px] font-bold text-hifi-accent-text">
					<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						<path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z" />
					</svg>
					KI-Analyse
				</div>
				<div class="text-[12.5px] leading-relaxed" style="color: oklch(40% 0.05 290);">
					{expiringWarrantiesCount}
					{expiringWarrantiesCount === 1 ? 'Garantie braucht' : 'Garantien brauchen'} Aufmerksamkeit
				</div>
			</div>
		</aside>

		<main class="min-w-0 flex-1 overflow-y-auto px-10 pb-16 pt-9">
			<slot />
		</main>
	</div>
</div>
{/if}
