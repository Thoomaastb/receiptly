<script lang="ts">
	import { CATEGORIES, categoryLabel, categoryColor, categoryFields } from '$lib/categories';
	import { tagColorVar, type Tag } from '$lib/tags';
	import { formatDate } from '$lib/formatDate';
	import { m } from '$lib/i18n';
	import { fade } from 'svelte/transition';
	import { tick } from 'svelte';
	import ShareManagementModal from './ShareManagementModal.svelte';
	import CustomSelect from './CustomSelect.svelte';
	import TagPicker from './TagPicker.svelte';

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

	export let receiptId: string;
	export let receiptDate: string | null;
	export let totalAmount: number | null;
	export let shippingCost: number | null = null;
	export let discountAmount: number | null = null;
	export let taxAmount: number | null = null;
	export let currency: string;
	export let status: string;
	export let merchantName: string | null = null;
	export let category: string | null = null;
	export let tags: Tag[] = [];
	export let suggestedTags: Tag[] = [];
	export let ocrRawText: string | null;
	export let isHighValue: boolean = false;
	export let warrantyMonths: number | null = null;
	export let warrantyExpiresAt: string | null = null;
	export let customFields: Record<string, unknown> | null = null;
	export let filePath: string;
	export let items: ItemRow[] = [];
	export let aiSuggestedMerchantName: string | null = null;
	export let aiSuggestedCategory: string | null = null;
	export let aiExtractionNote: string | null = null;
	export let aiExtractedAt: string | null = null;
	export let aiSuggestedReceiptDate: string | null = null;
	export let aiSuggestedTotalAmount: number | null = null;
	export let aiSuggestedCurrency: string | null = null;
	export let aiSuggestedShippingCost: number | null = null;
	export let aiSuggestedDiscountAmount: number | null = null;
	export let aiSuggestedTaxAmount: number | null = null;
	export let onBack: () => void;
	export let onUpdated: (() => void) | undefined = undefined;
	export let onDeleted: (() => void) | undefined = undefined;

	const fileUrl = `/api/receipts/${receiptId}/file`;
	$: isImageFile = /\.(jpe?g|png)$/i.test(filePath);
	// GET /thumb liefert 404, wenn kein serverseitiges Thumbnail existiert (alte Belege,
	// fehlgeschlagene Generierung) — analog zum Fallback-Muster in ReceiptRow.svelte.
	let thumbFailed = false;

	// --- Bild-Zoom & Maximieren (nur ab sm, siehe Pill-Menü im Vorschau-Panel unten) ---
	// Zoom wirkt über eine CSS-Custom-Property (--zoom) auf width/height des <img> (siehe
	// Markup) statt über transform:scale — reines transform vergrößert nur visuell und
	// vergrößert NICHT die Scroll-Fläche des umgebenden overflow-auto-Containers, das Bild
	// wäre also im gezoomten Zustand nicht pannbar.
	const ZOOM_MIN = 1;
	const ZOOM_MAX = 3;
	const ZOOM_STEP = 0.25;
	let zoomLevel = 1;

	// Ein anderer Beleg (receiptId wechselt) darf nicht den Zoom-Stand des vorherigen Belegs
	// übernehmen — sonst öffnet sich der nächste Beleg überraschend schon gezoomt. Der
	// dynamische Startzoom (siehe applyNativeZoom unten) wird dabei ebenfalls zurückgesetzt,
	// damit er für den neuen Beleg aus dessen eigener nativer Auflösung neu berechnet wird.
	$: if (receiptId) {
		zoomLevel = 1;
		zoomInitializedFor = null;
	}

	// Referenz auf das Vorschau-Panel (umschließt Bild + Pill-Menü) als Bezugsgröße für die
	// "Container-Breite" bei der nativen Zoom-Berechnung unten.
	let previewPanelEl: HTMLDivElement | undefined;
	// Verhindert, dass ein erneutes load-Event desselben Belegs (z.B. Browser-Reload) den
	// bereits manuell vom Nutzer gesetzten Zoom-Stand überschreibt — pro Beleg nur einmal.
	let zoomInitializedFor: string | null = null;

	// Initialer Zoom = native Bildauflösung statt fix 100%: ein langer, schmaler
	// Kassenbon-Scan ist bei reinem "passt in die Box"-Zoom (100%) beim Öffnen unleserlich
	// klein. 1 Bildpixel ≈ 1 CSS-Pixel bezogen auf die Container-Breite, siehe Kommentar am
	// --zoom-System oben — das bestehende System bleibt unverändert, nur dieser Startwert
	// wird jetzt dynamisch statt hartcodiert 1 berechnet. Nie über die native Auflösung
	// hinaus hochzoomen (nur unscharfe Vergrößerung, kein Informationsgewinn) und nie unter
	// die bisherige Fit-Container-Basis (100%) herunterzoomen.
	function applyNativeZoom(event: Event) {
		if (zoomInitializedFor === receiptId) return;
		zoomInitializedFor = receiptId;
		const img = event.currentTarget as HTMLImageElement;
		const containerWidth = previewPanelEl?.clientWidth;
		if (!containerWidth || !img.naturalWidth) return;
		const nativeZoom = img.naturalWidth / containerWidth;
		zoomLevel = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.round(nativeZoom * 100) / 100));
	}

	function zoomIn() {
		zoomLevel = Math.min(ZOOM_MAX, Math.round((zoomLevel + ZOOM_STEP) * 100) / 100);
	}
	function zoomOut() {
		zoomLevel = Math.max(ZOOM_MIN, Math.round((zoomLevel - ZOOM_STEP) * 100) / 100);
	}

	// Maximieren vergrößert die GESAMTE Card (nicht nur das Bild) auf ein Fixed-Overlay,
	// Backdrop/Escape-Verhalten analog zu ShareManagementModal.svelte (einziger bestehender
	// Modal-Präzedenzfall im Projekt) statt ein neues Overlay-Konzept zu erfinden.
	let maximized = false;
	let cardEl: HTMLDivElement | undefined;

	// Sanfter Übergang statt hartem Sprung auf die Zielgröße: manuelle FLIP-Technik
	// (First/Last/Invert/Play). Sveltes eingebaute transition:-Direktiven (siehe fade
	// oben) greifen nur beim Mounten/Unmounten eines #if-Blocks — hier bleibt dieselbe
	// Card-Instanz erhalten und wechselt nur Klassen (relative→fixed), deshalb wird die
	// Größen-/Positionsdifferenz manuell per getBoundingClientRect vor/nach dem
	// Zustandswechsel ermittelt und als transform animiert. Animiert wird ausschließlich
	// transform (Skalierung/Verschiebung), nie width/height/top/left direkt (Performance,
	// siehe ui-ux-pro-max-Vorgabe). prefers-reduced-motion überspringt die Animation
	// komplett und wechselt nur den Zustand.
	async function setMaximized(value: boolean) {
		if (value === maximized) return;
		const el = cardEl;
		const prefersReducedMotion =
			typeof window !== 'undefined' &&
			window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		if (!el || prefersReducedMotion) {
			maximized = value;
			return;
		}
		const first = el.getBoundingClientRect();
		maximized = value;
		await tick();
		const last = el.getBoundingClientRect();
		const dx = first.left - last.left;
		const dy = first.top - last.top;
		const scaleX = first.width / last.width;
		const scaleY = first.height / last.height;
		el.style.transformOrigin = 'top left';
		el.style.transition = 'none';
		el.style.transform = `translate(${dx}px, ${dy}px) scale(${scaleX}, ${scaleY})`;
		requestAnimationFrame(() => {
			el.style.transition = 'transform 320ms cubic-bezier(0.16, 1, 0.3, 1)';
			el.style.transform = 'translate(0, 0) scale(1, 1)';
		});
		const onTransitionEnd = () => {
			el.style.transition = '';
			el.style.transform = '';
			el.removeEventListener('transitionend', onTransitionEnd);
		};
		el.addEventListener('transitionend', onTransitionEnd);
	}
	function toggleMaximized() {
		setMaximized(!maximized);
	}
	function closeMaximized() {
		setMaximized(false);
	}
	function handleDetailKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && maximized) closeMaximized();
	}

	// Solange Datum/Betrag/Währung nur eine unbestätigte Heuristik-/KI-Schätzung sind
	// (Backend liefert dann einen Wert statt null), dezenten Hinweis in Lese- und
	// Editier-Ansicht zeigen — verschwindet automatisch, sobald der Nutzer bestätigt/ändert.
	$: dateIsEstimate = aiSuggestedReceiptDate !== null;
	$: amountIsEstimate = aiSuggestedTotalAmount !== null;
	$: currencyIsEstimate = aiSuggestedCurrency !== null;
	$: shippingIsEstimate = aiSuggestedShippingCost !== null;
	$: discountIsEstimate = aiSuggestedDiscountAmount !== null;
	$: taxIsEstimate = aiSuggestedTaxAmount !== null;

	let deleting = false;
	let shareModalOpen = false;

	async function deleteReceipt() {
		if (!confirm('Diesen Beleg wirklich löschen? Das kann nicht rückgängig gemacht werden.')) return;
		deleting = true;
		try {
			const res = await fetch(`/api/receipts/${receiptId}`, { method: 'DELETE', credentials: 'include' });
			if (res.ok || res.status === 204) onDeleted?.();
		} finally {
			deleting = false;
		}
	}

	function statusLabel(s: string): string {
		switch (s) {
			case 'pending':
				return 'Wird verarbeitet';
			case 'processed':
				return 'Verarbeitet';
			case 'needs_review':
				return 'Prüfung nötig';
			default:
				return s;
		}
	}

	$: warrantyStatus = (() => {
		if (!warrantyExpiresAt) return null;
		const days = (new Date(warrantyExpiresAt).getTime() - Date.now()) / 86_400_000;
		if (days < 0) return { level: 'expired', label: 'Garantie abgelaufen' };
		if (days <= 30) return { level: 'warning', label: 'Garantie läuft bald ab' };
		return { level: 'ok', label: 'Garantie aktiv' };
	})();

	// Bon-Betrag bleibt die primäre, direkt vom Beleg ablesbare Wahrheit — Artikel sind
	// optionale Detailtiefe. Statt die Summe aus Artikeln zu erzwingen, nur ein Hinweis
	// bei Abweichung, damit sichtbar ist, ob der Bon vollständig "aufgeschlüsselt" ist.
	$: itemsSum = items.reduce((sum, item) => sum + item.total_price, 0);
	// Versand/separat ausgewiesene Steuer heben den Bon-Betrag über die reine Artikelsumme
	// hinaus (von der Differenz abgezogen), ein Rabatt/Gutschein senkt ihn (zurückaddiert).
	$: itemsSumDiff =
		totalAmount !== null
			? Math.round(
					(totalAmount - itemsSum - (shippingCost ?? 0) - (taxAmount ?? 0) + (discountAmount ?? 0)) * 100
				) / 100
			: null;
	$: itemsIncomplete = items.length > 0 && itemsSumDiff !== null && Math.abs(itemsSumDiff) > 0.004;
	$: hasAdjustments = shippingCost !== null || discountAmount !== null || taxAmount !== null;
	// Passive Anzeige in der Leseansicht, damit sichtbar ist, was KI/manuelle Eingabe erkannt
	// haben, ohne extra ins Bearbeiten-Formular zu müssen (dort liegen die Rohwerte).
	$: adjustmentParts = [
		shippingCost !== null
			? `Versand ${shippingCost.toFixed(2)} ${currency}${shippingIsEstimate ? ' · geschätzt' : ''}`
			: null,
		discountAmount !== null
			? `Rabatt −${discountAmount.toFixed(2)} ${currency}${discountIsEstimate ? ' · geschätzt' : ''}`
			: null,
		taxAmount !== null
			? `Steuer ${taxAmount.toFixed(2)} ${currency}${taxIsEstimate ? ' · geschätzt' : ''}`
			: null
	].filter((part): part is string => part !== null);

	// --- Kernfelder bearbeiten (Datum/Betrag/Händler/Hochwertig/Garantie) ---
	// Manuelle Bearbeitung, solange die KI-Struktur-Extraktion aus dem OCR-Text noch
	// nicht existiert (siehe Backlog) — sonst blieben diese Felder auf ewig leer.
	let editing = false;
	let saving = false;
	let saveError = '';
	let draftDate = '';
	let draftAmount = '';
	let draftShippingCost = '';
	let draftDiscountAmount = '';
	let draftTaxAmount = '';
	let draftCurrency = '';
	let draftMerchant = '';
	let draftHighValue = false;
	let draftWarrantyMonths = '';
	let draftCategory = '';
	// String-Draft je Kategorie-Zusatzfeld (siehe categoryFields) — Keys über alle
	// Kategorien hinweg gesammelt, beim Speichern wird nur auf die Felder der aktuell
	// gewählten Kategorie gefiltert (siehe saveEdit).
	let draftCustomFields: Record<string, string> = {};
	let draftTagIds: string[] = [];

	// Vorschläge aus der Händler-Historie (siehe suggested_tags in applyDetail) — nur die noch
	// nicht ausgewählten anzeigen, damit ein bereits übernommener/manuell gesetzter Tag nicht
	// doppelt (als Chip UND als Vorschlag) auftaucht.
	$: unselectedSuggestions = suggestedTags.filter((t) => !draftTagIds.includes(t.id));

	function startEdit() {
		draftDate = receiptDate ?? '';
		draftAmount = totalAmount !== null ? String(totalAmount) : '';
		draftShippingCost = shippingCost !== null ? String(shippingCost) : '';
		draftDiscountAmount = discountAmount !== null ? String(discountAmount) : '';
		draftTaxAmount = taxAmount !== null ? String(taxAmount) : '';
		draftCurrency = currency;
		draftMerchant = merchantName ?? '';
		draftHighValue = isHighValue;
		draftWarrantyMonths = warrantyMonths !== null ? String(warrantyMonths) : '';
		draftCategory = category ?? '';
		draftCustomFields = Object.fromEntries(
			Object.entries(customFields ?? {}).map(([key, value]) => [key, String(value)])
		);
		draftTagIds = tags.map((t) => t.id);
		saveError = '';
		editing = true;
	}

	function cancelEdit() {
		editing = false;
	}

	function applyDetail(detail: {
		receipt_date: string | null;
		total_amount: number | null;
		shipping_cost?: number | null;
		discount_amount?: number | null;
		tax_amount?: number | null;
		merchant_name: string | null;
		category: string | null;
		tags?: Tag[];
		suggested_tags?: Tag[];
		is_high_value: boolean;
		warranty_months: number | null;
		warranty_expires_at: string | null;
		custom_fields: Record<string, unknown> | null;
		items: ItemRow[];
		status?: string;
		ai_suggested_merchant_name?: string | null;
		ai_suggested_category?: string | null;
		ai_extraction_note?: string | null;
		ai_extracted_at?: string | null;
		ai_suggested_receipt_date?: string | null;
		ai_suggested_total_amount?: number | null;
		ai_suggested_currency?: string | null;
		ai_suggested_shipping_cost?: number | null;
		ai_suggested_discount_amount?: number | null;
		ai_suggested_tax_amount?: number | null;
	}) {
		receiptDate = detail.receipt_date;
		totalAmount = detail.total_amount;
		if (detail.shipping_cost !== undefined) shippingCost = detail.shipping_cost;
		if (detail.discount_amount !== undefined) discountAmount = detail.discount_amount;
		if (detail.tax_amount !== undefined) taxAmount = detail.tax_amount;
		merchantName = detail.merchant_name;
		category = detail.category;
		if (detail.tags !== undefined) tags = detail.tags;
		suggestedTags = detail.suggested_tags ?? [];
		isHighValue = detail.is_high_value;
		warrantyMonths = detail.warranty_months;
		warrantyExpiresAt = detail.warranty_expires_at;
		customFields = detail.custom_fields;
		items = detail.items;
		if (detail.status !== undefined) status = detail.status;
		if (detail.ai_suggested_merchant_name !== undefined) {
			aiSuggestedMerchantName = detail.ai_suggested_merchant_name;
		}
		if (detail.ai_suggested_category !== undefined) aiSuggestedCategory = detail.ai_suggested_category;
		if (detail.ai_extraction_note !== undefined) aiExtractionNote = detail.ai_extraction_note;
		if (detail.ai_extracted_at !== undefined) aiExtractedAt = detail.ai_extracted_at;
		if (detail.ai_suggested_receipt_date !== undefined) {
			aiSuggestedReceiptDate = detail.ai_suggested_receipt_date;
		}
		if (detail.ai_suggested_total_amount !== undefined) {
			aiSuggestedTotalAmount = detail.ai_suggested_total_amount;
		}
		if (detail.ai_suggested_currency !== undefined) aiSuggestedCurrency = detail.ai_suggested_currency;
		if (detail.ai_suggested_shipping_cost !== undefined) {
			aiSuggestedShippingCost = detail.ai_suggested_shipping_cost;
		}
		if (detail.ai_suggested_discount_amount !== undefined) {
			aiSuggestedDiscountAmount = detail.ai_suggested_discount_amount;
		}
		if (detail.ai_suggested_tax_amount !== undefined) aiSuggestedTaxAmount = detail.ai_suggested_tax_amount;
	}

	// --- KI-Struktur-Extraktions-Vorschlag (Übernehmen/Verwerfen/Neu analysieren) ---
	// Die Kategorie wird von der KI mittlerweile direkt in receipt.category übernommen
	// (siehe ai_extraction.py) statt nur vorgeschlagen zu werden — nur noch der Händlername
	// bleibt ein offener, bestätigungspflichtiger Vorschlag.
	$: hasSuggestion = !!aiSuggestedMerchantName;

	let suggestionSaving = false;
	let reanalyzing = false;

	async function acceptSuggestion() {
		suggestionSaving = true;
		try {
			const payload: Record<string, unknown> = { dismiss_ai_suggestion: true };
			if (aiSuggestedMerchantName) payload.merchant_name = aiSuggestedMerchantName;
			const res = await fetch(`/api/receipts/${receiptId}`, {
				method: 'PATCH',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload)
			});
			if (res.ok) {
				applyDetail(await res.json());
				onUpdated?.();
			}
		} finally {
			suggestionSaving = false;
		}
	}

	async function dismissSuggestion() {
		suggestionSaving = true;
		try {
			const res = await fetch(`/api/receipts/${receiptId}`, {
				method: 'PATCH',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ dismiss_ai_suggestion: true })
			});
			if (res.ok) {
				applyDetail(await res.json());
				onUpdated?.();
			}
		} finally {
			suggestionSaving = false;
		}
	}

	async function reanalyze() {
		reanalyzing = true;
		try {
			const res = await fetch(`/api/receipts/${receiptId}/extract`, {
				method: 'POST',
				credentials: 'include'
			});
			if (res.ok) {
				applyDetail(await res.json());
				onUpdated?.();
			}
		} finally {
			reanalyzing = false;
		}
	}

	async function saveEdit() {
		saving = true;
		saveError = '';
		try {
			// Nur die Zusatzfelder der aktuell gewählten Kategorie mitschicken — ein
			// Kategoriewechsel während des Editierens lässt so keine verwaisten Werte
			// einer vorherigen Kategorie im JSONB-Feld zurück.
			const fieldsForCategory = categoryFields(draftCategory || null);
			const customFieldsPayload =
				fieldsForCategory.length > 0
					? Object.fromEntries(
							fieldsForCategory
								.map((field) => [field.key, draftCustomFields[field.key]?.trim() ?? ''])
								.filter(([, value]) => value !== '')
								.map(([key, value]) => [
									key,
									fieldsForCategory.find((f) => f.key === key)?.type === 'number'
										? Number(value)
										: value
								])
						)
					: null;

			const res = await fetch(`/api/receipts/${receiptId}`, {
				method: 'PATCH',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					receipt_date: draftDate || null,
					total_amount: draftAmount ? Number(draftAmount) : null,
					shipping_cost: draftShippingCost ? Number(draftShippingCost) : null,
					discount_amount: draftDiscountAmount ? Number(draftDiscountAmount) : null,
					tax_amount: draftTaxAmount ? Number(draftTaxAmount) : null,
					currency: draftCurrency.trim().toUpperCase() || null,
					merchant_name: draftMerchant.trim() || null,
					is_high_value: draftHighValue,
					warranty_months: draftWarrantyMonths ? Number(draftWarrantyMonths) : null,
					category: draftCategory || null,
					custom_fields: customFieldsPayload,
					tag_ids: draftTagIds
				})
			});
			if (res.ok) {
				applyDetail(await res.json());
				editing = false;
				onUpdated?.();
			} else {
				const body = await res.json().catch(() => null);
				saveError = body?.detail ?? 'Speichern fehlgeschlagen.';
			}
		} finally {
			saving = false;
		}
	}

	// --- Artikel (aufklappbare Liste, eigene CRUD-Aktionen unabhängig vom Bearbeiten-Modus) ---
	let itemsExpanded = true;
	let ocrTextExpanded = false;

	let addingItem = false;
	let newItemName = '';
	let newItemQuantity = '1';
	let newItemUnit = '';
	let newItemUnitPrice = '';
	let newItemTotalPrice = '';
	let newItemTotalPriceTouched = false;
	let newItemDiscountAmount = '';
	let newItemPackAmount = '';
	let newItemPackUnit = '';

	function resetNewItemForm() {
		newItemName = '';
		newItemQuantity = '1';
		newItemUnit = '';
		newItemUnitPrice = '';
		newItemTotalPrice = '';
		newItemTotalPriceTouched = false;
		newItemDiscountAmount = '';
		newItemPackAmount = '';
		newItemPackUnit = '';
	}

	// Menge × Einzelpreis rechnet die Gesamtsumme automatisch vor, solange der Nutzer das
	// Gesamt-Feld nicht selbst angefasst hat (z.B. für Rabatte) — sonst blieb bei "3x 4,99€"
	// nur 4,99€ in der Summe hängen, weil total_price ein reines Freitextfeld war.
	$: if (!newItemTotalPriceTouched && newItemUnitPrice) {
		const qty = Number(newItemQuantity) || 1;
		const unitPrice = Number(newItemUnitPrice);
		if (unitPrice >= 0) newItemTotalPrice = (qty * unitPrice).toFixed(2);
	}

	// Anzahl (quantity) vs. Menge pro Einheit (pack_amount): "6x Wasser à 1,5l" ergibt 9l
	// Gesamtmenge — getrennt von der Preis-Berechnung oben, siehe Kommentar am Item-Modell.
	$: newItemTotalAmount =
		newItemPackAmount && newItemPackUnit
			? (Number(newItemQuantity) || 1) * Number(newItemPackAmount)
			: null;

	async function addItem() {
		if (!newItemName.trim() || !newItemTotalPrice) return;
		const res = await fetch(`/api/receipts/${receiptId}/items`, {
			method: 'POST',
			credentials: 'include',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				raw_name: newItemName.trim(),
				quantity: newItemQuantity ? Number(newItemQuantity) : 1,
				unit: newItemUnit.trim() || null,
				unit_price: newItemUnitPrice ? Number(newItemUnitPrice) : null,
				total_price: Number(newItemTotalPrice),
				discount_amount: newItemDiscountAmount ? Number(newItemDiscountAmount) : null,
				pack_amount: newItemPackAmount ? Number(newItemPackAmount) : null,
				pack_unit: newItemPackUnit.trim() || null
			})
		});
		if (res.ok) {
			items = [...items, await res.json()];
			resetNewItemForm();
			addingItem = false;
			onUpdated?.();
		}
	}

	let editingItemId: string | null = null;
	let editItemName = '';
	let editItemQuantity = '';
	let editItemUnit = '';
	let editItemUnitPrice = '';
	let editItemTotalPrice = '';
	let editItemTotalPriceTouched = false;
	let editItemDiscountAmount = '';
	let editItemPackAmount = '';
	let editItemPackUnit = '';

	function startEditItem(item: ItemRow) {
		editingItemId = item.id;
		editItemName = item.raw_name;
		editItemQuantity = String(item.quantity);
		editItemUnit = item.unit ?? '';
		editItemUnitPrice = item.unit_price !== null ? String(item.unit_price) : '';
		editItemTotalPrice = String(item.total_price);
		editItemTotalPriceTouched = false;
		editItemDiscountAmount = item.discount_amount !== null ? String(item.discount_amount) : '';
		editItemPackAmount = item.pack_amount !== null ? String(item.pack_amount) : '';
		editItemPackUnit = item.pack_unit ?? '';
	}

	function cancelEditItem() {
		editingItemId = null;
	}

	// Gleiche Auto-Berechnung wie im Hinzufügen-Formular (siehe Kommentar dort)
	$: if (!editItemTotalPriceTouched && editItemUnitPrice) {
		const qty = Number(editItemQuantity) || 1;
		const unitPrice = Number(editItemUnitPrice);
		if (unitPrice >= 0) editItemTotalPrice = (qty * unitPrice).toFixed(2);
	}

	$: editItemTotalAmount =
		editItemPackAmount && editItemPackUnit
			? (Number(editItemQuantity) || 1) * Number(editItemPackAmount)
			: null;

	async function saveEditItem(itemId: string) {
		const res = await fetch(`/api/receipts/${receiptId}/items/${itemId}`, {
			method: 'PATCH',
			credentials: 'include',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				raw_name: editItemName.trim(),
				unit_price: editItemUnitPrice ? Number(editItemUnitPrice) : null,
				quantity: editItemQuantity ? Number(editItemQuantity) : undefined,
				unit: editItemUnit.trim() || null,
				total_price: editItemTotalPrice ? Number(editItemTotalPrice) : undefined,
				discount_amount: editItemDiscountAmount ? Number(editItemDiscountAmount) : null,
				pack_amount: editItemPackAmount ? Number(editItemPackAmount) : null,
				pack_unit: editItemPackUnit.trim() || null
			})
		});
		if (res.ok) {
			const updated = await res.json();
			items = items.map((i) => (i.id === updated.id ? updated : i));
			editingItemId = null;
			onUpdated?.();
		}
	}

	async function deleteItem(itemId: string) {
		const res = await fetch(`/api/receipts/${receiptId}/items/${itemId}`, {
			method: 'DELETE',
			credentials: 'include'
		});
		if (res.ok || res.status === 204) {
			items = items.filter((i) => i.id !== itemId);
			onUpdated?.();
		}
	}
</script>

<svelte:window on:keydown={handleDetailKeydown} />

<div class="flex flex-col sm:h-full sm:min-h-0">
	{#if !maximized}
		<button on:click={onBack} class="mb-4 flex-none flex items-center gap-1.5 text-sm font-medium text-hifi-text-muted hover:text-hifi-text">
			<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<path d="M15 18l-6-6 6-6" />
			</svg>
			Zurück
		</button>
	{/if}

	{#if maximized}
		<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
		<div
			transition:fade={{ duration: 150 }}
			class="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
			on:click={closeMaximized}
			role="presentation"
		></div>
	{/if}

	<!-- Card ab sm: höhenbegrenzt (füllt den durch das h-screen-Flex-Layout in +layout.svelte
	     ohnehin schon vorgegebenen verfügbaren Platz unterhalb der Topbar/oberhalb von main's
	     Padding) statt zu versuchen, das Bild selbst exakt in eine unklare Höhe zu zwingen — die
	     Artikel-Liste rechts scrollt bei Bedarf INNERHALB der Card (siehe dort), alles andere
	     bleibt fix sichtbar. Unter sm bleibt alles gestapelt und folgt normalem
	     Seiten-Scrolling (main ist bereits overflow-y-auto).
	     Maximieren (nur ab sm, siehe Pill-Menü im Vorschau-Panel): dieselbe Card wird per
	     position:fixed auf ~95% des Browserfensters vergrößert (top/bottom/left/right-8 =
	     Tailwind-Spacing-8/32px Rand auf allen Seiten) statt sie zu duplizieren — vermeidet
	     doppelten Markup-Unterhalt zwischen normaler und maximierter Ansicht. -->
	<div
		bind:this={cardEl}
		class="grid grid-cols-1 gap-6 rounded-[20px] border border-hifi-border bg-hifi-surface p-2 sm:min-h-0 sm:flex-1 sm:grid-cols-[1.1fr_0.9fr] sm:overflow-hidden"
		class:relative={!maximized}
		class:fixed={maximized}
		class:z-50={maximized}
		class:top-8={maximized}
		class:bottom-8={maximized}
		class:left-8={maximized}
		class:right-8={maximized}
		class:shadow-popover={maximized}
		role={maximized ? 'dialog' : undefined}
		aria-modal={maximized ? 'true' : undefined}
		aria-label={maximized ? 'Beleg-Detailansicht (maximiert)' : undefined}
	>
		{#if maximized}
			<button
				type="button"
				on:click={closeMaximized}
				aria-label="Maximierte Ansicht schließen"
				title="Maximierte Ansicht schließen"
				class="absolute right-3 top-3 z-10 flex h-11 w-11 items-center justify-center rounded-full bg-hifi-accent-tint text-hifi-accent-text hover:bg-hifi-accent hover:text-white"
			>
				<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<path d="M6 6l12 12M18 6L6 18" />
				</svg>
			</button>
		{/if}
		<!-- Links: Vorschau-Panel — Bild direkt eingebettet, PDF als Kachel mit Öffnen-Link
		     (kein <iframe>, um von PDF-Viewer-Eigenheiten je Browser unabhängig zu bleiben).
		     Feste Höhe (statt nur min-height) ist nötig, damit h-full auf dem <img> überhaupt
		     etwas zum Auflösen hat — eine reine min-height macht die Höhe des Containers für
		     Prozent-Angaben nicht "bestimmt" (CSS-Spec-Quirk), das war Kern des Bugs. Ab sm
		     übernimmt die durch das Grid gestreckte, von der Card-Höhenbegrenzung abgeleitete
		     Höhe (sm:h-full) diese Rolle. -->
		<div bind:this={previewPanelEl} class="relative flex h-[320px] items-center justify-center overflow-hidden rounded-2xl bg-hifi-surface sm:h-full sm:min-h-0">
			{#if isImageFile}
				<div class="h-full w-full sm:overflow-auto">
					<img
						src={fileUrl}
						alt="Beleg-Vorschau"
						class="block h-full w-full object-contain sm:h-[calc(var(--zoom)*100%)] sm:w-[calc(var(--zoom)*100%)]"
						style="--zoom: {zoomLevel};"
						on:load={applyNativeZoom}
					/>
				</div>
			{:else}
				<!-- Serverseitiges Thumbnail (erste PDF-Seite, siehe app/services/storage.py) als
				     Vorschau — mit demselben 404-Fallback-Muster wie ReceiptRow.svelte: schlägt es
				     fehl (alte Belege ohne generiertes Thumbnail), bleibt nur die Öffnen-Kachel. -->
				<div class="absolute inset-0 flex items-center justify-center" style={thumbFailed ? 'background: repeating-linear-gradient(135deg, var(--color-stripe-doc-a) 0, var(--color-stripe-doc-a) 10px, var(--color-stripe-doc-b) 10px, var(--color-stripe-doc-b) 20px);' : ''}>
					{#if !thumbFailed}
						<div class="h-full w-full sm:overflow-auto">
							<img
								src={`/api/receipts/${receiptId}/thumb`}
								alt="Beleg-Vorschau (erste Seite)"
								class="block h-full w-full object-contain sm:h-[calc(var(--zoom)*100%)] sm:w-[calc(var(--zoom)*100%)]"
								style="--zoom: {zoomLevel};"
								on:error={() => (thumbFailed = true)}
								on:load={applyNativeZoom}
							/>
						</div>
					{/if}
					<a
						href={fileUrl}
						target="_blank"
						rel="noopener noreferrer"
						class="flex items-center gap-2 rounded-md bg-hifi-surface/80 px-3 py-1.5 font-mono text-xs font-semibold text-hifi-accent-text hover:bg-hifi-surface {thumbFailed ? '' : 'absolute left-1/2 top-3 -translate-x-1/2'}"
					>
						PDF-Dokument öffnen
					</a>
				</div>
			{/if}
			<!-- Pill-Menü: Zoom/Maximieren nur ab sm (Mobile bleibt bewusst beim einfachen
			     Verhalten, siehe Kommentar bei maximized oben) — der Download-Button steckt aber
			     mit im selben Pill und bleibt deshalb auch unter sm sichtbar, sonst gäbe es auf
			     Mobile gar keinen Download-Zugriff mehr, seit der eigenständige Button entfallen
			     ist. left-1/2 ist hier das laut CLAUDE.md verbindliche explizite Inset zur
			     -translate-x-1/2-Zentrierung. -->
			<div class="absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-1 rounded-full border border-hifi-border/60 bg-hifi-accent-tint/90 p-1.5 shadow-popover backdrop-blur-md">
				{#if isImageFile || !thumbFailed}
					<div class="hidden items-center gap-1 sm:flex">
						<button
							type="button"
							on:click={zoomOut}
							disabled={zoomLevel <= ZOOM_MIN}
							aria-label="Bild verkleinern"
							title="Verkleinern"
							class="flex h-11 w-11 items-center justify-center rounded-full text-hifi-accent-text hover:bg-hifi-surface/70 disabled:opacity-40"
						>
							<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
								<path d="M5 12h14" />
							</svg>
						</button>
						<span class="min-w-[2.75rem] text-center font-mono text-[11px] font-semibold text-hifi-accent-text" aria-hidden="true">
							{Math.round(zoomLevel * 100)}%
						</span>
						<button
							type="button"
							on:click={zoomIn}
							disabled={zoomLevel >= ZOOM_MAX}
							aria-label="Bild vergrößern"
							title="Vergrößern"
							class="flex h-11 w-11 items-center justify-center rounded-full text-hifi-accent-text hover:bg-hifi-surface/70 disabled:opacity-40"
						>
							<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
								<path d="M12 5v14M5 12h14" />
							</svg>
						</button>
						<div class="mx-0.5 h-5 w-px bg-hifi-border" aria-hidden="true"></div>
						<button
							type="button"
							on:click={toggleMaximized}
							aria-label={maximized ? 'Normalansicht wiederherstellen' : 'Beleg maximieren'}
							title={maximized ? 'Normalansicht wiederherstellen' : 'Maximieren'}
							class="flex h-11 w-11 items-center justify-center rounded-full text-hifi-accent-text hover:bg-hifi-surface/70"
						>
							{#if maximized}
								<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
									<path d="M9 3v4a1 1 0 01-1 1H4M20 9h-4a1 1 0 01-1-1V4M15 21v-4a1 1 0 011-1h4M4 15h4a1 1 0 011 1v4" />
								</svg>
							{:else}
								<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
									<path d="M8 3H5a2 2 0 00-2 2v3M16 3h3a2 2 0 012 2v3M8 21H5a2 2 0 01-2-2v-3M16 21h3a2 2 0 002-2v-3" />
								</svg>
							{/if}
						</button>
						<div class="mx-0.5 h-5 w-px bg-hifi-border" aria-hidden="true"></div>
					</div>
				{/if}
				<a
					href={fileUrl}
					download
					aria-label="Beleg herunterladen"
					title="Herunterladen"
					class="flex h-11 w-11 items-center justify-center rounded-full text-hifi-accent-text hover:bg-hifi-surface/70"
				>
					<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						<path d="M12 3v12M7 10l5 5 5-5" /><path d="M5 21h14" />
					</svg>
				</a>
			</div>
		</div>

		<!-- Rechts: Metadaten — die oberen Infobereiche (Badges, Händler/Datum/Betrag inkl.
		     KI-Status-Chip, Garantie-Tracking, Bearbeiten) bleiben fix sichtbar; NUR der
		     aufklappbare Artikel-Abschnitt weiter unten bekommt seinen eigenen internen
		     Scroll-Container (siehe dort) — dieser Wrapper hier scrollt daher selbst
		     NICHT mehr. Im maximierten Zustand zusätzliches Top-Padding (pt-14 statt der
		     regulären p-4/sm:p-2), damit die erste Zeile (Badges + Bearbeiten-Link) nicht
		     mehr mit dem absolut positionierten ×-Schließen-Button (h-11 = 44px bei top-3)
		     kollidiert — per Screenshot bestätigter Bug, siehe CLAUDE.md-Bugs-Historie. -->
		<div class="flex flex-col gap-4 p-4 sm:h-full sm:min-h-0 sm:p-2 {maximized ? 'pt-14 sm:pt-14' : ''}">
			<div class="flex items-start justify-between gap-2">
				<div class="flex flex-wrap gap-1.5">
					<span class="rounded-full border border-hifi-border bg-hifi-surface px-2.5 py-0.5 text-xs font-medium text-hifi-text-muted">
						{statusLabel(status)}
					</span>
					{#if isHighValue}
						<span class="rounded-full bg-hifi-accent px-2.5 py-0.5 text-xs font-medium text-white">
							Hochwertig
						</span>
					{/if}
					{#if category}
						<span
							class="rounded-full px-2.5 py-0.5 text-xs font-medium text-white"
							style="background: {categoryColor(category)};"
						>
							{categoryLabel(category)}
						</span>
					{/if}
					{#each tags as tag (tag.id)}
						<span
							class="rounded-full px-2.5 py-0.5 text-xs font-medium text-white"
							style="background: {tagColorVar(tag.color)};"
						>
							{tag.name}
						</span>
					{/each}
				</div>
				{#if !editing}
					<button on:click={startEdit} class="text-xs font-semibold text-hifi-text-muted hover:text-hifi-text">
						Bearbeiten
					</button>
				{/if}
			</div>

			{#if editing}
				<div class="flex flex-col gap-3 rounded-[14px] border border-hifi-border bg-hifi-surface p-3">
					<label class="text-xs">
						<span class="mb-1 block text-hifi-text-muted">Händler</span>
						<input
							type="text"
							bind:value={draftMerchant}
							placeholder="z. B. Edeka"
							class="w-full rounded border border-hifi-border bg-hifi-surface p-2 text-sm"
						/>
					</label>
					<div class="grid grid-cols-2 gap-2 sm:grid-cols-3">
						<label class="text-xs">
							<span class="mb-1 block text-hifi-text-muted">Datum{dateIsEstimate ? ' · geschätzt' : ''}</span>
							<input type="date" bind:value={draftDate} class="w-full rounded border border-hifi-border bg-hifi-surface p-2 text-sm" />
						</label>
						<label class="text-xs">
							<span class="mb-1 block text-hifi-text-muted">Betrag{amountIsEstimate ? ' · geschätzt' : ''}</span>
							<input
								type="number"
								step="0.01"
								min="0"
								bind:value={draftAmount}
								class="w-full rounded border border-hifi-border bg-hifi-surface p-2 text-sm"
							/>
						</label>
						<label class="text-xs">
							<span class="mb-1 block text-hifi-text-muted">Währung{currencyIsEstimate ? ' · geschätzt' : ''}</span>
							<input
								type="text"
								maxlength="3"
								bind:value={draftCurrency}
								class="w-full rounded border border-hifi-border bg-hifi-surface p-2 text-sm uppercase"
							/>
						</label>
						<label class="text-xs">
							<span class="mb-1 block text-hifi-text-muted">Versand{shippingIsEstimate ? ' · geschätzt' : ''}</span>
							<input
								type="number"
								step="0.01"
								min="0"
								bind:value={draftShippingCost}
								class="w-full rounded border border-hifi-border bg-hifi-surface p-2 text-sm"
							/>
						</label>
						<label class="text-xs">
							<span class="mb-1 block text-hifi-text-muted">Rabatt{discountIsEstimate ? ' · geschätzt' : ''}</span>
							<input
								type="number"
								step="0.01"
								min="0"
								bind:value={draftDiscountAmount}
								class="w-full rounded border border-hifi-border bg-hifi-surface p-2 text-sm"
							/>
						</label>
						<label class="text-xs">
							<span class="mb-1 block text-hifi-text-muted">Steuer{taxIsEstimate ? ' · geschätzt' : ''}</span>
							<input
								type="number"
								step="0.01"
								min="0"
								bind:value={draftTaxAmount}
								class="w-full rounded border border-hifi-border bg-hifi-surface p-2 text-sm"
							/>
						</label>
					</div>
					<label class="flex items-center gap-2 text-xs">
						<input type="checkbox" bind:checked={draftHighValue} />
						<span>Hochwertiger Kauf</span>
					</label>
					<div class="text-xs">
						<span id="receipt-category-label" class="mb-1 block text-hifi-text-muted">Kategorie</span>
						<CustomSelect
							bind:value={draftCategory}
							labelledBy="receipt-category-label"
							options={[{ value: '', label: 'Keine' }, ...CATEGORIES]}
						/>
					</div>
					{#each categoryFields(draftCategory || null) as field (field.key)}
						<label class="text-xs">
							<span class="mb-1 block text-hifi-text-muted">
								{field.label}{field.unit ? ` (${field.unit})` : ''}
							</span>
							{#if field.type === 'number'}
								<input
									type="number"
									bind:value={draftCustomFields[field.key]}
									class="w-full rounded border border-hifi-border bg-hifi-surface p-2 text-sm"
								/>
							{:else}
								<input
									type="text"
									bind:value={draftCustomFields[field.key]}
									class="w-full rounded border border-hifi-border bg-hifi-surface p-2 text-sm"
								/>
							{/if}
						</label>
					{/each}
					{#if unselectedSuggestions.length > 0}
						<!-- Klick mutiert NUR draftTagIds (kein sofortiger PATCH) — identisches Verhalten
						     zu TagPickers internem addTag(). Speichern läuft über den bestehenden
						     Save-Button im Formular. Gestrichelter statt gefüllter Rahmen grenzt
						     "Vorschlag, noch nicht übernommen" visuell von bereits zugewiesenen Tags
						     (TagPicker selbst, gefüllte Chips) ab. -->
						<div class="text-xs">
							<span class="mb-1 block text-hifi-text-muted">Vorschlag aus Händler-Historie</span>
							<div class="flex flex-wrap gap-1.5">
								{#each unselectedSuggestions as tag (tag.id)}
									<button
										type="button"
										on:click={() => (draftTagIds = [...draftTagIds, tag.id])}
										class="flex items-center gap-1 rounded-full border border-dashed px-2.5 py-0.5 text-xs font-medium"
										style="border-color: {tagColorVar(tag.color)}; color: {tagColorVar(tag.color)};"
									>
										+ {tag.name}
									</button>
								{/each}
							</div>
						</div>
					{/if}
					<TagPicker bind:selectedTagIds={draftTagIds} />
					<label class="text-xs">
						<span class="mb-1 block text-hifi-text-muted">Garantie (Monate)</span>
						<input
							type="number"
							min="0"
							max="600"
							bind:value={draftWarrantyMonths}
							placeholder="z. B. 24"
							class="w-full rounded border border-hifi-border bg-hifi-surface p-2 text-sm"
						/>
					</label>
					{#if saveError}
						<p class="text-xs text-danger">{saveError}</p>
					{/if}
					<div class="flex gap-2">
						<button
							on:click={saveEdit}
							disabled={saving}
							class="rounded-[10px] bg-hifi-accent px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
						>
							{saving ? 'Speichert …' : 'Speichern'}
						</button>
						<button on:click={cancelEdit} class="text-xs text-hifi-text-muted hover:text-hifi-text">Abbrechen</button>
					</div>
				</div>
			{:else}
				{#if merchantName}
					<div class="text-[13.5px] font-bold text-hifi-text">{merchantName}</div>
				{/if}
				<div class="flex items-start justify-between gap-3">
					<div class="min-w-0">
						<div class="mb-1 text-[12px] text-hifi-text-muted">
							{receiptDate ? formatDate(receiptDate) : 'Datum folgt (OCR/KI)'}{#if dateIsEstimate && receiptDate}<span class="text-hifi-accent-text"> · geschätzt</span>{/if}
						</div>
						<div class="text-2xl font-bold">
							{totalAmount !== null ? `${totalAmount.toFixed(2)} ${currency}` : 'Betrag folgt (OCR/KI)'}{#if amountIsEstimate && totalAmount !== null}<span class="text-sm font-normal text-hifi-accent-text"> · geschätzt</span>{/if}
						</div>
						{#if adjustmentParts.length > 0}
							<div class="mt-1 text-[12px] text-hifi-text-muted">
								{adjustmentParts.join(' · ')}
							</div>
						{/if}
					</div>
					<!-- Kompakter KI-Status-Chip: ersetzt den früheren vollbreiten "KI-Zusammenfassung"-
					     Block unterhalb der Artikel-Liste — direkt neben dem Betrag platziert, damit die
					     Artikel-Liste darunter mehr vertikale Höhe zur Verfügung hat. Knapp beschriftet
					     (Chip statt Absatz); der volle Text bleibt für Maus-Nutzer über title und für
					     Screenreader über aria-label erreichbar, wo er über die Kurzbeschriftung
					     hinausgeht (KI-Vorschlag/Prüfung-nötig-Fall). -->
					<div class="flex-none">
						{#if status === 'pending'}
							<div
								class="flex items-center gap-1 rounded-full bg-hifi-accent-tint px-2.5 py-1.5 text-[11px] font-semibold text-hifi-accent-text"
								title="Wird analysiert …"
							>
								<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="flex-none">
									<path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z" />
								</svg>
								Wird analysiert …
							</div>
						{:else if hasSuggestion}
							<div class="flex flex-col items-end gap-1.5 rounded-[12px] bg-hifi-accent-tint px-2.5 py-2 text-[11px] text-hifi-accent-text">
								<div class="flex items-center gap-1 font-semibold">
									<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="flex-none">
										<path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z" />
									</svg>
									KI-Vorschlag
								</div>
								{#if aiSuggestedMerchantName}
									<div class="max-w-[9rem] truncate text-right text-hifi-text" title={aiSuggestedMerchantName}>
										{aiSuggestedMerchantName}
									</div>
								{/if}
								<div class="flex gap-2">
									<button
										type="button"
										on:click={acceptSuggestion}
										disabled={suggestionSaving}
										class="font-semibold text-hifi-accent hover:underline disabled:opacity-50"
									>
										Übernehmen
									</button>
									<button
										type="button"
										on:click={dismissSuggestion}
										disabled={suggestionSaving}
										class="text-hifi-text-muted hover:text-hifi-text disabled:opacity-50"
									>
										Verwerfen
									</button>
								</div>
							</div>
						{:else if status === 'needs_review' && aiExtractionNote}
							<div
								class="flex items-center gap-1 rounded-full border border-status-warning-border bg-status-warning-bg px-2.5 py-1.5 text-[11px] font-semibold text-status-warning"
								title={aiExtractionNote}
								aria-label={`KI-Hinweis: ${aiExtractionNote}`}
							>
								<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="flex-none">
									<path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z" />
								</svg>
								Prüfung nötig
							</div>
						{:else if !aiExtractedAt}
							<div
								class="flex items-center gap-1 rounded-full bg-hifi-accent-tint px-2.5 py-1.5 text-[11px] font-semibold text-hifi-accent-text"
								title="Noch keine KI-Analyse für diesen Beleg."
							>
								<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="flex-none">
									<path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z" />
								</svg>
								Keine KI-Analyse
							</div>
						{:else}
							<div
								class="flex items-center gap-1 rounded-full bg-hifi-accent-tint px-2.5 py-1.5 text-[11px] font-semibold text-hifi-accent-text"
								title="Beleg wurde von der KI geprüft — keine neuen Vorschläge."
							>
								<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="flex-none">
									<path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z" />
								</svg>
								KI geprüft
							</div>
						{/if}
					</div>
				</div>
				{#if customFields}
					{#each categoryFields(category) as field (field.key)}
						{#if customFields[field.key] !== undefined && customFields[field.key] !== null}
							<div class="text-[12px] text-hifi-text-muted">
								{field.label}: <span class="font-semibold text-hifi-text"
									>{customFields[field.key]}{field.unit ? ` ${field.unit}` : ''}</span
								>
							</div>
						{/if}
					{/each}
				{/if}
			{/if}

			{#if warrantyStatus}
				<div
					class="rounded-[14px] border p-3 text-sm"
					class:border-success-border={warrantyStatus.level === 'ok'}
					class:bg-success-bg={warrantyStatus.level === 'ok'}
					class:border-status-warning-border={warrantyStatus.level === 'warning'}
					class:bg-status-warning-bg={warrantyStatus.level === 'warning'}
					class:border-danger-border={warrantyStatus.level === 'expired'}
					class:bg-danger-bg={warrantyStatus.level === 'expired'}
				>
					{warrantyStatus.label}
				</div>
			{:else}
				<div class="rounded-[14px] border border-hifi-border bg-hifi-surface p-3 text-sm text-hifi-text-muted">
					Kein Garantie-Tracking hinterlegt
				</div>
			{/if}

			<div
				class="rounded-[14px] border border-hifi-border sm:flex sm:flex-1 sm:min-h-0 sm:flex-col"
			>
				<button
					type="button"
					class="flex w-full flex-none items-center justify-between px-3 py-2.5 text-left"
					on:click={() => (itemsExpanded = !itemsExpanded)}
					aria-expanded={itemsExpanded}
				>
					<span class="text-[13.5px] font-bold text-hifi-text">Artikel ({items.length})</span>
					<svg
						width="14"
						height="14"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						class="text-hifi-text-muted"
						class:rotate-180={!itemsExpanded}
						aria-hidden="true"
					>
						<path d="M6 9l6 6 6-6" />
					</svg>
				</button>
				{#if itemsIncomplete && itemsSumDiff !== null}
					<div class="flex-none border-t border-status-warning-border bg-status-warning-bg px-3 py-2 text-xs text-status-warning">
						{#if itemsSumDiff > 0}
							Noch {itemsSumDiff.toFixed(2)} {currency} nicht auf Artikel aufgeteilt.
						{:else}
							Artikel-Summe liegt {Math.abs(itemsSumDiff).toFixed(2)} {currency} über dem Bon-Betrag.
						{/if}
						{#if hasAdjustments}
							<span class="text-hifi-text-muted"> (Versand/Rabatt/Steuer bereits berücksichtigt)</span>
						{/if}
					</div>
				{/if}
				{#if itemsExpanded}
					<!-- Einziger Bereich der rechten Spalte, der noch eigenständig scrollt (siehe
					     Kommentar an der äußeren Card oben) -- sm:overflow-y-auto zusammen mit
					     sm:flex-1/sm:min-h-0 lässt diesen Abschnitt genau den Platz einnehmen, der
					     nach den fix sichtbaren Geschwister-Elementen (Header-Button,
					     Unvollständig-Hinweis, Erkannter-Text [nur maximiert], Aktionsleiste) noch
					     übrig bleibt. Der KI-Status-Chip sitzt seit der Verschlankung nicht mehr hier,
					     sondern kompakt oben neben dem Betrag (siehe Datum/Betrag-Zeile). -->
					<div class="border-t border-hifi-border p-3 sm:min-h-0 sm:flex-1 sm:overflow-y-auto">
						{#if items.length === 0}
							<p class="mb-3 text-xs text-hifi-text-muted">Noch keine Artikel erfasst.</p>
						{:else}
							<ul class="mb-3 flex flex-col gap-2">
								{#each items as item (item.id)}
									<li class="text-sm">
										{#if editingItemId === item.id}
											<div class="flex flex-col gap-1.5 rounded border border-hifi-border bg-hifi-surface p-2">
												<input
													type="text"
													bind:value={editItemName}
													placeholder="Artikelname"
													class="rounded border border-hifi-border bg-hifi-surface p-1.5 text-xs"
												/>
												<div class="grid grid-cols-2 gap-1.5 sm:grid-cols-4">
													<input
														type="number"
														step="0.001"
														min="0"
														bind:value={editItemQuantity}
														placeholder="Menge"
														class="rounded border border-hifi-border bg-hifi-surface p-1.5 text-xs"
													/>
													<input
														type="text"
														bind:value={editItemUnit}
														placeholder="Einheit"
														class="rounded border border-hifi-border bg-hifi-surface p-1.5 text-xs"
													/>
													<input
														type="number"
														step="0.01"
														min="0"
														bind:value={editItemUnitPrice}
														placeholder="€/Stk"
														class="rounded border border-hifi-border bg-hifi-surface p-1.5 text-xs"
													/>
													<input
														type="number"
														step="0.01"
														min="0"
														bind:value={editItemTotalPrice}
														on:input={() => (editItemTotalPriceTouched = true)}
														placeholder="Gesamt €"
														class="rounded border border-hifi-border bg-hifi-surface p-1.5 text-xs"
													/>
												</div>
												<input
													type="number"
													step="0.01"
													min="0"
													bind:value={editItemDiscountAmount}
													placeholder="Rabatt €"
													class="rounded border border-hifi-border bg-hifi-surface p-1.5 text-xs"
												/>
												<div class="grid grid-cols-2 gap-1.5">
													<input
														type="number"
														step="0.001"
														min="0"
														bind:value={editItemPackAmount}
														placeholder="Menge/Einheit, z.B. 1.5"
														class="rounded border border-hifi-border bg-hifi-surface p-1.5 text-xs"
													/>
													<input
														type="text"
														bind:value={editItemPackUnit}
														placeholder="Einheit, z.B. l"
														class="rounded border border-hifi-border bg-hifi-surface p-1.5 text-xs"
													/>
												</div>
												{#if editItemTotalAmount !== null}
													<p class="text-xs text-hifi-text-muted">
														= {editItemTotalAmount} {editItemPackUnit} gesamt
													</p>
												{/if}
												<div class="flex gap-2">
													<button on:click={() => saveEditItem(item.id)} class="text-xs font-semibold text-hifi-accent-text">
														Speichern
													</button>
													<button on:click={cancelEditItem} class="text-xs text-hifi-text-muted hover:text-hifi-text">
														Abbrechen
													</button>
												</div>
											</div>
										{:else}
											<div class="flex items-center justify-between gap-2">
												<div class="min-w-0 flex-1">
													<div class="truncate text-[13.5px] font-bold text-hifi-text">{item.raw_name}</div>
													<div class="text-[12px] text-hifi-text-muted">
														{item.quantity}{item.unit ? ` ${item.unit}` : ''}{item.unit_price !== null
															? ` · ${item.unit_price.toFixed(2)} €/Stk`
															: ''}{item.pack_amount !== null && item.pack_unit
															? ` · ${item.pack_amount} ${item.pack_unit}/Stk = ${(item.quantity * item.pack_amount).toFixed(2)} ${item.pack_unit} gesamt`
															: ''}
													</div>
													{#if item.discount_amount !== null}
														<div class="text-[12px] text-hifi-text-muted">
															Rabatt −{item.discount_amount.toFixed(2)} {currency}
														</div>
													{/if}
												</div>
												<div class="flex flex-none items-center gap-2">
													<span class="font-mono text-sm">{item.total_price.toFixed(2)} €</span>
													<button on:click={() => startEditItem(item)} aria-label="Artikel bearbeiten" class="text-hifi-text-muted hover:text-hifi-text">
														<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
															<path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z" />
														</svg>
													</button>
													<button on:click={() => deleteItem(item.id)} aria-label="Artikel löschen" class="text-hifi-text-muted hover:text-danger">
														<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
															<path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6" />
														</svg>
													</button>
												</div>
											</div>
										{/if}
									</li>
								{/each}
							</ul>
						{/if}

						{#if addingItem}
							<div class="flex flex-col gap-1.5 rounded border border-hifi-border bg-hifi-surface p-2">
								<input
									type="text"
									bind:value={newItemName}
									placeholder="Artikelname"
									class="rounded border border-hifi-border bg-hifi-surface p-1.5 text-xs"
								/>
								<div class="grid grid-cols-2 gap-1.5 sm:grid-cols-4">
									<input
										type="number"
										step="0.001"
										min="0"
										bind:value={newItemQuantity}
										placeholder="Menge"
										class="rounded border border-hifi-border bg-hifi-surface p-1.5 text-xs"
									/>
									<input
										type="text"
										bind:value={newItemUnit}
										placeholder="Einheit"
										class="rounded border border-hifi-border bg-hifi-surface p-1.5 text-xs"
									/>
									<input
										type="number"
										step="0.01"
										min="0"
										bind:value={newItemUnitPrice}
										placeholder="€/Stk"
										class="rounded border border-hifi-border bg-hifi-surface p-1.5 text-xs"
									/>
									<input
										type="number"
										step="0.01"
										min="0"
										bind:value={newItemTotalPrice}
										on:input={() => (newItemTotalPriceTouched = true)}
										placeholder="Gesamt €"
										class="rounded border border-hifi-border bg-hifi-surface p-1.5 text-xs"
									/>
								</div>
								<input
									type="number"
									step="0.01"
									min="0"
									bind:value={newItemDiscountAmount}
									placeholder="Rabatt €"
									class="rounded border border-hifi-border bg-hifi-surface p-1.5 text-xs"
								/>
								<div class="grid grid-cols-2 gap-1.5">
									<input
										type="number"
										step="0.001"
										min="0"
										bind:value={newItemPackAmount}
										placeholder="Menge/Einheit, z.B. 1.5"
										class="rounded border border-hifi-border bg-hifi-surface p-1.5 text-xs"
									/>
									<input
										type="text"
										bind:value={newItemPackUnit}
										placeholder="Einheit, z.B. l"
										class="rounded border border-hifi-border bg-hifi-surface p-1.5 text-xs"
									/>
								</div>
								{#if newItemTotalAmount !== null}
									<p class="text-xs text-hifi-text-muted">= {newItemTotalAmount} {newItemPackUnit} gesamt</p>
								{/if}
								<div class="flex gap-2">
									<button on:click={addItem} class="text-xs font-semibold text-hifi-accent-text">Hinzufügen</button>
									<button
										on:click={() => {
											addingItem = false;
											resetNewItemForm();
										}}
										class="text-xs text-hifi-text-muted hover:text-hifi-text"
									>
										Abbrechen
									</button>
								</div>
							</div>
						{:else}
							<button on:click={() => (addingItem = true)} class="text-xs font-semibold text-hifi-accent-text">
								+ Artikel hinzufügen
							</button>
						{/if}
					</div>
				{/if}
			</div>

			{#if maximized && ocrRawText}
				<!-- "Erkannter Text" (OCR-Rohtext) nur im Maximieren-Modus: im normalen, platzknappen
				     Layout blendet dieser Abschnitt sonst die Artikel-Liste stark ein; im maximierten
				     Zustand ist genug Platz vorhanden. -->
				<div class="rounded-[14px] border border-hifi-border">
					<button
						type="button"
						class="flex w-full items-center justify-between px-3 py-2.5 text-left"
						on:click={() => (ocrTextExpanded = !ocrTextExpanded)}
						aria-expanded={ocrTextExpanded}
					>
						<span class="text-[13.5px] font-bold text-hifi-text">Erkannter Text</span>
						<svg
							width="14"
							height="14"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
							class="text-hifi-text-muted"
							class:rotate-180={!ocrTextExpanded}
							aria-hidden="true"
						>
							<path d="M6 9l6 6 6-6" />
						</svg>
					</button>
					{#if ocrTextExpanded}
						<div class="max-h-40 overflow-auto border-t border-hifi-border bg-hifi-surface p-3 text-xs text-hifi-text-muted">
							{ocrRawText}
						</div>
					{/if}
				</div>
			{/if}

			<div class="mt-auto flex gap-2 border-t border-hifi-border pt-4">
				<button
					on:click={reanalyze}
					disabled={reanalyzing || status === 'pending'}
					aria-label="Neu analysieren"
					title="Neu analysieren"
					class="flex h-11 w-11 items-center justify-center rounded-full border border-hifi-border text-hifi-text-muted hover:border-hifi-accent hover:text-hifi-accent-text disabled:opacity-40"
				>
					<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 2v6h-6" /><path d="M3 12a9 9 0 0 1 15-6.7L21 8" /><path d="M3 22v-6h6" /><path d="M21 12a9 9 0 0 1-15 6.7L3 16" /></svg>
				</button>
				<button
					on:click={() => (shareModalOpen = true)}
					aria-label={m.shareManage.buttonLabel}
					title={m.shareManage.buttonLabel}
					class="flex h-11 w-11 items-center justify-center rounded-full border border-hifi-border text-hifi-text-muted hover:border-hifi-accent hover:text-hifi-accent-text"
				>
					<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><path d="M8.6 13.5l6.8 3.9M15.4 6.6L8.6 10.5" /></svg>
				</button>
				<button
					on:click={deleteReceipt}
					disabled={deleting}
					aria-label="Beleg löschen"
					title="Beleg löschen"
					class="flex h-11 w-11 items-center justify-center rounded-full border border-hifi-border text-hifi-text-muted hover:border-danger-border hover:text-danger disabled:opacity-40"
				>
					<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6" /></svg>
				</button>
			</div>
		</div>
	</div>
</div>

{#if shareModalOpen}
	<ShareManagementModal {receiptId} onClose={() => (shareModalOpen = false)} />
{/if}
