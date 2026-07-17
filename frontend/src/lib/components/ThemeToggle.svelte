<script lang="ts">
	import { getStoredPreference, setPreference, resolveEffectiveTheme, type ThemePreference } from '$lib/theme';

	// getStoredPreference() ist SSR-sicher (guardet auf typeof localStorage), daher
	// hier ohne onMount direkt lesbar.
	let preference: ThemePreference = getStoredPreference();
	let open = false;
	let menuEl: HTMLDivElement;

	// Icon folgt dem EFFEKTIVEN Theme (System löst sich sichtbar zu Sonne/Mond auf),
	// das Dropdown selbst markiert aber weiterhin, ob "System" explizit gewählt ist.
	$: effective = resolveEffectiveTheme(preference);

	const options: { value: ThemePreference; label: string }[] = [
		{ value: 'system', label: 'System' },
		{ value: 'light', label: 'Hell' },
		{ value: 'dark', label: 'Dunkel' }
	];

	function choose(pref: ThemePreference) {
		preference = pref;
		setPreference(pref);
		open = false;
	}

	function toggleOpen() {
		open = !open;
	}

	function handleClickOutside(e: MouseEvent) {
		if (!open) return;
		if (!menuEl?.contains(e.target as Node)) {
			open = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') open = false;
	}
</script>

<svelte:window on:click={handleClickOutside} on:keydown={handleKeydown} />

<div class="relative" bind:this={menuEl}>
	<button
		on:click={toggleOpen}
		aria-label="Darstellung ändern"
		aria-haspopup="true"
		aria-expanded={open}
		class="flex h-[38px] w-[38px] items-center justify-center rounded-[10px] text-hifi-text-muted transition-colors hover:bg-hifi-accent-tint hover:text-hifi-accent-text"
	>
		{#if preference === 'system'}
			<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<rect x="3" y="4" width="18" height="12" rx="2" />
				<path d="M8 20h8M12 16v4" />
			</svg>
		{:else if effective === 'dark'}
			<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<path d="M20 14.5A8.5 8.5 0 019.5 4a8.5 8.5 0 1010.5 10.5z" />
			</svg>
		{:else}
			<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<circle cx="12" cy="12" r="4.5" />
				<path d="M12 2.5v2.2M12 19.3v2.2M4.9 4.9l1.55 1.55M17.55 17.55l1.55 1.55M2.5 12h2.2M19.3 12h2.2M4.9 19.1l1.55-1.55M17.55 6.45l1.55-1.55" />
			</svg>
		{/if}
	</button>

	{#if open}
		<div
			class="absolute right-0 top-[38px] z-30 w-44 rounded-[14px] border border-hifi-border bg-hifi-surface p-1.5"
			role="menu"
		>
			{#each options as option (option.value)}
				<button
					role="menuitemradio"
					aria-checked={preference === option.value}
					on:click={() => choose(option.value)}
					class="flex w-full items-center justify-between gap-2 rounded-[9px] px-3 py-2 text-left text-[13px] font-medium text-hifi-text transition-colors hover:bg-hifi-accent-tint"
				>
					{option.label}
					{#if preference === option.value}
						<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="text-hifi-accent-text">
							<path d="M20 6L9 17l-5-5" />
						</svg>
					{/if}
				</button>
			{/each}
		</div>
	{/if}
</div>
