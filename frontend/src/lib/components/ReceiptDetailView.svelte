<script lang="ts">
	import { CATEGORIES, categoryLabel, categoryColor, categoryFields } from '$lib/categories';
	import { formatDate } from '$lib/formatDate';
	import { m } from '$lib/i18n';
	import ShareManagementModal from './ShareManagementModal.svelte';

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

	export let receiptId: string;
	export let receiptDate: string | null;
	export let totalAmount: number | null;
	export let currency: string;
	export let status: string;
	export let merchantName: string | null = null;
	export let category: string | null = null;
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
	export let onBack: () => void;
	export let onUpdated: (() => void) | undefined = undefined;
	export let onDeleted: (() => void) | undefined = undefined;

	const fileUrl = `/api/receipts/${receiptId}/file`;
	$: isImageFile = /\.(jpe?g|png)$/i.test(filePath);

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
	$: itemsSumDiff = totalAmount !== null ? Math.round((totalAmount - itemsSum) * 100) / 100 : null;
	$: itemsIncomplete = items.length > 0 && itemsSumDiff !== null && Math.abs(itemsSumDiff) > 0.004;

	// --- Kernfelder bearbeiten (Datum/Betrag/Händler/Hochwertig/Garantie) ---
	// Manuelle Bearbeitung, solange die KI-Struktur-Extraktion aus dem OCR-Text noch
	// nicht existiert (siehe Backlog) — sonst blieben diese Felder auf ewig leer.
	let editing = false;
	let saving = false;
	let saveError = '';
	let draftDate = '';
	let draftAmount = '';
	let draftMerchant = '';
	let draftHighValue = false;
	let draftWarrantyMonths = '';
	let draftCategory = '';
	// String-Draft je Kategorie-Zusatzfeld (siehe categoryFields) — Keys über alle
	// Kategorien hinweg gesammelt, beim Speichern wird nur auf die Felder der aktuell
	// gewählten Kategorie gefiltert (siehe saveEdit).
	let draftCustomFields: Record<string, string> = {};

	function startEdit() {
		draftDate = receiptDate ?? '';
		draftAmount = totalAmount !== null ? String(totalAmount) : '';
		draftMerchant = merchantName ?? '';
		draftHighValue = isHighValue;
		draftWarrantyMonths = warrantyMonths !== null ? String(warrantyMonths) : '';
		draftCategory = category ?? '';
		draftCustomFields = Object.fromEntries(
			Object.entries(customFields ?? {}).map(([key, value]) => [key, String(value)])
		);
		saveError = '';
		editing = true;
	}

	function cancelEdit() {
		editing = false;
	}

	function applyDetail(detail: {
		receipt_date: string | null;
		total_amount: number | null;
		merchant_name: string | null;
		category: string | null;
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
	}) {
		receiptDate = detail.receipt_date;
		totalAmount = detail.total_amount;
		merchantName = detail.merchant_name;
		category = detail.category;
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
	}

	// --- KI-Struktur-Extraktions-Vorschlag (Übernehmen/Verwerfen/Neu analysieren) ---
	// Kategorie-Vorschlag der KI wird gegen die feste CATEGORIES-Liste geprüft — nur
	// bekannte Werte werden angezeigt/übernommen, sonst bliebe eine Freitext-Kategorie im
	// System, die categoryLabel()/categoryColor() nicht kennen.
	$: validSuggestedCategory =
		aiSuggestedCategory && CATEGORIES.some((c) => c.value === aiSuggestedCategory)
			? aiSuggestedCategory
			: null;
	$: hasSuggestion = !!aiSuggestedMerchantName || !!validSuggestedCategory;

	let suggestionSaving = false;
	let reanalyzing = false;

	async function acceptSuggestion() {
		suggestionSaving = true;
		try {
			const payload: Record<string, unknown> = { dismiss_ai_suggestion: true };
			if (aiSuggestedMerchantName) payload.merchant_name = aiSuggestedMerchantName;
			if (validSuggestedCategory) payload.category = validSuggestedCategory;
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
					merchant_name: draftMerchant.trim() || null,
					is_high_value: draftHighValue,
					warranty_months: draftWarrantyMonths ? Number(draftWarrantyMonths) : null,
					category: draftCategory || null,
					custom_fields: customFieldsPayload
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
	let newItemPackAmount = '';
	let newItemPackUnit = '';

	function resetNewItemForm() {
		newItemName = '';
		newItemQuantity = '1';
		newItemUnit = '';
		newItemUnitPrice = '';
		newItemTotalPrice = '';
		newItemTotalPriceTouched = false;
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

<div>
	<button on:click={onBack} class="mb-4 flex items-center gap-1.5 text-sm font-medium text-hifi-text-muted hover:text-hifi-text">
		<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
			<path d="M15 18l-6-6 6-6" />
		</svg>
		Zurück
	</button>

	<div class="grid grid-cols-1 gap-6 rounded-[20px] border border-hifi-border bg-hifi-surface p-2 sm:grid-cols-[1.1fr_0.9fr]">
		<!-- Links: Vorschau-Panel — Bild direkt eingebettet, PDF als Kachel mit Öffnen-Link
		     (kein <iframe>, um von PDF-Viewer-Eigenheiten je Browser unabhängig zu bleiben) -->
		<div class="relative flex min-h-[320px] items-center justify-center overflow-hidden rounded-2xl bg-hifi-surface sm:min-h-[520px]">
			{#if isImageFile}
				<img src={fileUrl} alt="Beleg-Vorschau" class="h-full max-h-[520px] w-full object-contain" />
			{:else}
				<div class="flex flex-col items-center gap-2" style="background: repeating-linear-gradient(135deg, var(--color-stripe-doc-a) 0, var(--color-stripe-doc-a) 10px, var(--color-stripe-doc-b) 10px, var(--color-stripe-doc-b) 20px); position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;">
					<a
						href={fileUrl}
						target="_blank"
						rel="noopener noreferrer"
						class="flex items-center gap-2 rounded-md bg-hifi-surface/80 px-3 py-1.5 font-mono text-xs font-semibold text-hifi-accent-text hover:bg-hifi-surface"
					>
						PDF-Dokument öffnen
					</a>
				</div>
			{/if}
			<a
				href={fileUrl}
				download
				class="absolute bottom-4 right-4 flex items-center gap-1.5 rounded-[10px] border border-hifi-border bg-hifi-surface px-3 py-2 text-xs font-medium hover:bg-hifi-accent-tint hover:text-hifi-accent-text"
			>
				<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<path d="M12 3v12M7 10l5 5 5-5" /><path d="M5 21h14" />
				</svg>
				Herunterladen
			</a>
		</div>

		<!-- Rechts: Metadaten -->
		<div class="flex flex-col gap-4 p-4 sm:p-2">
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
					<div class="grid grid-cols-2 gap-2">
						<label class="text-xs">
							<span class="mb-1 block text-hifi-text-muted">Datum</span>
							<input type="date" bind:value={draftDate} class="w-full rounded border border-hifi-border bg-hifi-surface p-2 text-sm" />
						</label>
						<label class="text-xs">
							<span class="mb-1 block text-hifi-text-muted">Betrag ({currency})</span>
							<input
								type="number"
								step="0.01"
								min="0"
								bind:value={draftAmount}
								class="w-full rounded border border-hifi-border bg-hifi-surface p-2 text-sm"
							/>
						</label>
					</div>
					<label class="flex items-center gap-2 text-xs">
						<input type="checkbox" bind:checked={draftHighValue} />
						<span>Hochwertiger Kauf</span>
					</label>
					<label class="text-xs">
						<span class="mb-1 block text-hifi-text-muted">Kategorie</span>
						<select
							bind:value={draftCategory}
							disabled={!draftMerchant.trim()}
							class="w-full rounded border border-hifi-border bg-hifi-surface p-2 text-sm disabled:opacity-50"
						>
							<option value="">Keine</option>
							{#each CATEGORIES as cat (cat.value)}
								<option value={cat.value}>{cat.label}</option>
							{/each}
						</select>
						{#if !draftMerchant.trim()}
							<span class="mt-1 block text-hifi-text-muted">Braucht zuerst einen Händlernamen.</span>
						{/if}
					</label>
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
				<div>
					<div class="mb-1 text-[12px] text-hifi-text-muted">{receiptDate ? formatDate(receiptDate) : 'Datum folgt (OCR/KI)'}</div>
					<div class="text-2xl font-bold">
						{totalAmount !== null ? `${totalAmount.toFixed(2)} ${currency}` : 'Betrag folgt (OCR/KI)'}
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

			<div class="rounded-[14px] border border-hifi-border">
				<button
					type="button"
					class="flex w-full items-center justify-between px-3 py-2.5 text-left"
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
					<div class="border-t border-status-warning-border bg-status-warning-bg px-3 py-2 text-xs text-status-warning">
						{#if itemsSumDiff > 0}
							Noch {itemsSumDiff.toFixed(2)} {currency} nicht auf Artikel aufgeteilt.
						{:else}
							Artikel-Summe liegt {Math.abs(itemsSumDiff).toFixed(2)} {currency} über dem Bon-Betrag.
						{/if}
					</div>
				{/if}
				{#if itemsExpanded}
					<div class="border-t border-hifi-border p-3">
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

			{#if status === 'pending'}
				<div class="rounded-[14px] bg-hifi-accent-tint p-3.5">
					<div class="mb-1.5 flex items-center gap-1.5 text-xs font-bold text-hifi-accent-text">
						<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
							<path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z" />
						</svg>
						KI-Zusammenfassung
					</div>
					<div class="text-xs text-hifi-text-muted">Wird analysiert …</div>
				</div>
			{:else if hasSuggestion}
				<div class="rounded-[14px] bg-hifi-accent-tint p-3.5">
					<div class="mb-1.5 flex items-center gap-1.5 text-xs font-bold text-hifi-accent-text">
						<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
							<path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z" />
						</svg>
						KI-Vorschlag
					</div>
					<div class="mb-3 text-xs text-hifi-text">
						{#if aiSuggestedMerchantName}
							<div>Händler: <span class="font-semibold">{aiSuggestedMerchantName}</span></div>
						{/if}
						{#if validSuggestedCategory}
							<div>Kategorie: <span class="font-semibold">{categoryLabel(validSuggestedCategory)}</span></div>
						{/if}
					</div>
					<div class="flex gap-2">
						<button
							on:click={acceptSuggestion}
							disabled={suggestionSaving}
							class="rounded-[10px] bg-hifi-accent px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
						>
							Übernehmen
						</button>
						<button
							on:click={dismissSuggestion}
							disabled={suggestionSaving}
							class="text-xs text-hifi-text-muted hover:text-hifi-text disabled:opacity-50"
						>
							Verwerfen
						</button>
					</div>
				</div>
			{:else if status === 'needs_review' && aiExtractionNote}
				<div class="rounded-[14px] border border-status-warning-border bg-status-warning-bg p-3.5 text-xs text-status-warning">
					<div class="mb-1 flex items-center gap-1.5 font-bold">
						<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
							<path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z" />
						</svg>
						KI-Zusammenfassung
					</div>
					{aiExtractionNote}
				</div>
			{:else}
				<div class="rounded-[14px] bg-hifi-accent-tint p-3.5">
					<div class="mb-1.5 flex items-center gap-1.5 text-xs font-bold text-hifi-accent-text">
						<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
							<path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z" />
						</svg>
						KI-Zusammenfassung
					</div>
					<div class="text-xs text-hifi-text-muted">Noch keine KI-Analyse für diesen Beleg.</div>
				</div>
			{/if}

			{#if ocrRawText}
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
