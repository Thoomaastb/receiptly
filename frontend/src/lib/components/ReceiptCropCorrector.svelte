<script lang="ts">
	import { createEventDispatcher, onDestroy, onMount } from 'svelte';
	import { m } from '$lib/i18n';
	import { getEdgeDetectionProvider } from '$lib/edge-detection';
	import { clampPoint, clientToImagePoint, imageCorners } from '$lib/edge-detection/geometry';
	import type { Point } from '$lib/edge-detection/types';

	// Korrektur-Bildschirm für den automatischen Beleg-Zuschnitt: SVG-Overlay (nicht Canvas)
	// über dem Foto, vier per Pointer/Tastatur verschiebbare Eckpunkte. Positionierung über
	// `cx`/`cy`-Attribute im viewBox-Koordinatenraum -- bewusst KEIN `transform: translate()`
	// auf einem `position: absolute`-Element, siehe CLAUDE.md "Absolute+Transform-Falle".
	//
	// EXIF-Orientierung: sowohl die Vorschau als auch die spätere Verarbeitung in voller
	// Auflösung laufen über denselben `createImageBitmap(file, { imageOrientation:
	// 'from-image' })`-Aufruf -- ohne das würden bestätigte Eckpunkte bei Fotos mit
	// EXIF-Rotation nicht zur tatsächlichen Pixel-Orientierung des Ergebnisses passen.

	export let image: File;
	export let initialQuad: Point[];

	const dispatch = createEventDispatcher<{ confirm: File; cancel: void }>();

	let bitmap: ImageBitmap | null = null;
	let previewUrl = '';
	let imgWidth = 0;
	let imgHeight = 0;
	let quad: Point[] = initialQuad.map((p) => ({ ...p }));
	let containerEl: HTMLDivElement;
	let draggingIndex: number | null = null;
	let processing = false;
	let loadError = '';

	onMount(async () => {
		try {
			bitmap = await createImageBitmap(image, { imageOrientation: 'from-image' });
			imgWidth = bitmap.width;
			imgHeight = bitmap.height;
			if (quad.length !== 4) quad = imageCorners(imgWidth, imgHeight);

			const canvas = document.createElement('canvas');
			canvas.width = imgWidth;
			canvas.height = imgHeight;
			const ctx = canvas.getContext('2d');
			if (!ctx) throw new Error('2D-Canvas-Context nicht verfügbar.');
			ctx.drawImage(bitmap, 0, 0);

			const blob: Blob | null = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.92));
			if (!blob) throw new Error('Vorschau konnte nicht erzeugt werden.');
			previewUrl = URL.createObjectURL(blob);
		} catch (err) {
			loadError = err instanceof Error ? err.message : m.cropCorrector.errorGeneric;
		}
	});

	onDestroy(() => {
		if (previewUrl) URL.revokeObjectURL(previewUrl);
		bitmap?.close();
	});

	function resetQuad() {
		quad = imageCorners(imgWidth, imgHeight);
	}

	// Element, auf dem `setPointerCapture` aufgerufen wurde -- muss für `releasePointerCapture`
	// separat gemerkt werden, weil handlePointerUp global auf `window` hängt (siehe unten) und
	// dort `event.currentTarget` bereits `window` wäre, nicht mehr der ursprüngliche <circle>.
	let capturedHandleEl: Element | null = null;

	function handlePointerDown(index: number, event: PointerEvent) {
		draggingIndex = index;
		capturedHandleEl = event.currentTarget as Element;
		capturedHandleEl.setPointerCapture(event.pointerId);
	}

	function handlePointerMove(event: PointerEvent) {
		if (draggingIndex === null || !containerEl) return;
		const rect = containerEl.getBoundingClientRect();
		const point = clientToImagePoint(event.clientX, event.clientY, rect, imgWidth, imgHeight);
		quad[draggingIndex] = clampPoint(point, imgWidth, imgHeight);
		quad = quad;
	}

	function handlePointerUp(event: PointerEvent) {
		if (draggingIndex === null) return;
		capturedHandleEl?.releasePointerCapture(event.pointerId);
		capturedHandleEl = null;
		draggingIndex = null;
	}

	function handleHandleKeydown(index: number, event: KeyboardEvent) {
		const step = event.shiftKey ? 10 : 1;
		let { x, y } = quad[index];
		switch (event.key) {
			case 'ArrowLeft':
				x -= step;
				break;
			case 'ArrowRight':
				x += step;
				break;
			case 'ArrowUp':
				y -= step;
				break;
			case 'ArrowDown':
				y += step;
				break;
			default:
				return;
		}
		event.preventDefault();
		quad[index] = clampPoint({ x, y }, imgWidth, imgHeight);
		quad = quad;
	}

	async function handleConfirm() {
		if (!bitmap) return;
		processing = true;
		loadError = '';
		try {
			const provider = await getEdgeDetectionProvider();
			const blob = await provider.extractDocument(bitmap, quad);
			const croppedName = image.name.replace(/(\.[^.]+)?$/, (ext) => `-cropped${ext || '.jpg'}`);
			const file = new File([blob], croppedName, { type: 'image/jpeg' });
			dispatch('confirm', file);
		} catch (err) {
			loadError = err instanceof Error ? err.message : m.cropCorrector.errorGeneric;
		} finally {
			processing = false;
		}
	}

	function handleSkip() {
		dispatch('cancel');
	}
</script>

<!-- Unconditional attachment auf window: handlePointerMove/-Up prüfen `draggingIndex`
     selbst und kehren sonst sofort zurück -- so bleibt die Handle-Verschiebung auch dann
     robust, wenn der Pointer während des Ziehens den <circle> verlässt (setPointerCapture
     routet die Events zwar zum Ursprungselement zurück, window fängt sie hier zusätzlich
     als zweite, einfache Absicherung ab). -->
<svelte:window on:pointermove={handlePointerMove} on:pointerup={handlePointerUp} on:pointercancel={handlePointerUp} />

{#if loadError}
	<p class="mb-4 text-sm text-danger">{loadError}</p>
	<div class="flex flex-wrap gap-2">
		<button
			type="button"
			on:click={handleSkip}
			class="rounded-[10px] border border-hifi-border px-4 py-2 text-sm font-medium text-hifi-text"
		>
			{m.cropCorrector.skipButton}
		</button>
	</div>
{:else if !previewUrl}
	<p class="text-sm text-hifi-text-muted">{m.cropCorrector.loading}</p>
{:else}
	<div
		bind:this={containerEl}
		class="relative mx-auto w-full touch-none select-none"
		style="aspect-ratio: {imgWidth} / {imgHeight}; max-width: {imgWidth}px;"
	>
		<img
			src={previewUrl}
			alt={m.cropCorrector.previewAlt}
			draggable="false"
			class="pointer-events-none absolute inset-0 h-full w-full rounded-[10px] object-contain"
		/>
		<svg viewBox="0 0 {imgWidth} {imgHeight}" class="absolute inset-0 h-full w-full" role="presentation">
			<polygon
				points={quad.map((p) => `${p.x},${p.y}`).join(' ')}
				class="fill-hifi-accent/15 stroke-hifi-accent"
				stroke-width={Math.max(imgWidth, imgHeight) * 0.004}
			/>
			{#each quad as point, i}
				<circle
					cx={point.x}
					cy={point.y}
					r={Math.max(imgWidth, imgHeight) * 0.016}
					tabindex="0"
					role="slider"
					aria-label={m.cropCorrector.handleAriaLabel.replace('{n}', String(i + 1))}
					aria-valuemin={0}
					aria-valuemax={imgWidth}
					aria-valuenow={Math.round(point.x)}
					aria-valuetext="x {Math.round(point.x)}, y {Math.round(point.y)}"
					class="cursor-grab fill-hifi-surface stroke-hifi-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-hifi-accent"
					stroke-width={Math.max(imgWidth, imgHeight) * 0.006}
					on:pointerdown={(e) => handlePointerDown(i, e)}
					on:keydown={(e) => handleHandleKeydown(i, e)}
				/>
			{/each}
		</svg>
	</div>

	<div class="mt-4 flex flex-wrap gap-2">
		<button
			type="button"
			on:click={handleConfirm}
			disabled={processing}
			class="rounded-[10px] bg-hifi-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
		>
			{processing ? m.cropCorrector.confirmButtonLoading : m.cropCorrector.confirmButton}
		</button>
		<button
			type="button"
			on:click={resetQuad}
			disabled={processing}
			class="rounded-[10px] border border-hifi-border px-4 py-2 text-sm font-medium text-hifi-text disabled:opacity-50"
		>
			{m.cropCorrector.resetButton}
		</button>
		<button
			type="button"
			on:click={handleSkip}
			disabled={processing}
			class="rounded-[10px] px-4 py-2 text-sm font-medium text-hifi-text-muted transition-colors hover:text-hifi-text disabled:opacity-50"
		>
			{m.cropCorrector.skipButton}
		</button>
	</div>
{/if}
