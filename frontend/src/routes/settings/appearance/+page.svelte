<script lang="ts">
	import { getStoredPreference, setPreference, type ThemePreference } from '$lib/theme';

	let preference: ThemePreference = getStoredPreference();

	const options: { value: ThemePreference; label: string; description: string }[] = [
		{
			value: 'system',
			label: 'System',
			description: 'Folgt automatisch der Einstellung deines Geräts.'
		},
		{ value: 'light', label: 'Hell', description: 'Immer das helle Farbschema verwenden.' },
		{ value: 'dark', label: 'Dunkel', description: 'Immer das dunkle Farbschema verwenden.' }
	];

	function choose(pref: ThemePreference) {
		preference = pref;
		setPreference(pref);
	}

	function handleKeydown(e: KeyboardEvent, index: number) {
		if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
		e.preventDefault();
		const next = e.key === 'ArrowDown' ? (index + 1) % options.length : (index - 1 + options.length) % options.length;
		choose(options[next].value);
		(document.getElementById(`appearance-option-${options[next].value}`) as HTMLElement | null)?.focus();
	}
</script>

<div class="max-w-2xl rounded-[14px] border border-hifi-border bg-hifi-surface p-6">
	<h2 class="mb-1 text-[13.5px] font-bold text-hifi-text">Darstellung</h2>
	<p class="mb-4 text-sm text-hifi-text-muted">
		Legt fest, ob receiptly im hellen oder dunklen Farbschema angezeigt wird. Die Einstellung gilt nur auf diesem Gerät.
	</p>

	<div class="flex flex-col gap-2" role="radiogroup" aria-label="Darstellung">
		{#each options as option, index (option.value)}
			<button
				id="appearance-option-{option.value}"
				role="radio"
				aria-checked={preference === option.value}
				on:click={() => choose(option.value)}
				on:keydown={(e) => handleKeydown(e, index)}
				class="flex items-start justify-between gap-4 rounded-[10px] border px-4 py-3 text-left transition-colors"
				class:border-hifi-accent={preference === option.value}
				class:bg-hifi-accent-tint={preference === option.value}
				class:border-hifi-border={preference !== option.value}
			>
				<span>
					<span class="block text-[13.5px] font-semibold text-hifi-text">{option.label}</span>
					<span class="block text-[12.5px] text-hifi-text-muted">{option.description}</span>
				</span>
				{#if preference === option.value}
					<svg
						width="16"
						height="16"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2.2"
						stroke-linecap="round"
						stroke-linejoin="round"
						aria-hidden="true"
						class="mt-0.5 flex-none text-hifi-accent-text"
					>
						<path d="M20 6L9 17l-5-5" />
					</svg>
				{/if}
			</button>
		{/each}
	</div>
</div>
