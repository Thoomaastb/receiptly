<script lang="ts">
	import { TAG_COLOR_KEYS, tagColorVar } from '$lib/tags';
	import { m } from '$lib/i18n';

	export let value: string;

	let swatchEls: (HTMLButtonElement | null)[] = [];

	// Natives Radiogroup-Verhalten: Pfeiltasten bewegen Fokus UND Auswahl gemeinsam (wie bei
	// <input type="radio">-Gruppen), kein separates "Bestätigen" nötig — ein Klick/Enter/Space
	// auf einen Swatch wählt ihn direkt (siehe on:click, native Button-Semantik deckt
	// Enter/Space bereits ab).
	function handleKeydown(e: KeyboardEvent, index: number) {
		let nextIndex = index;
		if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
			nextIndex = (index + 1) % TAG_COLOR_KEYS.length;
		} else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
			nextIndex = (index - 1 + TAG_COLOR_KEYS.length) % TAG_COLOR_KEYS.length;
		} else {
			return;
		}
		e.preventDefault();
		value = TAG_COLOR_KEYS[nextIndex];
		swatchEls[nextIndex]?.focus();
	}
</script>

<div role="radiogroup" aria-label={m.tags.colorPicker.groupLabel} class="grid grid-cols-6 gap-2.5 sm:grid-cols-8">
	{#each TAG_COLOR_KEYS as key, i (key)}
		<!-- Selected-State: neutraler Ring (text-hifi) + Häkchen — bewusst NICHT die Accent-Farbe,
		     damit "ausgewählt" sich klar vom Accent-Focus-Ring unterscheidet; das Häkchen erfüllt
		     color-not-only (Auswahl nicht allein über Ringfarbe kommunizieren). Ring-Offset-Farbe
		     explizit auf die Surface gesetzt, sonst rendert der Offset-Spalt im Dark Mode weiß. -->
		<button
			bind:this={swatchEls[i]}
			type="button"
			role="radio"
			aria-checked={value === key}
			aria-label={m.tags.colorPicker.swatchAriaLabel.replace('{n}', String(i + 1))}
			tabindex={value === key ? 0 : -1}
			on:click={() => (value = key)}
			on:keydown={(e) => handleKeydown(e, i)}
			class="relative h-9 w-9 rounded-full border border-hifi-border transition-transform duration-150 ease-out hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-hifi-accent focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--color-surface-hifi)]"
			class:ring-2={value === key}
			class:ring-offset-2={value === key}
			class:ring-offset-[color:var(--color-surface-hifi)]={value === key}
			class:ring-[color:var(--color-text-hifi)]={value === key}
			style="background: {tagColorVar(key)};"
		>
			{#if value === key}
				<svg
					class="pointer-events-none absolute inset-0 m-auto h-4 w-4 text-white [filter:drop-shadow(0_0_1.5px_rgba(0,0,0,0.55))]"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="3"
					stroke-linecap="round"
					stroke-linejoin="round"
					aria-hidden="true"
				>
					<path d="M5 13l4 4L19 7" />
				</svg>
			{/if}
		</button>
	{/each}
</div>
