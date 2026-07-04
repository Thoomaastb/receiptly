<script lang="ts">
	import { onMount } from 'svelte';
	import '../app.css';
	import { page } from '$app/stores';
	import { fly } from 'svelte/transition';
	import { cubicOut } from 'svelte/easing';

	const reducedMotion =
		typeof window !== 'undefined' &&
		window.matchMedia('(prefers-reduced-motion: reduce)').matches;

	const transitionDuration = reducedMotion ? 0 : 180;

	// Kategorien kommen aus merchant.category — aktuell noch leer, da Auto-Tagging
	// (KI-Provider-Paket) noch nicht gebaut ist. Ehrlicher Leer-Zustand statt Fake-Daten.
	let categories: { name: string; color: string; count: number }[] = [];
	let expiringWarrantiesCount = 0;
	let categoriesLoading = true;

	onMount(async () => {
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

<div class="min-h-screen bg-hifi-bg font-ui text-hifi-text" style="color-scheme: light;">
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
				Belege
			</a>
			<a href="/buckets" class="rounded-[10px] px-4 py-2 text-[14.5px] font-semibold text-hifi-text-muted transition-colors hover:text-hifi-text">
				Buckets
			</a>
		</div>

		<div class="flex items-center gap-1.5 justify-self-end">
			<button
				aria-label="Suche"
				class="flex h-[38px] w-[38px] items-center justify-center rounded-[10px] text-hifi-text-muted transition-colors hover:bg-hifi-accent-tint hover:text-hifi-accent-text"
			>
				<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<circle cx="10" cy="10" r="6" />
					<path d="M20 20l-5.5-5.5" />
				</svg>
			</button>
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
			{#key $page.url.pathname}
				<div
					in:fly={{ y: 8, duration: transitionDuration, easing: cubicOut }}
					out:fly={{ y: -8, duration: transitionDuration, easing: cubicOut }}
				>
					<slot />
				</div>
			{/key}
		</main>
	</div>
</div>
