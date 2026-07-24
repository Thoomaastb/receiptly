<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import CustomSelect from './CustomSelect.svelte';

	export let isAdmin: boolean;
	// 'desktop' (Standard): bestehende Vertikal-Liste für die feste Sidebar (>= lg).
	// 'mobile': Dropdown-Ersatz, den +layout.svelte oberhalb des Seiteninhalts einblendet,
	// weil die Sidebar selbst unter lg komplett ausgeblendet ist (kein Hamburger-Drawer,
	// siehe Plan) -- beide Varianten teilen dieselben items/adminItems, keine doppelte Liste.
	export let variant: 'desktop' | 'mobile' = 'desktop';

	const items: { href: string; label: string }[] = [
		{ href: '/settings/profile', label: 'Profil' },
		{ href: '/settings/appearance', label: 'Darstellung' },
		{ href: '/settings/localization', label: 'Lokalisation' },
		{ href: '/settings/security', label: 'Sicherheit' },
		{ href: '/settings/account', label: 'Konto' },
		{ href: '/settings/notifications', label: 'Benachrichtigungen' }
	];

	const adminItems: { href: string; label: string }[] = [
		{ href: '/settings/ai-provider', label: 'KI-Provider' },
		{ href: '/settings/smtp', label: 'E-Mail-Versand' },
		{ href: '/settings/security-policy', label: 'Sicherheitsrichtlinien' }
	];

	$: pathname = $page.url.pathname;

	// Admin-Einträge bekommen im Dropdown-Label einen sichtbaren Suffix statt einer
	// eigenen optgroup (CustomSelect kennt keine Gruppen) -- die Desktop-<nav> unten löst
	// dieselbe Unterscheidung stattdessen über die "Admin-Bereich"-Zwischenüberschrift.
	$: mobileOptions = [
		...items.map((i) => ({ value: i.href, label: i.label })),
		...(isAdmin ? adminItems.map((i) => ({ value: i.href, label: `${i.label} · Admin` })) : [])
	];
	$: currentHref = mobileOptions.find((o) => pathname.startsWith(o.value))?.value ?? '';

	// CustomSelect hat kein eigenes on:change -- es mutiert nur den gebundenen value-Prop
	// direkt (siehe CustomSelect.svelte::selectOption). Diese Zeile hält die Auswahl mit
	// der Route synchron, AUCH wenn sich pathname von außen ändert (z.B. Browser-Zurück).
	let mobileSelected = '';
	$: mobileSelected = currentHref;

	// Navigiert nur, wenn die Auswahl vom aktuell aktiven Eintrag abweicht -- verhindert
	// eine Schleife mit der Sync-Zeile oben (currentHref -> mobileSelected -> hier -> goto
	// -> pathname ändert sich -> currentHref ändert sich -> ...), die sonst bei jeder
	// Navigation erneut anspringen würde.
	$: if (mobileSelected && mobileSelected !== currentHref) {
		goto(mobileSelected);
	}
</script>

{#if variant === 'mobile'}
	<div>
		<span id="settings-mobile-nav-label" class="mb-1 block text-[11.5px] font-bold uppercase tracking-[0.04em] text-hifi-text-faint">
			Einstellungen
		</span>
		<CustomSelect
			bind:value={mobileSelected}
			labelledBy="settings-mobile-nav-label"
			options={mobileOptions}
		/>
	</div>
{:else}
	<nav class="flex flex-col gap-0.5" aria-label="Einstellungen">
		<div class="px-3 pb-2 text-[11.5px] font-bold uppercase tracking-[0.04em] text-hifi-text-faint">
			Einstellungen
		</div>
		{#each items as item (item.href)}
			<a
				href={item.href}
				class="rounded-[9px] px-3 py-2 text-[13.5px] font-medium transition-colors hover:bg-hifi-accent-tint hover:text-hifi-accent-text"
				class:bg-hifi-accent-tint={pathname.startsWith(item.href)}
				class:text-hifi-accent-text={pathname.startsWith(item.href)}
				class:text-hifi-text-muted={!pathname.startsWith(item.href)}
			>
				{item.label}
			</a>
		{/each}

		{#if isAdmin}
			<div class="my-2 h-px bg-hifi-border"></div>
			<div class="px-3 pb-2 text-[11.5px] font-bold uppercase tracking-[0.04em] text-hifi-text-faint">
				Admin-Bereich
			</div>
			{#each adminItems as item (item.href)}
				<a
					href={item.href}
					class="rounded-[9px] px-3 py-2 text-[13.5px] font-medium transition-colors hover:bg-hifi-accent-tint hover:text-hifi-accent-text"
					class:bg-hifi-accent-tint={pathname.startsWith(item.href)}
					class:text-hifi-accent-text={pathname.startsWith(item.href)}
					class:text-hifi-text-muted={!pathname.startsWith(item.href)}
				>
					{item.label}
				</a>
			{/each}
		{/if}
	</nav>
{/if}
