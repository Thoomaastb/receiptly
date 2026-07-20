<script lang="ts">
	import { mosaicCompact, setMosaicCompact } from '$lib/mosaicDensity';
</script>

<div class="flex max-w-2xl flex-col gap-6">
	<div class="rounded-[14px] border border-hifi-border bg-hifi-surface p-6">
		<h2 class="mb-1 text-[13.5px] font-bold text-hifi-text">Übersicht</h2>
		<p class="mb-4 text-sm text-hifi-text-muted">
			Layout-Einstellungen für die Home-Übersicht. Das Farbschema (Hell/Dunkel) stellst du über
			den Schnellzugriff in der Topbar ein.
		</p>

		<div class="flex items-center justify-between gap-4">
			<div class="min-w-0">
				<div class="text-sm font-semibold text-hifi-text">Kompaktes Mosaik</div>
				<div class="mt-0.5 text-[12.5px] leading-relaxed text-hifi-text-muted">
					Mehr, kleinere Karten im Raster „Zuletzt hinzugefügt“ auf der Übersicht.
				</div>
			</div>
			<button
				type="button"
				role="switch"
				aria-checked={$mosaicCompact}
				aria-label="Kompaktes Mosaik"
				on:click={() => setMosaicCompact(!$mosaicCompact)}
				class="relative h-6 w-11 flex-none rounded-full transition-colors"
				class:bg-hifi-accent={$mosaicCompact}
				class:bg-hifi-border={!$mosaicCompact}
			>
				<span
					class="absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform"
					class:translate-x-[22px]={$mosaicCompact}
					class:translate-x-0.5={!$mosaicCompact}
				></span>
			</button>
		</div>
	</div>
</div>
