<script lang="ts">
	export let icon: 'home' | 'lock';
	export let name: string;
	export let count: number;
	export let sum: number;
	export let currency: string = 'EUR';
	export let expanded = true;
</script>

<button
	class="flex w-full items-center justify-between border-b border-border py-3 text-left"
	on:click={() => (expanded = !expanded)}
	aria-expanded={expanded}
>
	<div class="flex items-center gap-2">
		{#if icon === 'home'}
			<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-text-muted" aria-hidden="true">
				<path d="M3 12l9-9 9 9M5 10v10h14V10" />
			</svg>
		{:else}
			<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-text-muted" aria-hidden="true">
				<rect x="5" y="11" width="14" height="10" rx="1" />
				<path d="M8 11V7a4 4 0 018 0v4" />
			</svg>
		{/if}
		<span class="text-sm font-medium">{name}</span>
		<span class="text-xs text-text-muted">
			{count}
			{count === 1 ? 'Beleg' : 'Belege'} · {sum.toFixed(2)}
			{currency}
		</span>
	</div>
	<svg
		width="14"
		height="14"
		viewBox="0 0 24 24"
		fill="none"
		stroke="currentColor"
		stroke-width="2"
		class="text-text-muted transition-transform"
		class:rotate-180={!expanded}
		aria-hidden="true"
	>
		<path d="M6 9l6 6 6-6" />
	</svg>
</button>
