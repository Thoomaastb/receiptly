<script lang="ts">
	import { onMount } from 'svelte';

	export let receiptId: string;
	export let receiptDate: string | null;
	export let totalAmount: number | null;
	export let currency: string;
	export let status: string;
	export let ocrRawText: string | null;
	export let isHighValue: boolean = false;
	export let warrantyExpiresAt: string | null = null;
	export let onClose: () => void;

	let visible = false;
	let closing = false;

	const reducedMotion =
		typeof window !== 'undefined' &&
		window.matchMedia('(prefers-reduced-motion: reduce)').matches;

	// Exakt laut Hifi-Handoff: Scale (0.98→1) + Opacity-Fade, 340ms öffnen / 260ms schließen,
	// cubic-bezier(0.22,1,0.36,1). Kein Positions-Morphing vom Kartenort mehr (das alte
	// FLIP-System war fehleranfällig — Ursache der gemeldeten Animations-Bugs).
	const OPEN_MS = 340;
	const CLOSE_MS = 260;
	const EASE = 'cubic-bezier(0.22,1,0.36,1)';

	onMount(() => {
		requestAnimationFrame(() => {
			visible = true;
		});
	});

	function handleClose() {
		if (closing) return;
		closing = true;
		visible = false;
		setTimeout(onClose, reducedMotion ? 0 : CLOSE_MS);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') handleClose();
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

	// Garantie-Status-Logik exakt laut Handoff: expired <0 Tage, warning 0-30, ok >30
	$: warrantyStatus = (() => {
		if (!warrantyExpiresAt) return null;
		const days = (new Date(warrantyExpiresAt).getTime() - Date.now()) / 86_400_000;
		if (days < 0) return { level: 'expired', label: 'Garantie abgelaufen' };
		if (days <= 30) return { level: 'warning', label: 'Garantie läuft bald ab' };
		return { level: 'ok', label: 'Garantie aktiv' };
	})();

	const currentDuration = () => (closing ? CLOSE_MS : OPEN_MS);
</script>

<svelte:window on:keydown={handleKeydown} />

<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
<div
	class="fixed inset-0 z-40 bg-black"
	style="opacity: {visible ? 0.5 : 0}; -webkit-backdrop-filter: blur({visible ? 4 : 0}px); backdrop-filter: blur({visible ? 4 : 0}px); transition-property: opacity, backdrop-filter, -webkit-backdrop-filter; transition-duration: {reducedMotion ? '0ms' : `${currentDuration()}ms`}; transition-timing-function: {EASE};"
	on:click={handleClose}
	role="presentation"
></div>

<div
	class="fixed left-1/2 top-1/2 z-50 max-h-[85vh] w-[92vw] max-w-3xl overflow-auto rounded-[20px] border border-border bg-surface"
	style="transform: translate(-50%, -50%) scale({visible ? 1 : 0.98}); opacity: {visible ? 1 : 0}; transition-property: transform, opacity; transition-duration: {reducedMotion ? '0ms' : `${currentDuration()}ms`}; transition-timing-function: {EASE};"
	role="dialog"
	aria-modal="true"
	aria-label="Beleg-Detail"
>
	<div class="grid grid-cols-1 gap-0 sm:grid-cols-[1.1fr_0.9fr]">
		<!-- Links: Vorschau-Panel (Platzhalter, echtes PDF/Bild-Rendering ist eigenes Paket) -->
		<div class="relative flex min-h-[320px] items-center justify-center sm:min-h-[520px]" style="background: repeating-linear-gradient(135deg, oklch(58% 0.19 290 / 0.08) 0, oklch(58% 0.19 290 / 0.08) 10px, oklch(58% 0.19 290 / 0.03) 10px, oklch(58% 0.19 290 / 0.03) 20px);">
			<span class="rounded-md bg-white/80 px-3 py-1.5 font-mono text-xs font-semibold text-accent">
				Vorschau folgt
			</span>
			<button
				class="absolute bottom-4 right-4 flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-2 text-xs font-medium"
				disabled
				data-receipt-id={receiptId}
				title="Download folgt, sobald echte Dateivorschau existiert"
			>
				<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<path d="M12 3v12M7 10l5 5 5-5" /><path d="M5 21h14" />
				</svg>
				Herunterladen
			</button>
		</div>

		<!-- Rechts: Metadaten -->
		<div class="flex flex-col gap-4 p-6">
			<div class="flex items-start justify-between">
				<div class="flex flex-wrap gap-1.5">
					<span class="rounded-full bg-surface-raised px-2.5 py-0.5 text-xs font-medium text-text-muted">
						{statusLabel(status)}
					</span>
					{#if isHighValue}
						<span class="rounded-full bg-accent px-2.5 py-0.5 text-xs font-medium text-accent-contrast">
							Hochwertig
						</span>
					{/if}
				</div>
				<button on:click={handleClose} aria-label="Schließen" class="rounded-full p-1 text-text-muted hover:text-text">
					✕
				</button>
			</div>

			<div>
				<div class="mb-1 text-xs text-text-muted">{receiptDate ?? 'Datum folgt (OCR/KI)'}</div>
				<div class="text-2xl font-bold">
					{totalAmount !== null ? `${totalAmount.toFixed(2)} ${currency}` : 'Betrag folgt (OCR/KI)'}
				</div>
			</div>

			{#if warrantyStatus}
				<div
					class="rounded-lg border p-3 text-sm"
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
				<div class="rounded-lg border border-border bg-surface-raised p-3 text-sm text-text-muted">
					Kein Garantie-Tracking hinterlegt
				</div>
			{/if}

			<div class="rounded-lg border border-border bg-hifi-accent-tint p-3.5">
				<div class="mb-1.5 flex items-center gap-1.5 text-xs font-bold" style="color: var(--color-accent-text, var(--color-accent));">
					<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						<path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z" />
					</svg>
					KI-Zusammenfassung
				</div>
				<div class="text-xs text-text-muted">
					Noch keine KI-Analyse — das Struktur-Extraktions-Paket ist noch nicht gebaut.
				</div>
			</div>

			{#if ocrRawText}
				<div class="max-h-40 overflow-auto rounded-lg border border-border bg-surface-raised p-3 text-xs text-text-muted">
					{ocrRawText}
				</div>
			{/if}

			<div class="mt-auto flex gap-2 border-t border-border pt-4">
				<button disabled title="Folgt in einem späteren Paket" class="flex h-9 w-9 items-center justify-center rounded-full border border-border text-text-muted disabled:opacity-40">
					<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z" /></svg>
				</button>
				<button disabled title="Folgt in einem späteren Paket" class="flex h-9 w-9 items-center justify-center rounded-full border border-border text-text-muted disabled:opacity-40">
					<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4" /></svg>
				</button>
				<button disabled title="Folgt in einem späteren Paket" class="flex h-9 w-9 items-center justify-center rounded-full border border-border text-text-muted disabled:opacity-40">
					<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6" /></svg>
				</button>
			</div>
		</div>
	</div>
</div>
