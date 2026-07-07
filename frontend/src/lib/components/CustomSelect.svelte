<script lang="ts">
	export let value: string;
	export let options: { value: string; label: string }[];
	export let placeholder = 'Bitte wählen';
	export let disabled = false;
	export let labelledBy: string | undefined = undefined;

	let open = false;
	let triggerEl: HTMLButtonElement;
	let listEl: HTMLUListElement;
	let highlightedIndex = -1;

	$: selectedLabel = options.find((o) => o.value === value)?.label ?? placeholder;

	function toggle() {
		if (disabled) return;
		open = !open;
		if (open) {
			highlightedIndex = options.findIndex((o) => o.value === value);
			queueMicrotask(() => scrollHighlightedIntoView());
		}
	}

	function close() {
		open = false;
	}

	function selectOption(opt: { value: string; label: string }) {
		value = opt.value;
		close();
		triggerEl?.focus();
	}

	function scrollHighlightedIntoView() {
		listEl?.querySelector('[data-highlighted="true"]')?.scrollIntoView({ block: 'nearest' });
	}

	function handleTriggerKeydown(e: KeyboardEvent) {
		if (!open) {
			if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown' || e.key === 'ArrowUp') {
				e.preventDefault();
				toggle();
			}
			return;
		}
		handleListKeydown(e);
	}

	function handleListKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			e.preventDefault();
			close();
			triggerEl?.focus();
		} else if (e.key === 'ArrowDown') {
			e.preventDefault();
			highlightedIndex = Math.min(highlightedIndex + 1, options.length - 1);
			scrollHighlightedIntoView();
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			highlightedIndex = Math.max(highlightedIndex - 1, 0);
			scrollHighlightedIntoView();
		} else if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			if (highlightedIndex >= 0) selectOption(options[highlightedIndex]);
		} else if (e.key === 'Tab') {
			close();
		}
	}

	function handleClickOutside(e: MouseEvent) {
		if (!open) return;
		const target = e.target as Node;
		if (!triggerEl?.contains(target) && !listEl?.contains(target)) {
			close();
		}
	}
</script>

<svelte:window on:click={handleClickOutside} />

<div class="relative">
	<button
		type="button"
		bind:this={triggerEl}
		on:click={toggle}
		on:keydown={handleTriggerKeydown}
		{disabled}
		class="flex w-full items-center justify-between rounded border border-border bg-surface p-2 text-left text-sm transition-colors hover:border-text-muted disabled:opacity-50"
		aria-haspopup="listbox"
		aria-expanded={open}
		aria-labelledby={labelledBy}
	>
		<span class:text-text-muted={!options.some((o) => o.value === value)}>{selectedLabel}</span>
		<svg
			width="14"
			height="14"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			stroke-width="2"
			class="shrink-0 text-text-muted"
			class:rotate-180={open}
			aria-hidden="true"
		>
			<path d="M6 9l6 6 6-6" />
		</svg>
	</button>

	{#if open}
		<ul
			bind:this={listEl}
			role="listbox"
			tabindex="-1"
			on:keydown={handleListKeydown}
			class="absolute z-20 mt-1 max-h-60 w-full overflow-auto rounded border border-border bg-surface py-1 text-sm"
		>
			{#each options as opt, i (opt.value)}
				<li role="presentation">
					<button
						type="button"
						role="option"
						aria-selected={opt.value === value}
						data-highlighted={i === highlightedIndex}
						on:click={() => selectOption(opt)}
						on:mouseenter={() => (highlightedIndex = i)}
						class="block w-full px-3 py-2 text-left transition-colors"
						class:bg-surface-raised={i === highlightedIndex}
						class:font-medium={opt.value === value}
					>
						{opt.label}
					</button>
				</li>
			{/each}
		</ul>
	{/if}
</div>
