<script lang="ts">
	import { themePreference, effectiveTheme, setPreference, type ThemePreference } from '$lib/theme';

	// Das Icon zeigt IMMER das effektive Theme (Sonne/Mond) — auch bei "System" wird
	// direkt das gerade aktive Theme angezeigt, kein eigenes drittes Icon dafür. Das
	// Dropdown markiert zusätzlich, welche Präferenz explizit gewählt ist.
	let open = false;
	let menuEl: HTMLDivElement;

	const options: { value: ThemePreference; label: string }[] = [
		{ value: 'system', label: 'System' },
		{ value: 'light', label: 'Hell' },
		{ value: 'dark', label: 'Dunkel' }
	];

	function choose(pref: ThemePreference) {
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
		class="flex h-11 w-11 items-center justify-center rounded-[10px] text-hifi-text-muted transition-colors hover:bg-hifi-accent-tint hover:text-hifi-accent-text"
	>
		{#if $effectiveTheme === 'dark'}
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
			class="absolute right-0 top-11 z-30 w-44 rounded-[14px] border border-hifi-border bg-hifi-surface p-1.5"
			role="menu"
		>
			{#each options as option (option.value)}
				<button
					role="menuitemradio"
					aria-checked={$themePreference === option.value}
					on:click={() => choose(option.value)}
					class="flex w-full items-center justify-between gap-2 rounded-[9px] px-3 py-2 text-left text-[13px] font-medium text-hifi-text transition-colors hover:bg-hifi-accent-tint"
				>
					{option.label}
					{#if $themePreference === option.value}
						<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="text-hifi-accent-text">
							<path d="M20 6L9 17l-5-5" />
						</svg>
					{/if}
				</button>
			{/each}
		</div>
	{/if}
</div>
