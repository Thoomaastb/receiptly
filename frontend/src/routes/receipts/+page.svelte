<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import ReceiptRow from '$lib/components/ReceiptRow.svelte';
	import ReceiptDetailView from '$lib/components/ReceiptDetailView.svelte';
	import SectionHeader from '$lib/components/SectionHeader.svelte';
	import { categoryLabel } from '$lib/categories';
	import { tagColorVar, type Tag } from '$lib/tags';
	import { m } from '$lib/i18n';

	interface Receipt {
		id: string;
		bucket_id: string;
		status: string;
		receipt_date: string | null;
		total_amount: number | null;
		currency: string;
		thumb_path: string | null;
		merchant_name: string | null;
		// Bestätigter Titel (siehe concepts/beleg-titel.md) — die Liste liefert bewusst
		// keinen ai_suggested_title (nur ReceiptDetail hat das Feld), siehe ReceiptRow.
		title: string | null;
		category: string | null;
		tags: Tag[];
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
		discount_amount: number | null;
		pack_amount: number | null;
		pack_unit: string | null;
	}

	interface ReceiptDetail extends Receipt {
		suggested_tags: Tag[];
		ocr_raw_text: string | null;
		file_path: string;
		is_high_value: boolean;
		warranty_months: number | null;
		warranty_expires_at: string | null;
		custom_fields: Record<string, unknown> | null;
		shipping_cost: number | null;
		discount_amount: number | null;
		tax_amount: number | null;
		items: ItemRow[];
		ai_suggested_merchant_name: string | null;
		ai_suggested_title: string | null;
		ai_suggested_category: string | null;
		ai_extraction_note: string | null;
		ai_extracted_at: string | null;
		ai_suggested_receipt_date: string | null;
		ai_suggested_total_amount: number | null;
		ai_suggested_currency: string | null;
		ai_suggested_shipping_cost: number | null;
		ai_suggested_discount_amount: number | null;
		ai_suggested_tax_amount: number | null;
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
	// true nur, wenn der aktuell offene Beleg über den Deep-Link von der Startseite
	// ("Zuletzt hinzugefügt", ?open=<id>) geöffnet wurde -> steuert, wohin "Zurück" führt.
	let openedViaHomeDeeplink = false;
	// Schaltet den $:-Sync-Block unten (siehe dort) erst frei, NACHDEM onMount seine eigene
	// initiale Deep-Link-Behandlung abgeschlossen hat -- sonst würde der Block bereits beim
	// allerersten reaktiven Durchlauf (der schon vor onMount läuft) denselben ?open-Parameter
	// ein zweites Mal verarbeiten (doppelter Fetch).
	let openParamSyncActive = false;
	// Wird unmittelbar vor dem goto(...) gesetzt, das den ?open-Parameter nach dem initialen
	// Öffnen wieder aus der URL entfernt (siehe onMount) -- verhindert, dass dieser rein
	// interne "Aufräum"-Navigationsschritt den gerade erst geöffneten Beleg sofort wieder
	// schließt, wenn der $:-Block danach den jetzt leeren Parameter sieht.
	let suppressNextOpenParamClose = false;
	// Zuletzt gesehener URL-Such-String (z.B. "?category=Lebensmittel") -- der $:-Block unten
	// führt seine Öffnen-/Schließen-Seiteneffekte nur aus, wenn sich DIESER gegenüber dem
	// letzten Lauf ändert, also bei einer ECHTEN Navigation. Ohne das würde JEDE Änderung an
	// $page ODER openReceipt (z.B. das Setzen von openReceipt beim manuellen Öffnen über
	// openDetailManual, das die URL gar nicht anfasst) den Block erneut auslösen und den
	// gerade erst geöffneten Beleg im selben Tick wieder schließen, weil
	// $page.url.searchParams.get('open') dann weiterhin null ist.
	//
	// Bewusst der VOLLE Such-String und nicht nur der ?open-Wert: Ein Sidebar-Kategorie-Klick
	// (+layout.svelte, goto('/receipts?category=X')) muss eine offene Detailansicht auch dann
	// schließen, wenn der Beleg über einen normalen Listen-Klick geöffnet wurde (also nie einen
	// ?open-Parameter in der URL hatte) -- reines Diffing von ?open allein würde in diesem Fall
	// "null -> null" sehen und fälschlich nichts tun.
	let lastUrlSearch: string | null = null;

	let searchQuery = '';
	let activeType: string | null = null;
	let activeCategory: string | null = null;
	// Mehrfachauswahl (OR-Semantik serverseitig, siehe list_receipts) — im Unterschied zu
	// activeCategory (Single-Select) ist das ein Array von Tag-IDs.
	let activeTags: string[] = [];
	let activeSort: string | null = null;
	let allCategories: string[] = [];
	// Anders als allCategories NICHT aus geladenen Seiten aggregiert, sondern einmalig als
	// eigene Ressource geladen (siehe onMount) — Tags existieren unabhängig davon, ob gerade
	// ein Beleg mit diesem Tag geladen ist.
	let allTags: Tag[] = [];
	let searchDebounceHandle: ReturnType<typeof setTimeout> | undefined;
	let hasMore = true;
	let loadingMore = false;

	function buildParams(offset: number): URLSearchParams {
		const params = new URLSearchParams();
		if (searchQuery.trim()) params.set('q', searchQuery.trim());
		if (activeType) params.set('type', activeType);
		if (activeCategory) params.set('category', activeCategory);
		activeTags.forEach((id) => params.append('tags', id));
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

	function selectTag(id: string) {
		activeTags = activeTags.includes(id) ? activeTags.filter((t) => t !== id) : [...activeTags, id];
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
			// Deep-Link mit mehreren ?tags=<id>-Parametern (analog zum ?category-Handling oben,
			// aber Mehrfachauswahl statt Single-Value).
			const tagsParam = $page.url.searchParams.getAll('tags');
			if (tagsParam.length > 0) activeTags = tagsParam;

			const [receiptsRes, bucketsRes, tagsRes] = await Promise.all([
				fetch(`/api/receipts?${buildParams(0)}`, { credentials: 'include' }),
				fetch('/api/buckets', { credentials: 'include' }),
				fetch('/api/tags', { credentials: 'include' })
			]);
			if (!receiptsRes.ok) throw new Error(`Belege konnten nicht geladen werden (${receiptsRes.status})`);
			if (!bucketsRes.ok) throw new Error(`Buckets konnten nicht geladen werden (${bucketsRes.status})`);
			receipts = await receiptsRes.json();
			hasMore = receipts.length === PAGE_SIZE;
			buckets = await bucketsRes.json();
			mergeCategories(receipts);
			if (tagsRes.ok) allTags = await tagsRes.json();
			for (const bucket of buckets) expandedBuckets[bucket.id] = true;

			// Direktlink von der Startseite ("Zuletzt hinzugefügt") -> Detail sofort öffnen,
			// statt erst die Liste zu zeigen und einen zweiten Klick zu verlangen. "Zurück" muss
			// in diesem Fall zur Startseite statt zur Liste führen (siehe backToList), und der
			// ?open-Param wird danach aus der URL entfernt, damit ein Reload nicht erneut
			// denselben Beleg deep-linkt und das Flag bei einem späteren manuellen Öffnen nicht
			// fälschlich hängen bleibt.
			const openId = $page.url.searchParams.get('open');
			if (openId) {
				openedViaHomeDeeplink = true;
				await openDetail(openId);
				suppressNextOpenParamClose = true;
				goto('/receipts', { replaceState: true, keepFocus: true, noScroll: true });
			}
		} catch (err) {
			errorMessage = err instanceof Error ? err.message : 'Unbekannter Fehler.';
		} finally {
			loading = false;
			// Aktuellen URL-Such-String als Ausgangspunkt für den $:-Block festhalten, BEVOR er
			// scharf geschaltet wird -- sonst hielte der Block den zu diesem Zeitpunkt bereits
			// vorliegenden Zustand fälschlich für eine neue Änderung und würde beim ersten Durchlauf
			// erneut reagieren. Das oben aufgerufene goto('/receipts', ...) wird bewusst nicht
			// awaited und hat den $page-Store an dieser Stelle in aller Regel noch NICHT
			// aktualisiert (SvelteKits Navigation läuft intern über mehrere await-Punkte, bevor der
			// Store gesetzt wird) -- $page.url zeigt hier also meist noch den alten ?open=<id>-Stand.
			// Das ist unschädlich: Sobald die Navigation tatsächlich abschließt und $page sich
			// ändert, erkennt der Block den Unterschied zu lastUrlSearch korrekt und verarbeitet das
			// Entfernen des Parameters dann regulär (inkl. Konsum von suppressNextOpenParamClose).
			lastUrlSearch = $page.url.search;
			// Ab hier übernimmt der $:-Block unten die Kopplung an ?open (siehe dort) --
			// bewusst erst NACH der obigen initialen Deep-Link-Behandlung aktiv, siehe Kommentar
			// bei openParamSyncActive.
			openParamSyncActive = true;
		}
	});

	// Hält die Detailansicht mit dem ?open-Parameter der URL synchron, NACHDEM die initiale
	// Deep-Link-Behandlung in onMount abgeschlossen ist (siehe openParamSyncActive). Behebt den
	// Bug, dass ein Kategorie-Klick in der Sidebar (+layout.svelte, goto('/receipts?category=X'))
	// den ?open-Parameter zwar aus der URL entfernt, die noch offene Detailansicht aber stehen
	// ließ, weil openReceipt bis dahin nirgends reaktiv an die URL gekoppelt war.
	//
	// Liest sowohl $page ALS AUCH openReceipt -- Svelte re-triggert $:-Blöcke bei JEDER darin
	// gelesenen Abhängigkeit, nicht nur bei $page. openDetailManual (normaler Klick aus der
	// Liste/Suche) setzt openReceipt direkt, ohne die URL anzufassen -- das würde diesen Block
	// sonst erneut auslösen, obwohl gar keine Navigation stattgefunden hat, und ihn dann
	// fälschlich in den else-Zweig (schließen) laufen lassen, weil urlOpenId ohnehin null ist.
	// Deshalb die Seiteneffekte nur ausführen, wenn sich der volle URL-Such-String GEGENÜBER DEM
	// LETZTEN LAUF tatsächlich geändert hat (lastUrlSearch) -- also bei einer ECHTEN Navigation.
	//
	// Bewusst der volle Such-String statt nur des ?open-Werts (siehe Deklaration von
	// lastUrlSearch oben): Sonst würde ein Sidebar-Kategorie-Klick bei einem über die Liste
	// (nicht per ?open-Deep-Link) geöffneten Beleg NICHT schließen, weil ?open dabei durchgehend
	// null bleibt ("null -> null" sieht wie "keine Änderung" aus) -- das wäre exakt der
	// ursprüngliche Bug, nur für den Listen-Klick-Fall statt den Deep-Link-Fall.
	$: if (openParamSyncActive) {
		const currentUrlSearch = $page.url.search;
		if (currentUrlSearch !== lastUrlSearch) {
			lastUrlSearch = currentUrlSearch;
			const urlOpenId = $page.url.searchParams.get('open');
			if (urlOpenId) {
				if (!openReceipt || openReceipt.id !== urlOpenId) {
					openedViaHomeDeeplink = true;
					openDetail(urlOpenId);
				}
			} else if (openReceipt) {
				if (suppressNextOpenParamClose) {
					suppressNextOpenParamClose = false;
				} else {
					openReceipt = null;
					openedViaHomeDeeplink = false;
				}
			}
		}
	}

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

	// Nachbar-Belege (nach Datum, im selben Bucket) für die Vor-/Zurück-Navigation in der
	// Detailansicht (Pfeil-Buttons ab sm, Swipe unterhalb sm — siehe ReceiptDetailView). Wird
	// bei jedem Öffnen/Wechsel neu geladen; null vor dem ersten Ergebnis bzw. bei Fehlern
	// (Buttons/Swipe bleiben dann inaktiv, kein Blocker für den Rest der Ansicht).
	let adjacentIds: { newer_id: string | null; older_id: string | null } | null = null;
	// Sperrt Pfeile/Swipe in ReceiptDetailView während ein Wechsel-Request läuft, damit ein
	// Doppel-Klick/Doppel-Swipe nicht zwei Requests gleichzeitig auslöst (siehe navigateReceipt).
	let navigatingReceipt = false;

	async function fetchAdjacent(receiptId: string, bucketId: string) {
		try {
			const res = await fetch(
				`/api/receipts/${receiptId}/adjacent?bucket_id=${bucketId}`,
				{ credentials: 'include' }
			);
			adjacentIds = res.ok ? await res.json() : null;
		} catch {
			adjacentIds = null;
		}
	}

	async function openDetail(id: string) {
		// Alte Nachbar-IDs sofort verwerfen statt bis zur neuen Antwort stehen zu lassen -- sonst
		// zeigen die Pfeile/die Swipe-Richtung kurzzeitig die Nachbarn des vorherigen Belegs.
		adjacentIds = null;
		const res = await fetch(`/api/receipts/${id}`, { credentials: 'include' });
		if (!res.ok) return;
		openReceipt = await res.json();
		pollAttempts = 0;
		schedulePendingPoll();
		if (openReceipt) fetchAdjacent(openReceipt.id, openReceipt.bucket_id);
	}

	// Für manuelle Klicks aus der Liste (im Gegensatz zum Deep-Link-Effect in onMount) -
	// stellt sicher, dass "Zurück" wieder zur Liste statt zur Startseite führt, falls zuvor
	// ein Beleg per Deep-Link geöffnet wurde.
	function openDetailManual(id: string) {
		openedViaHomeDeeplink = false;
		openDetail(id);
	}

	// Pfeil-Klick/Swipe in ReceiptDetailView -- lädt einfach den Nachbar-Beleg über den
	// bestehenden openDetail-Pfad nach (inkl. dessen eigenem Nachbar-Refetch für den nächsten
	// Schritt), das "Zurück"-Ziel (openedViaHomeDeeplink) bleibt dabei unverändert.
	async function navigateReceipt(direction: 'newer' | 'older') {
		if (!openReceipt || !adjacentIds || navigatingReceipt) return;
		const targetId = direction === 'newer' ? adjacentIds.newer_id : adjacentIds.older_id;
		if (!targetId) return;
		navigatingReceipt = true;
		try {
			await openDetail(targetId);
		} finally {
			navigatingReceipt = false;
		}
	}

	function backToList() {
		clearTimeout(pollHandle);
		openReceipt = null;
		adjacentIds = null;
		if (openedViaHomeDeeplink) {
			openedViaHomeDeeplink = false;
			goto('/');
		}
	}

	onDestroy(() => clearTimeout(pollHandle));

	function handleDeleted() {
		openReceipt = null;
		adjacentIds = null;
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
		const updated: ReceiptDetail = await res.json();
		openReceipt = updated;
		pollAttempts = 0;
		schedulePendingPoll();
		// Eine Bearbeitung kann receipt_date ändern und damit die Nachbar-Reihenfolge im
		// Bucket verschieben (Adjacent-Liste ist nach Datum sortiert) -- neu laden statt
		// veraltete newer_id/older_id stehen zu lassen.
		fetchAdjacent(updated.id, updated.bucket_id);
	}
</script>

{#if openReceipt}
	<!-- Content-Switch statt Modal, gemäß Mockup: ersetzt die Liste komplett.
	     {#key openReceipt.id}: erzwingt einen sauberen Unmount/Remount der Detail-Ansicht bei
	     JEDEM Beleg-Wechsel (Pfeil-Navigation/Swipe via navigateReceipt(), nicht nur beim
	     Öffnen aus der Liste) -- ReceiptDetailView.svelte hält mehrere lokale States, die
	     implizit von receiptId/filePath abhängen (Bild-URL, Zoom/Pan-Startwert, thumbFailed,
	     Bearbeiten-Entwurf, Artikel-Formulare, aufgeklappte Abschnitte), aber nur teilweise
	     reaktiv zurückgesetzt werden. Ohne Remount blieb v.a. die Bild-URL dauerhaft auf den
	     zuerst geöffneten Beleg eingefroren (Props aktualisierten sich, das <img src> nicht) --
	     live vom Nutzer bestätigt (mehrere LIDL-Belege zeigten alle dasselbe Bild). Der Key
	     ändert sich NICHT bei reinen Objekt-Refreshes mit gleicher id (Pending-Polling,
	     handleReceiptUpdated) -- dort bleibt die Instanz bewusst erhalten. -->
	{#key openReceipt.id}
		<ReceiptDetailView
			receiptId={openReceipt.id}
			receiptDate={openReceipt.receipt_date}
			totalAmount={openReceipt.total_amount}
			shippingCost={openReceipt.shipping_cost}
			discountAmount={openReceipt.discount_amount}
			taxAmount={openReceipt.tax_amount}
			currency={openReceipt.currency}
			status={openReceipt.status}
			merchantName={openReceipt.merchant_name}
			title={openReceipt.title}
			category={openReceipt.category}
			tags={openReceipt.tags}
			suggestedTags={openReceipt.suggested_tags}
			ocrRawText={openReceipt.ocr_raw_text}
			filePath={openReceipt.file_path}
			isHighValue={openReceipt.is_high_value}
			warrantyMonths={openReceipt.warranty_months}
			warrantyExpiresAt={openReceipt.warranty_expires_at}
			customFields={openReceipt.custom_fields}
			items={openReceipt.items}
			aiSuggestedMerchantName={openReceipt.ai_suggested_merchant_name}
			aiSuggestedTitle={openReceipt.ai_suggested_title}
			aiSuggestedCategory={openReceipt.ai_suggested_category}
			aiExtractionNote={openReceipt.ai_extraction_note}
			aiExtractedAt={openReceipt.ai_extracted_at}
			aiSuggestedReceiptDate={openReceipt.ai_suggested_receipt_date}
			aiSuggestedTotalAmount={openReceipt.ai_suggested_total_amount}
			aiSuggestedCurrency={openReceipt.ai_suggested_currency}
			aiSuggestedShippingCost={openReceipt.ai_suggested_shipping_cost}
			aiSuggestedDiscountAmount={openReceipt.ai_suggested_discount_amount}
			aiSuggestedTaxAmount={openReceipt.ai_suggested_tax_amount}
			onBack={backToList}
			onUpdated={handleReceiptUpdated}
			onDeleted={handleDeleted}
			hasNewer={adjacentIds?.newer_id != null}
			hasOlder={adjacentIds?.older_id != null}
			navigating={navigatingReceipt}
			onNavigate={navigateReceipt}
		/>
	{/key}
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

	{#if allTags.length > 0}
		<div class="mb-5 flex flex-wrap gap-2" aria-label={m.tags.filterSectionLabel}>
			{#each allTags as tag (tag.id)}
				{@const active = activeTags.includes(tag.id)}
				<button
					on:click={() => selectTag(tag.id)}
					aria-pressed={active}
					class="rounded-full px-3.5 py-1.5 text-[13px] font-semibold transition-colors"
					class:text-white={active}
					class:bg-hifi-surface={!active}
					class:border={!active}
					class:border-hifi-border={!active}
					class:text-hifi-text-muted={!active}
					style={active ? `background: ${tagColorVar(tag.color)};` : ''}
				>
					{tag.name}
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
			{searchQuery || activeType || activeCategory || activeTags.length > 0
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
							title={receipt.title}
							itemCount={receipt.item_count}
							tags={receipt.tags}
							bucketName={section.bucket.name}
							bucketIsDefault={section.bucket.is_default}
							showBucketPill={false}
							thumbUrl={`/api/receipts/${receipt.id}/thumb`}
							onOpen={openDetailManual}
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
					title={receipt.title}
					itemCount={receipt.item_count}
					tags={receipt.tags}
					bucketName={bucket?.name ?? '…'}
					bucketIsDefault={bucket?.is_default ?? false}
					thumbUrl={`/api/receipts/${receipt.id}/thumb`}
					onOpen={openDetailManual}
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
