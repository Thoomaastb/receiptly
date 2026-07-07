<script lang="ts">
	import { onMount } from 'svelte';
	import UploadFlow from './UploadFlow.svelte';

	export let onClose: () => void;
	export let captureMode: 'camera' | 'file' = 'file';

	let visible = false;
	let closing = false;

	const reducedMotion =
		typeof window !== 'undefined' &&
		window.matchMedia('(prefers-reduced-motion: reduce)').matches;

	// Gleiche Scale+Fade-Sprache wie die Beleg-Detail-Ansicht laut Hifi-Handoff,
	// hier weiterhin als Modal (dein eigener "on-the-fly"-Wunsch, nicht Teil des Mockups)
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
	class="fixed left-1/2 top-1/2 z-50 max-h-[85vh] w-[92vw] max-w-md overflow-auto rounded-[20px] border border-border bg-surface p-5"
	style="transform: translate(-50%, -50%) scale({visible ? 1 : 0.98}); opacity: {visible ? 1 : 0}; transition-property: transform, opacity; transition-duration: {reducedMotion ? '0ms' : `${currentDuration()}ms`}; transition-timing-function: {EASE};"
	role="dialog"
	aria-modal="true"
	aria-label="Beleg hochladen"
>
	<div class="mb-4 flex items-center justify-between">
		<h2 class="text-lg font-medium">{captureMode === 'camera' ? 'Beleg scannen' : 'Beleg hochladen'}</h2>
		<button on:click={handleClose} aria-label="Schließen" class="rounded-full p-1 text-text-muted hover:text-text">
			✕
		</button>
	</div>
	<UploadFlow onSuccess={handleClose} {captureMode} />
</div>
