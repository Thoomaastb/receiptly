<script lang="ts">
	import '../app.css';
</script>

<div class="min-h-screen bg-surface text-text">
	<header class="border-b border-border">
		<nav class="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
			<!-- Links: Icon + Wortmarke -->
			<a href="/" class="flex items-center gap-2 text-lg font-semibold tracking-tight">
				<svg width="22" height="22" viewBox="0 0 24 24" fill="none" class="text-accent" aria-hidden="true">
					<path
						d="M6 2h12v19l-3-2-3 2-3-2-3 2V2z"
						stroke="currentColor"
						stroke-width="1.6"
						stroke-linejoin="round"
					/>
					<path d="M9 7h6M9 11h6M9 15h3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
				</svg>
				receiptly
			</a>

			<!-- Mitte: minimalistische Textbuttons -->
			<div class="hidden gap-6 text-sm text-text-muted sm:flex">
				<a href="/" class="rounded px-1 py-0.5 transition-colors hover:text-text">Start</a>
				<a href="/receipts" class="rounded px-1 py-0.5 transition-colors hover:text-text">Belege</a>
				<a href="/prices" class="rounded px-1 py-0.5 transition-colors hover:text-text">Preise</a>
				<a href="/buckets" class="rounded px-1 py-0.5 transition-colors hover:text-text">Buckets</a>
			</div>

			<!-- Rechts: nur Icons, echte SVGs statt Unicode-Symbolen -->
			<div class="flex gap-1 text-text-muted">
				<button
					aria-label="Suche"
					class="rounded-full p-2 transition-colors hover:bg-surface-raised hover:text-text"
				>
					<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
						<circle cx="11" cy="11" r="7" />
						<path d="M21 21l-4.3-4.3" stroke-linecap="round" />
					</svg>
				</button>
				<button
					aria-label="Benachrichtigungen"
					class="rounded-full p-2 transition-colors hover:bg-surface-raised hover:text-text"
				>
					<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
						<path d="M6 8a6 6 0 0112 0c0 5 2 6 2 6H4s2-1 2-6" stroke-linecap="round" stroke-linejoin="round" />
						<path d="M10 20a2 2 0 004 0" stroke-linecap="round" />
					</svg>
				</button>
				<a
					href="/settings"
					aria-label="Einstellungen"
					class="rounded-full p-2 transition-colors hover:bg-surface-raised hover:text-text"
				>
					<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
						<circle cx="12" cy="12" r="3" />
						<path
							d="M19.4 15a1.7 1.7 0 00.34 1.87l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.7 1.7 0 00-1.87-.34 1.7 1.7 0 00-1 1.55V21a2 2 0 01-4 0v-.09a1.7 1.7 0 00-1-1.55 1.7 1.7 0 00-1.87.34l-.06.06a2 2 0 11-2.83-2.83l.06-.06A1.7 1.7 0 004.6 15a1.7 1.7 0 00-1.55-1H3a2 2 0 010-4h.09A1.7 1.7 0 004.6 9a1.7 1.7 0 00-.34-1.87l-.06-.06a2 2 0 112.83-2.83l.06.06A1.7 1.7 0 009 4.6a1.7 1.7 0 001-1.55V3a2 2 0 014 0v.09a1.7 1.7 0 001 1.55 1.7 1.7 0 001.87-.34l.06-.06a2 2 0 112.83 2.83l-.06.06A1.7 1.7 0 0019.4 9a1.7 1.7 0 001.55 1H21a2 2 0 010 4h-.09a1.7 1.7 0 00-1.55 1z"
							stroke-linecap="round"
							stroke-linejoin="round"
						/>
					</svg>
				</a>
			</div>
		</nav>
	</header>

	<main class="mx-auto max-w-6xl px-6 py-8">
		<slot />
	</main>
</div>
