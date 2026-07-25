<script lang="ts">
	import { onMount } from 'svelte';
	import { tagColorVar, TAG_COLOR_KEYS, type Tag } from '$lib/tags';
	import { m } from '$lib/i18n';
	import TagColorSwatchPicker from './TagColorSwatchPicker.svelte';

	// Zuweisung: bind:selectedTagIds, komplette Tag-Liste des Haushalts wird selbst geladen
	// (siehe unten) statt vom Elternteil durchgereicht — macht die Komponente unabhängig vom
	// Aufrufkontext wiederverwendbar, ohne dass ReceiptDetailView eine zusätzliche
	// allTags-Prop pflegen muss (getrennt von der Filter-Zeile auf /receipts, die ihre eigene
	// Kopie lädt, siehe routes/receipts/+page.svelte).
	export let selectedTagIds: string[] = [];

	// Eindeutige DOM-IDs pro Instanz (mehrere TagPicker theoretisch gleichzeitig denkbar) —
	// verhindert doppelte IDs bei ARIA-Referenzen (aria-controls/aria-activedescendant).
	const uid = Math.random().toString(36).slice(2);

	let availableTags: Tag[] = [];
	let loadingTags = true;
	let loadError = '';

	async function loadTags() {
		loadingTags = true;
		loadError = '';
		try {
			const res = await fetch('/api/tags', { credentials: 'include' });
			if (!res.ok) throw new Error();
			availableTags = await res.json();
		} catch {
			loadError = m.tags.picker.loadError;
		} finally {
			loadingTags = false;
		}
	}

	onMount(loadTags);

	$: selectedTags = selectedTagIds
		.map((id) => availableTags.find((t) => t.id === id))
		.filter((t): t is Tag => !!t);

	let query = '';
	let open = false;
	let highlightedIndex = -1;
	let inputEl: HTMLInputElement;
	let containerEl: HTMLDivElement;

	$: normalizedQuery = query.trim().toLowerCase();
	$: suggestions = availableTags.filter(
		(t) => !selectedTagIds.includes(t.id) && t.name.toLowerCase().includes(normalizedQuery)
	);
	$: exactMatch = suggestions.find((t) => t.name.toLowerCase() === normalizedQuery);
	$: showCreateOption = normalizedQuery.length > 0 && !exactMatch;

	function removeTag(id: string) {
		selectedTagIds = selectedTagIds.filter((t) => t !== id);
	}

	function addTag(tag: Tag) {
		if (!selectedTagIds.includes(tag.id)) selectedTagIds = [...selectedTagIds, tag.id];
		query = '';
		highlightedIndex = -1;
		inputEl?.focus();
	}

	function openDropdown() {
		open = true;
		highlightedIndex = -1;
	}

	// --- Freitext "+ Neuer Tag" -> Swatch-Picker -> POST /api/tags (Get-or-Create) ---
	let creatingName = '';
	let newTagColor: string = TAG_COLOR_KEYS[0];
	let creating = false;
	let createError = '';

	function startCreate(name: string) {
		const trimmed = name.trim();
		if (!trimmed) return;
		creatingName = trimmed;
		newTagColor = TAG_COLOR_KEYS[0];
		createError = '';
	}

	function cancelCreate() {
		creatingName = '';
		createError = '';
	}

	function closeDropdown() {
		open = false;
		highlightedIndex = -1;
		cancelCreate();
	}

	async function confirmCreate() {
		if (!creatingName) return;
		creating = true;
		createError = '';
		try {
			const res = await fetch('/api/tags', {
				method: 'POST',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ name: creatingName, color: newTagColor })
			});
			if (!res.ok) throw new Error();
			const created: Tag = await res.json();
			if (!availableTags.some((t) => t.id === created.id)) {
				availableTags = [...availableTags, created].sort((a, b) => a.name.localeCompare(b.name));
			}
			creatingName = '';
			addTag(created);
		} catch {
			createError = m.tags.picker.createError;
		} finally {
			creating = false;
		}
	}

	function handleInputKeydown(e: KeyboardEvent) {
		if (creatingName) return; // Swatch-Picker hat währenddessen die Tastaturhoheit
		const optionCount = suggestions.length + (showCreateOption ? 1 : 0);
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			if (!open) {
				openDropdown();
				return;
			}
			highlightedIndex = Math.min(highlightedIndex + 1, optionCount - 1);
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			highlightedIndex = Math.max(highlightedIndex - 1, 0);
		} else if (e.key === 'Enter') {
			e.preventDefault();
			if (highlightedIndex >= 0 && highlightedIndex < suggestions.length) {
				addTag(suggestions[highlightedIndex]);
			} else if (highlightedIndex === suggestions.length && showCreateOption) {
				startCreate(query);
			} else if (exactMatch) {
				addTag(exactMatch);
			} else if (query.trim()) {
				startCreate(query);
			}
		} else if (e.key === 'Escape') {
			if (open) {
				e.preventDefault();
				closeDropdown();
			}
		} else if (e.key === 'Backspace' && !query && selectedTagIds.length > 0) {
			// Letzten Chip per Backspace entfernen, wenn das Eingabefeld bereits leer ist —
			// gängiges Muster bei Chip-Eingaben, spart einen Extra-Klick auf das ✕.
			removeTag(selectedTagIds[selectedTagIds.length - 1]);
		}
	}

	function handleClickOutside(e: MouseEvent) {
		if (!open && !creatingName) return;
		const target = e.target as Node;
		if (!containerEl?.contains(target)) closeDropdown();
	}
</script>

<svelte:window on:click={handleClickOutside} />

<div class="relative" bind:this={containerEl}>
	<span id="tag-picker-label-{uid}" class="mb-1 block text-xs text-hifi-text-muted">{m.tags.picker.fieldLabel}</span>

	<div class="flex flex-wrap items-center gap-1.5 rounded border border-hifi-border bg-hifi-surface p-2">
		{#each selectedTags as tag (tag.id)}
			<span
				class="flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium text-white"
				style="background: {tagColorVar(tag.color)};"
			>
				{tag.name}
				<button
					type="button"
					on:click={() => removeTag(tag.id)}
					aria-label={m.tags.picker.removeAriaLabel.replace('{name}', tag.name)}
					class="ml-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full hover:bg-black/15"
				>
					<svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" aria-hidden="true">
						<path d="M6 6l12 12M18 6L6 18" />
					</svg>
				</button>
			</span>
		{/each}

		<input
			bind:this={inputEl}
			type="text"
			role="combobox"
			aria-expanded={open}
			aria-controls="tag-picker-listbox-{uid}"
			aria-autocomplete="list"
			aria-activedescendant={open && highlightedIndex >= 0 ? `tag-picker-option-${uid}-${highlightedIndex}` : undefined}
			aria-labelledby="tag-picker-label-{uid}"
			bind:value={query}
			on:focus={openDropdown}
			on:input={openDropdown}
			on:keydown={handleInputKeydown}
			placeholder={selectedTags.length === 0 ? m.tags.picker.inputPlaceholder : ''}
			disabled={!!creatingName}
			class="min-w-[8ch] flex-1 border-none bg-transparent p-0.5 text-xs focus:outline-none disabled:opacity-50"
		/>
	</div>

	{#if creatingName}
		<div class="absolute z-20 mt-1 w-full rounded border border-hifi-border bg-hifi-surface p-3 text-xs shadow-sm">
			<p class="mb-2 text-hifi-text-muted">{m.tags.picker.createOptionLabel.replace('{name}', creatingName)}</p>
			<TagColorSwatchPicker bind:value={newTagColor} />
			{#if createError}
				<p class="mt-2 text-danger">{createError}</p>
			{/if}
			<div class="mt-3 flex gap-2">
				<button
					type="button"
					on:click={confirmCreate}
					disabled={creating}
					class="rounded-[10px] bg-hifi-accent px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
				>
					{creating ? m.tags.picker.creatingLabel : m.tags.picker.confirmCreateButton}
				</button>
				<button type="button" on:click={cancelCreate} class="text-hifi-text-muted hover:text-hifi-text">
					{m.tags.picker.cancelCreateButton}
				</button>
			</div>
		</div>
	{:else if open}
		<ul
			id="tag-picker-listbox-{uid}"
			role="listbox"
			aria-labelledby="tag-picker-label-{uid}"
			class="absolute z-20 mt-1 max-h-48 w-full overflow-auto rounded border border-hifi-border bg-hifi-surface py-1 text-xs shadow-sm"
		>
			{#if loadingTags}
				<li class="px-3 py-2 text-hifi-text-muted">{m.common.checking}</li>
			{:else if loadError}
				<li class="px-3 py-2 text-danger">{loadError}</li>
			{:else}
				{#each suggestions as tag, i (tag.id)}
					<li role="presentation">
						<button
							type="button"
							id="tag-picker-option-{uid}-{i}"
							role="option"
							aria-selected={i === highlightedIndex}
							on:click={() => addTag(tag)}
							on:mouseenter={() => (highlightedIndex = i)}
							class="flex w-full items-center gap-2 px-3 py-1.5 text-left transition-colors"
							class:bg-hifi-accent-tint={i === highlightedIndex}
						>
							<span class="h-2.5 w-2.5 flex-none rounded-full" style="background: {tagColorVar(tag.color)};" aria-hidden="true"></span>
							{tag.name}
						</button>
					</li>
				{/each}
				{#if showCreateOption}
					<li role="presentation">
						<button
							type="button"
							id="tag-picker-option-{uid}-{suggestions.length}"
							role="option"
							aria-selected={highlightedIndex === suggestions.length}
							on:click={() => startCreate(query)}
							on:mouseenter={() => (highlightedIndex = suggestions.length)}
							class="flex w-full items-center gap-2 px-3 py-1.5 text-left font-semibold text-hifi-accent-text transition-colors"
							class:bg-hifi-accent-tint={highlightedIndex === suggestions.length}
						>
							{m.tags.picker.createOptionLabel.replace('{name}', query.trim())}
						</button>
					</li>
				{:else if suggestions.length === 0}
					<li class="px-3 py-2 text-hifi-text-muted">{m.tags.picker.noResults}</li>
				{/if}
			{/if}
		</ul>
	{/if}
</div>
