<script lang="ts">
	import { onMount } from 'svelte';
	import UploadFlow from './UploadFlow.svelte';

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
		const width = Math.min(440, window.innerWidth - 32);
		const height = Math.min(480, window.innerHeight - 64);
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
</script>

<svelte:window on:keydown={handleKeydown} />

<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
<div
	class="fixed inset-0 z-40 bg-black transition-opacity"
	style="opacity: {backdropOpacity * 0.5}; backdrop-filter: blur({backdropOpacity * 4}px); transition-duration: {reducedMotion
		? '0ms'
		: '260ms'};"
	on:click={handleClose}
	role="presentation"
></div>

<div
	bind:this={modalEl}
	class="fixed z-50 overflow-auto border border-border bg-surface"
	role="dialog"
	aria-modal="true"
	aria-label="Beleg hochladen"
>
	<div class="p-5 transition-opacity duration-150" class:opacity-0={!contentVisible}>
		<div class="mb-4 flex items-center justify-between">
			<h2 class="text-lg font-medium">Beleg hochladen</h2>
			<button
				on:click={handleClose}
				aria-label="Schließen"
				class="rounded-full p-1 text-text-muted hover:text-text"
			>
				✕
			</button>
		</div>
		<UploadFlow onSuccess={handleClose} />
	</div>
</div>
