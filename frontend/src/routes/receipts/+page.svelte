<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import ReceiptRow from '$lib/components/ReceiptRow.svelte';
	import ReceiptDetailView from '$lib/components/ReceiptDetailView.svelte';
	import SectionHeader from '$lib/components/SectionHeader.svelte';
	import { categoryLabel } from '$lib/categories';

	interface Receipt {
		id: string;
		bucket_id: string;
		status: string;
		receipt_date: string | null;
		total_amount: number | null;
		currency: string;
		thumb_path: string | null;
		merchant_name: string | null;
		category: string | null;
		item_count: number;
		created_at: string;
	}

	interface ItemRow {
		id: string;
		raw_name: string;
		quantity: number;
		unit: string | null;
		unit_price: number | null;
		total_price: number;
		pack_amount: number | null;
		pack_unit: string | null;
	}

	interface ReceiptDetail extends Receipt {
		ocr_raw_text: string | null;
		file_path: string;
		is_high_value: boolean;
		warranty_months: number | null;
		warranty_expires_at: string | null;
		custom_fields: Record<string, unknown> | null;
		items: ItemRow[];
		ai_suggested_merchant_name: string | null;
		ai_suggested_category: string | null;
		ai_extraction_note: string | null;
		ai_extracted_at: string | null;
	}

	interface Bucket {
		id: string;
		name: string;
		type: string;
		visibility: string;
		is_default: boolean;
	}

	const typeChips: { value: string | null; label: string }[] = [
		{ value: null, label: 'Alle' },
		{ value: 'high_value', label: 'Hochwertig' },
		{ value: 'warranty', label: 'Mit Garantie' },
		{ value: 'needs_review', label: 'Prüfung nötig' }
	];

	const sortChips: { value: string | null; label: string }[] = [
		{ value: null, label: 'Zuletzt hinzugefügt' },
		{ value: 'date_desc', label: 'Datum' },
		{ value: 'amount_desc', label: 'Betrag' }
	];

	const PAGE_SIZE = 30;

	let receipts: Receipt[] = [];
	let buckets: Bucket[] = [];
	let loading = true;
	let searching = false;
	let errorMessage = '';
	let groupByBucket = false;
	let openReceipt: ReceiptDetail | null = null;
	let expandedBuckets: Record<string, boolean> = {};

	let searchQuery = '';
	let activeType: string | null = null;
	let activeCategory: string | null = null;
	let activeSort: string | null = null;
	let allCategories: string[] = [];
	let searchDebounceHandle: ReturnType<typeof setTimeout> | undefined;
	let hasMore = true;
	let loadingMore = false;

	function buildParams(offset: number): URLSearchParams {
		const params = new URLSearchParams();
		if (searchQuery.trim()) params.set('q', searchQuery.trim());
		if (activeType) params.set('type', activeType);
		if (activeCategory) params.set('category', activeCategory);
		if (activeSort) params.set('sort', activeSort);
		params.set('limit', String(PAGE_SIZE));
		params.set('offset', String(offset));
		return params;
	}

	// Kategorie-Chips wachsen nur (Union), schrumpfen nie — weder durchs Filtern (Facetten-UX)
	// noch bleiben sie hinter neu vergebenen Kategorien zurück, die erst nach dem initialen
	// Laden dazukommen (z.B. direkt nach dem ersten Zuweisen einer Kategorie im Edit-Formular).
	function mergeCategories(pageReceipts: Receipt[]) {
		const found = pageReceipts.map((r) => r.category).filter((c): c is string => !!c);
		if (found.length === 0) return;
		allCategories = Array.from(new Set([...allCategories, ...found])).sort((a, b) =>
			a.localeCompare(b)
		);
	}

	// Ersetzt die Liste komplett (Filter/Sortierung geändert) und setzt die Lazy-Load-Seite zurück.
	async function refreshReceipts() {
		searching = true;
		try {
			const res = await fetch(`/api/receipts?${buildParams(0)}`, { credentials: 'include' });
			if (!res.ok) return;
			receipts = await res.json();
			hasMore = receipts.length === PAGE_SIZE;
			mergeCategories(receipts);
		} finally {
			searching = false;
		}
	}

	// Hängt die nächste Seite an (Endless Scroll laut UI-Konzept, keine klassische Pagination).
	async function loadMore() {
		if (!hasMore || loadingMore) return;
		loadingMore = true;
		try {
			const res = await fetch(`/api/receipts?${buildParams(receipts.length)}`, {
				credentials: 'include'
			});
			if (!res.ok) return;
			const nextPage: Receipt[] = await res.json();
			receipts = [...receipts, ...nextPage];
			hasMore = nextPage.length === PAGE_SIZE;
			mergeCategories(nextPage);
		} finally {
			loadingMore = false;
		}
	}

	function observeSentinel(node: HTMLDivElement) {
		const observer = new IntersectionObserver(
			(entries) => {
				if (entries[0].isIntersecting) loadMore();
			},
			{ rootMargin: '200px' }
		);
		observer.observe(node);
		return {
			destroy() {
				observer.disconnect();
			}
		};
	}

	function onSearchInput() {
		clearTimeout(searchDebounceHandle);
		searchDebounceHandle = setTimeout(refreshReceipts, 300);
	}

	function selectType(value: string | null) {
		activeType = value;
		refreshReceipts();
	}

	function selectCategory(value: string | null) {
		activeCategory = activeCategory === value ? null : value;
		refreshReceipts();
	}

	function selectSort(value: string | null) {
		activeSort = value;
		refreshReceipts();
	}

	onMount(async () => {
		try {
			// Direktlink von der Sidebar-Kategorienliste -> Filter vor dem ersten Laden setzen,
			// damit gleich gefiltert geladen wird statt erst ungefiltert und dann nachzufiltern.
			const categoryParam = $page.url.searchParams.get('category');
			if (categoryParam) activeCategory = categoryParam;

			const [receiptsRes, bucketsRes] = await Promise.all([
				fetch(`/api/receipts?${buildParams(0)}`, { credentials: 'include' }),
				fetch('/api/buckets', { credentials: 'include' })
			]);
			if (!receiptsRes.ok) throw new Error(`Belege konnten nicht geladen werden (${receiptsRes.status})`);
			if (!bucketsRes.ok) throw new Error(`Buckets konnten nicht geladen werden (${bucketsRes.status})`);
			receipts = await receiptsRes.json();
			hasMore = receipts.length === PAGE_SIZE;
			buckets = await bucketsRes.json();
			mergeCategories(receipts);
			for (const bucket of buckets) expandedBuckets[bucket.id] = true;

			// Direktlink von der Startseite ("Zuletzt hinzugefügt") -> Detail sofort öffnen,
			// statt erst die Liste zu zeigen und einen zweiten Klick zu verlangen.
			const openId = $page.url.searchParams.get('open');
			if (openId) await openDetail(openId);
		} catch (err) {
			errorMessage = err instanceof Error ? err.message : 'Unbekannter Fehler.';
		} finally {
			loading = false;
		}
	});

	function bucketFor(bucketId: string): Bucket | undefined {
		return buckets.find((b) => b.id === bucketId);
	}

	$: bucketFilterId = $page.url.searchParams.get('bucket');
	$: bucketFilter = bucketFilterId ? bucketFor(bucketFilterId) : undefined;
	$: visibleReceipts = bucketFilterId
		? receipts.filter((r) => r.bucket_id === bucketFilterId)
		: receipts;

	function clearBucketFilter() {
		goto('/receipts');
	}

	// Reihenfolge exakt nach UI-Konzept: Household-Bucket zuerst, dann eigene Personal Buckets
	$: groupedSections = groupByBucket
		? buckets
				.slice()
				.sort((a, b) => Number(b.is_default) - Number(a.is_default))
				.map((bucket) => ({
					bucket,
					items: visibleReceipts.filter((r) => r.bucket_id === bucket.id)
				}))
				.filter((section) => section.items.length > 0)
		: [];

	// Begrenztes Polling, solange die KI-Extraktion im Hintergrund läuft (status=pending) —
	// bewusst lokal hier statt als generische Store-/Polling-Infrastruktur, da es im Projekt
	// noch kein vergleichbares Muster gibt. Bricht nach ~10 Versuchen (30s) ab, damit ein
	// hängender Beleg nicht endlos weiterpollt.
	const PENDING_POLL_INTERVAL_MS = 3000;
	const PENDING_POLL_MAX_ATTEMPTS = 10;
	let pollHandle: ReturnType<typeof setTimeout> | undefined;
	let pollAttempts = 0;

	function schedulePendingPoll() {
		clearTimeout(pollHandle);
		if (!openReceipt || openReceipt.status !== 'pending' || pollAttempts >= PENDING_POLL_MAX_ATTEMPTS) {
			return;
		}
		pollHandle = setTimeout(async () => {
			if (!openReceipt) return;
			pollAttempts += 1;
			const res = await fetch(`/api/receipts/${openReceipt.id}`, { credentials: 'include' });
			if (!res.ok) return;
			const updated: ReceiptDetail = await res.json();
			const statusChanged = updated.status !== openReceipt.status;
			openReceipt = updated;
			// Badges/Filter-Chip ("Prüfung nötig" etc.) in der Liste dahinter aktualisieren,
			// sobald die Extraktion einen Endzustand erreicht hat.
			if (statusChanged) refreshReceipts();
			schedulePendingPoll();
		}, PENDING_POLL_INTERVAL_MS);
	}

	async function openDetail(id: string) {
		const res = await fetch(`/api/receipts/${id}`, { credentials: 'include' });
		if (!res.ok) return;
		openReceipt = await res.json();
		pollAttempts = 0;
		schedulePendingPoll();
	}

	function backToList() {
		clearTimeout(pollHandle);
		openReceipt = null;
	}

	onDestroy(() => clearTimeout(pollHandle));

	function handleDeleted() {
		openReceipt = null;
		refreshReceipts();
	}

	// Ein einziger onUpdated-Callback deckt saveEdit/Items/Vorschlag-Übernehmen/-Verwerfen
	// UND "Neu analysieren" ab. Letzteres setzt den Beleg serverseitig zurück auf pending,
	// aber ReceiptDetailView aktualisiert nur seine eigenen lokalen Props, nicht das
	// openReceipt-Objekt hier — ohne diesen Re-Fetch bliebe das Polling unten (das nur in
	// openDetail() angestoßen wird) für den neuen Extraktionslauf inaktiv, und die UI würde
	// den Ausgang erst nach einem manuellen Reload zeigen.
	async function handleReceiptUpdated() {
		refreshReceipts();
		if (!openReceipt) return;
		const res = await fetch(`/api/receipts/${openReceipt.id}`, { credentials: 'include' });
		if (!res.ok) return;
		openReceipt = await res.json();
		pollAttempts = 0;
		schedulePendingPoll();
	}
</script>

{#if openReceipt}
	<!-- Content-Switch statt Modal, gemäß Mockup: ersetzt die Liste komplett -->
	<ReceiptDetailView
		receiptId={openReceipt.id}
		receiptDate={openReceipt.receipt_date}
		totalAmount={openReceipt.total_amount}
		currency={openReceipt.currency}
		status={openReceipt.status}
		merchantName={openReceipt.merchant_name}
		category={openReceipt.category}
		ocrRawText={openReceipt.ocr_raw_text}
		filePath={openReceipt.file_path}
		isHighValue={openReceipt.is_high_value}
		warrantyMonths={openReceipt.warranty_months}
		warrantyExpiresAt={openReceipt.warranty_expires_at}
		customFields={openReceipt.custom_fields}
		items={openReceipt.items}
		aiSuggestedMerchantName={openReceipt.ai_suggested_merchant_name}
		aiSuggestedCategory={openReceipt.ai_suggested_category}
		aiExtractionNote={openReceipt.ai_extraction_note}
		aiExtractedAt={openReceipt.ai_extracted_at}
		onBack={backToList}
		onUpdated={handleReceiptUpdated}
		onDeleted={handleDeleted}
	/>
{:else}
	<h1 class="mb-6 text-[26px] font-extrabold tracking-tight text-hifi-text">Suche &amp; Filter</h1>

	<div class="relative mb-4">
		<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-hifi-text-faint" aria-hidden="true">
			<circle cx="10" cy="10" r="6" />
			<path d="M20 20l-5.5-5.5" />
		</svg>
		<input
			type="search"
			bind:value={searchQuery}
			on:input={onSearchInput}
			placeholder="Belege durchsuchen — Händler, Artikel, Text …"
			class="w-full rounded-[12px] border border-hifi-border bg-hifi-surface py-3 pl-11 pr-4 text-[14px] text-hifi-text placeholder:text-hifi-text-faint focus:border-hifi-accent focus:outline-none"
		/>
	</div>

	<div class="mb-3 flex flex-wrap gap-2">
		{#each typeChips as chip (chip.label)}
			<button
				on:click={() => selectType(chip.value)}
				class="rounded-full px-3.5 py-1.5 text-[13px] font-semibold transition-colors"
				class:bg-hifi-accent={activeType === chip.value}
				class:text-white={activeType === chip.value}
				class:bg-hifi-surface={activeType !== chip.value}
				class:border={activeType !== chip.value}
				class:border-hifi-border={activeType !== chip.value}
				class:text-hifi-text-muted={activeType !== chip.value}
			>
				{chip.label}
			</button>
		{/each}
	</div>

	{#if allCategories.length > 0}
		<div class="mb-5 flex flex-wrap gap-2">
			{#each allCategories as cat (cat)}
				<button
					on:click={() => selectCategory(cat)}
					class="rounded-full px-3.5 py-1.5 text-[13px] font-semibold transition-colors"
					class:bg-hifi-accent-tint={activeCategory === cat}
					class:text-hifi-accent-text={activeCategory === cat}
					class:bg-hifi-surface={activeCategory !== cat}
					class:border={activeCategory !== cat}
					class:border-hifi-border={activeCategory !== cat}
					class:text-hifi-text-muted={activeCategory !== cat}
				>
					{categoryLabel(cat)}
				</button>
			{/each}
		</div>
	{/if}

	{#if bucketFilter}
		<div class="mb-4 inline-flex items-center gap-2 rounded-full border border-hifi-border bg-hifi-surface px-3 py-1 text-xs text-hifi-text">
			<span>Bucket: {bucketFilter.name}</span>
			<button on:click={clearBucketFilter} aria-label="Filter entfernen" class="text-hifi-text-muted hover:text-hifi-text">✕</button>
		</div>
	{/if}

	{#if !loading && !errorMessage && visibleReceipts.length > 0}
		<div class="mb-4 flex flex-wrap items-center gap-2">
			<button
				class="block rounded-full border border-hifi-border px-3 py-1 text-xs text-hifi-text-muted hover:text-hifi-text"
				on:click={() => (groupByBucket = !groupByBucket)}
			>
				{groupByBucket ? 'Flach anzeigen' : 'Nach Bucket gruppieren'}
			</button>
			<span class="text-xs text-hifi-text-faint">·</span>
			<span class="text-xs text-hifi-text-faint">Sortieren:</span>
			{#each sortChips as chip (chip.label)}
				<button
					on:click={() => selectSort(chip.value)}
					class="rounded-full px-3 py-1 text-xs font-medium transition-colors"
					class:bg-hifi-accent-tint={activeSort === chip.value}
					class:text-hifi-accent-text={activeSort === chip.value}
					class:text-hifi-text-muted={activeSort !== chip.value}
					class:hover:text-hifi-text={activeSort !== chip.value}
				>
					{chip.label}
				</button>
			{/each}
		</div>
	{/if}

	{#if loading}
		<p class="text-sm text-hifi-text-muted">Belege werden geladen …</p>
	{:else if errorMessage}
		<p class="text-sm" style="color: var(--color-danger);">{errorMessage}</p>
	{:else if visibleReceipts.length === 0}
		<p class="text-sm text-hifi-text-muted">
			{searchQuery || activeType || activeCategory
				? 'Keine Belege gefunden — Filter anpassen oder Suche ändern.'
				: 'Noch keine Belege hochgeladen.'}
		</p>
	{:else if groupByBucket}
		{#each groupedSections as section (section.bucket.id)}
			<SectionHeader
				icon={section.bucket.is_default ? 'home' : 'lock'}
				name={section.bucket.name}
				count={section.items.length}
				sum={section.items.reduce((sum, r) => sum + (r.total_amount ?? 0), 0)}
				bind:expanded={expandedBuckets[section.bucket.id]}
			/>
			{#if expandedBuckets[section.bucket.id]}
				<div class="mb-4">
					{#each section.items as receipt (receipt.id)}
						<ReceiptRow
							id={receipt.id}
							receiptDate={receipt.receipt_date}
							totalAmount={receipt.total_amount}
							currency={receipt.currency}
							status={receipt.status}
							merchantName={receipt.merchant_name}
							itemCount={receipt.item_count}
							bucketName={section.bucket.name}
							bucketIsDefault={section.bucket.is_default}
							showBucketPill={false}
							thumbUrl={receipt.thumb_path ? `/api/receipts/${receipt.id}/thumb` : null}
							onOpen={openDetail}
						/>
					{/each}
				</div>
			{/if}
		{/each}
	{:else}
		<div class="rounded-[14px] border border-hifi-border bg-hifi-surface px-2" class:opacity-60={searching}>
			{#each visibleReceipts as receipt (receipt.id)}
				{@const bucket = bucketFor(receipt.bucket_id)}
				<ReceiptRow
					id={receipt.id}
					receiptDate={receipt.receipt_date}
					totalAmount={receipt.total_amount}
					currency={receipt.currency}
					status={receipt.status}
					merchantName={receipt.merchant_name}
					itemCount={receipt.item_count}
					bucketName={bucket?.name ?? '…'}
					bucketIsDefault={bucket?.is_default ?? false}
					thumbUrl={receipt.thumb_path ? `/api/receipts/${receipt.id}/thumb` : null}
					onOpen={openDetail}
				/>
			{/each}
		</div>
	{/if}

	{#if !loading && !errorMessage && hasMore}
		<div use:observeSentinel class="py-6 text-center text-xs text-hifi-text-faint">
			{loadingMore ? 'Weitere Belege werden geladen …' : ''}
		</div>
	{/if}
{/if}
