<script lang="ts">
	import UploadFlow from './UploadFlow.svelte';

	export let onClose: () => void;
	export let captureMode: 'camera' | 'file' = 'file';

	function handleClose() {
		onClose();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') handleClose();
	}
</script>

<svelte:window on:keydown={handleKeydown} />

<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
<div
	class="fixed inset-0 z-40 bg-black opacity-50 backdrop-blur-sm"
	on:click={handleClose}
	role="presentation"
></div>

<div
	class="fixed left-1/2 top-1/2 z-50 max-h-[85vh] w-[92vw] max-w-md -translate-x-1/2 -translate-y-1/2 overflow-auto rounded-[20px] border border-hifi-border bg-hifi-surface p-5"
	role="dialog"
	aria-modal="true"
	aria-label="Beleg hochladen"
>
	<div class="mb-4 flex items-center justify-between">
		<h2 class="text-[13.5px] font-bold text-hifi-text">{captureMode === 'camera' ? 'Beleg scannen' : 'Beleg hochladen'}</h2>
		<button on:click={handleClose} aria-label="Schließen" class="rounded-full p-1 text-hifi-text-muted hover:text-hifi-text">
			✕
		</button>
	</div>
	<UploadFlow onSuccess={handleClose} {captureMode} />
</div>
