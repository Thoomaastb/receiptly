<script lang="ts">
	import { page } from '$app/stores';

	export let isAdmin: boolean;

	const items: { href: string; label: string }[] = [
		{ href: '/settings/profile', label: 'Profil' },
		{ href: '/settings/localization', label: 'Lokalisation' },
		{ href: '/settings/security', label: 'Sicherheit' }
	];

	const adminItems: { href: string; label: string }[] = [
		{ href: '/settings/ai-provider', label: 'KI-Provider' }
	];

	$: pathname = $page.url.pathname;
</script>

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
