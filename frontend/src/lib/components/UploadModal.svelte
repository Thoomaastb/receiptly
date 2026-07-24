<script lang="ts">
	import { fade, fly } from 'svelte/transition';
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
	transition:fade={{ duration: 150 }}
	class="fixed inset-0 z-40 bg-black opacity-50 backdrop-blur-sm"
	on:click={handleClose}
	role="presentation"
></div>

<!-- Flexbox-Zentrierung statt left/top-50%+translate (Muster projektweit einheitlich für
     alle 4 Modals): auf Mobile randloses Bottom-Sheet, ab lg unverändert die bisherige
     zentrierte Karte -- kein Transform mehr im Spiel, damit auch kein Berührungspunkt mit
     der Absolute/Transform-Inset-Regel aus CLAUDE.md. -->
<div class="fixed inset-0 z-50 flex items-end justify-center lg:items-center">
	<div
		transition:fly={{ y: 20, duration: 180 }}
		class="max-h-[92dvh] w-full overflow-auto rounded-t-[20px] border-t border-hifi-border bg-hifi-surface p-5 pb-[calc(1.25rem+env(safe-area-inset-bottom))] lg:max-h-[85vh] lg:w-[92vw] lg:max-w-md lg:rounded-[20px] lg:border lg:pb-5"
		role="dialog"
		aria-modal="true"
		aria-label="Beleg hochladen"
	>
		<div class="mb-4 flex items-center justify-between">
			<h2 class="text-[13.5px] font-bold text-hifi-text">{captureMode === 'camera' ? 'Beleg scannen' : 'Beleg hochladen'}</h2>
			<button on:click={handleClose} aria-label="Schließen" class="flex h-11 w-11 items-center justify-center rounded-full text-hifi-text-muted hover:text-hifi-text">
				✕
			</button>
		</div>
		<UploadFlow onSuccess={handleClose} {captureMode} />
	</div>
</div>
