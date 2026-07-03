<script lang="ts">
	import '../app.css';
</script>

<div class="min-h-screen bg-surface text-text">
	<header class="border-b border-border">
		<nav class="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
			<!-- Links: Logo/Name -->
			<a href="/" class="text-lg font-semibold tracking-tight">receiptly</a>

			<!-- Mitte: minimalistische Textbuttons, keine Sidebar/verschachtelte Menüs -->
			<div class="hidden gap-6 text-sm text-text-muted sm:flex">
				<a href="/" class="hover:text-text">Start</a>
				<a href="/receipts" class="hover:text-text">Belege</a>
				<a href="/prices" class="hover:text-text">Preise</a>
				<a href="/buckets" class="hover:text-text">Buckets</a>
			</div>

			<!-- Rechts: nur Icons, keine Labels (Icons folgen mit Scan/Upload-Flow in alpha.2) -->
			<div class="flex gap-4 text-text-muted">
				<button aria-label="Suche" class="hover:text-text">⌕</button>
				<button aria-label="Benachrichtigungen" class="hover:text-text">◔</button>
				<button aria-label="Einstellungen" class="hover:text-text">⚙</button>
			</div>
		</nav>
	</header>

	<main class="mx-auto max-w-6xl px-6 py-8">
		<slot />
	</main>
</div>
