<script lang="ts">
	import BucketPill from './BucketPill.svelte';
	import Logo from './Logo.svelte';
	import { formatDate } from '$lib/formatDate';
	import { tagColorVar, type Tag } from '$lib/tags';
	import { m } from '$lib/i18n';

	export let id: string;
	export let receiptDate: string | null;
	export let totalAmount: number | null;
	export let currency: string;
	export let status: string;
	export let merchantName: string | null = null;
	// Bestätigter Titel (siehe concepts/beleg-titel.md) — ReceiptListItem liefert KEIN
	// ai_suggested_title (nur ReceiptDetail hat das Feld), die Fallback-Kette ist hier
	// deshalb kürzer als in ReceiptDetailView.
	export let title: string | null = null;
	export let itemCount = 0;
	export let tags: Tag[] = [];
	export let bucketName: string;
	export let bucketIsDefault: boolean;
	export let showBucketPill = true;
	export let thumbUrl: string | null = null;
	export let onOpen: (id: string) => void;

	// Nur reine Anzeige (keine Zuweisung/Entfernen hier, siehe TagPicker in
	// ReceiptDetailView) — begrenzt auf 3 Chips + "+N"-Overflow, damit eine Zeile mit vielen
	// Tags die kompakte Listenzeile nicht sprengt.
	const MAX_VISIBLE_TAGS = 3;
	$: visibleTags = tags.slice(0, MAX_VISIBLE_TAGS);
	$: overflowCount = tags.length - visibleTags.length;

	// GET /thumb liefert 404, wenn kein serverseitiges Thumbnail existiert (alte Belege,
	// fehlgeschlagene Generierung) — der Browser feuert dann on:error auf dem <img>, und wir
	// fallen dauerhaft auf das SVG-Platzhalter-Icon zurück statt ein kaputtes Bild zu zeigen.
	let thumbFailed = false;
	$: showThumb = !!thumbUrl && !thumbFailed;

	// Titel wird Hauptzeile, Händler rückt zur Sekundärzeile (siehe concepts/beleg-titel.md
	// Abschnitt 5). Fallback-Kette, damit nie leer: title ?? merchantName ?? "Beleg vom
	// {date}" — fehlt auch das Datum (frisch hochgeladener, noch unanalysierter Beleg),
	// greift ein generischer Platzhalter statt eines kaputten "Beleg vom undefined".
	$: dateLabel = receiptDate ? formatDate(receiptDate) : null;
	$: fallbackTitle = dateLabel
		? m.receiptTitle.fallbackPrefix.replace('{date}', dateLabel)
		: m.receiptTitle.fallbackGeneric;
	$: displayTitle = title ?? merchantName ?? fallbackTitle;
	// Händler nur als Sekundärzeile zeigen, wenn der Titel tatsächlich ein eigenständiger,
	// bestätigter Titel ist -- fällt der Titel selbst schon auf merchantName zurück, wäre
	// eine zweite Zeile mit demselben Text redundant.
	$: showMerchantSubtitle = title !== null && merchantName !== null;

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

	function open() {
		onOpen(id);
	}
</script>

<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
<div
	role="button"
	tabindex="0"
	class="flex w-full items-center gap-4 border-b border-hifi-border px-2 py-3.5 text-left transition-colors hover:bg-hifi-accent-tint"
	on:click={open}
	on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), open())}
>
	{#if showThumb}
		<img
			src={thumbUrl}
			alt={`Beleg-Vorschau: ${displayTitle}`}
			loading="lazy"
			class="h-9 w-9 flex-none rounded-[10px] border border-hifi-border object-cover"
			on:error={() => (thumbFailed = true)}
		/>
	{:else}
		<span class="flex h-9 w-9 flex-none items-center justify-center rounded-[10px] bg-hifi-accent-tint text-hifi-accent-text">
			<Logo size={16} />
		</span>
	{/if}

	<div class="min-w-0 flex-1">
		<div class="truncate text-[13.5px] font-bold text-hifi-text">{displayTitle}</div>
		<div class="mt-0.5 flex min-w-0 items-center gap-2 text-xs text-hifi-text-muted">
			{#if showMerchantSubtitle}
				<span class="truncate">{merchantName}</span>
				<span aria-hidden="true">·</span>
			{/if}
			<span class="shrink-0">{dateLabel ?? 'Datum folgt'}</span>
			{#if itemCount > 0}
				<span class="shrink-0">· {itemCount} Artikel</span>
			{/if}
		</div>
		{#if tags.length > 0}
			<div class="mt-1 flex flex-wrap items-center gap-1">
				{#each visibleTags as tag (tag.id)}
					<span
						class="rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none text-white"
						style="background: {tagColorVar(tag.color)};"
					>
						{tag.name}
					</span>
				{/each}
				{#if overflowCount > 0}
					<span class="rounded-full bg-hifi-bg px-1.5 py-0.5 text-[10px] font-medium leading-none text-hifi-text-faint">
						{m.tags.overflowLabel.replace('{count}', String(overflowCount))}
					</span>
				{/if}
			</div>
		{/if}
	</div>

	<span class="hidden shrink-0 text-xs text-hifi-text-faint sm:inline">{statusLabel(status)}</span>

	{#if showBucketPill}
		<!-- Ausgeblendet bis sm (analog zum Status-Label oben) -- Thumb+Text+Pill+Betrag
		     nebeneinander sprengt sonst die Zeile auf sehr schmalen Screens. -->
		<div class="hidden shrink-0 sm:block"><BucketPill name={bucketName} isDefault={bucketIsDefault} /></div>
	{/if}

	<span class="w-24 shrink-0 text-right font-mono text-[14px] font-bold text-hifi-text">
		{totalAmount !== null ? `${totalAmount.toFixed(2)} ${currency}` : '—'}
	</span>
</div>
