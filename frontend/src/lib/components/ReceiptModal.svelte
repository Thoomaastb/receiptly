<script lang="ts">
	import { onMount } from 'svelte';

	export let receiptDate: string | null;
	export let totalAmount: number | null;
	export let currency: string;
	export let status: string;
	export let ocrRawText: string | null;
	export let originRect: DOMRect;
	export let onClose: () => void;

	let modalEl: HTMLElement;
	let backdropOpacity = 0;
	let contentVisible = false;
	let closing = false;

	const reducedMotion =
		typeof window !== 'undefined' &&
		window.matchMedia('(prefers-reduced-motion: reduce)').matches;

	const OPEN_MS = 380;
	const CLOSE_MS = 260;
	const OVERSHOOT_EASE = 'cubic-bezier(0.34, 1.56, 0.64, 1)';
	const EASE_IN = 'cubic-bezier(.4,0,.2,1)';

	function targetRect() {
		const width = Math.min(480, window.innerWidth - 32);
		const height = Math.min(560, window.innerHeight - 64);
		return {
			top: (window.innerHeight - height) / 2,
			left: (window.innerWidth - width) / 2,
			width,
			height
		};
	}

	onMount(() => {
		if (!modalEl) return;

		if (reducedMotion) {
			const t = targetRect();
			Object.assign(modalEl.style, {
				top: `${t.top}px`,
				left: `${t.left}px`,
				width: `${t.width}px`,
				height: `${t.height}px`,
				borderRadius: '12px'
			});
			backdropOpacity = 1;
			contentVisible = true;
			return;
		}

		// FLIP: erst exakt an der Kartenposition platzieren (First), dann zur Modal-Position
		// animieren (Last), Browser interpoliert (Invert+Play) über die CSS-Transition.
		Object.assign(modalEl.style, {
			top: `${originRect.top}px`,
			left: `${originRect.left}px`,
			width: `${originRect.width}px`,
			height: `${originRect.height}px`,
			borderRadius: '12px',
			transition: 'none'
		});

		requestAnimationFrame(() => {
			const t = targetRect();
			modalEl.style.transition = `top ${OPEN_MS}ms ${OVERSHOOT_EASE}, left ${OPEN_MS}ms ${OVERSHOOT_EASE}, width ${OPEN_MS}ms ${OVERSHOOT_EASE}, height ${OPEN_MS}ms ${OVERSHOOT_EASE}, border-radius ${OPEN_MS}ms ${OVERSHOOT_EASE}`;
			modalEl.style.top = `${t.top}px`;
			modalEl.style.left = `${t.left}px`;
			modalEl.style.width = `${t.width}px`;
			modalEl.style.height = `${t.height}px`;
			backdropOpacity = 1;
			setTimeout(() => (contentVisible = true), OPEN_MS * 0.4);
		});
	});

	function handleClose() {
		if (closing) return;
		closing = true;
		contentVisible = false;
		backdropOpacity = 0;

		if (reducedMotion) {
			onClose();
			return;
		}

		modalEl.style.transition = `top ${CLOSE_MS}ms ${EASE_IN}, left ${CLOSE_MS}ms ${EASE_IN}, width ${CLOSE_MS}ms ${EASE_IN}, height ${CLOSE_MS}ms ${EASE_IN}, border-radius ${CLOSE_MS}ms ${EASE_IN}`;
		modalEl.style.top = `${originRect.top}px`;
		modalEl.style.left = `${originRect.left}px`;
		modalEl.style.width = `${originRect.width}px`;
		modalEl.style.height = `${originRect.height}px`;
		setTimeout(onClose, CLOSE_MS);
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
</script>

<svelte:window on:keydown={handleKeydown} />

<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
<div
	class="fixed inset-0 z-40 bg-black"
	style="opacity: {backdropOpacity * 0.5}; -webkit-backdrop-filter: blur({backdropOpacity * 4}px); backdrop-filter: blur({backdropOpacity * 4}px); transition-property: opacity, backdrop-filter, -webkit-backdrop-filter; transition-duration: {reducedMotion
		? '0ms'
		: '260ms'};"
	on:click={handleClose}
	role="presentation"
></div>

<div
	bind:this={modalEl}
	class="fixed z-50 overflow-hidden border border-border bg-surface shadow-none"
	role="dialog"
	aria-modal="true"
>
	<div class="flex h-full flex-col p-5 transition-opacity duration-150" class:opacity-0={!contentVisible}>
		<div class="mb-4 flex items-center justify-between">
			<span class="text-sm text-text-muted">{receiptDate ?? 'Datum folgt (OCR/KI)'}</span>
			<button
				on:click={handleClose}
				aria-label="Schließen"
				class="rounded-full p-1 text-text-muted hover:text-text"
			>
				✕
			</button>
		</div>
		<div class="mb-4 text-2xl font-medium">
			{totalAmount !== null ? `${totalAmount.toFixed(2)} ${currency}` : 'Betrag folgt (OCR/KI)'}
		</div>
		<div class="mb-4 text-xs text-text-muted">{statusLabel(status)}</div>
		{#if ocrRawText}
			<div class="flex-1 overflow-auto rounded-lg border border-border bg-surface-raised p-3 text-xs text-text-muted">
				{ocrRawText}
			</div>
		{:else}
			<div class="flex-1 rounded-lg border border-border bg-surface-raised p-3 text-xs text-text-muted">
				Noch kein OCR-Text vorhanden.
			</div>
		{/if}
	</div>
</div>
