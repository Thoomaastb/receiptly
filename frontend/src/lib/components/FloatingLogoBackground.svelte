<script lang="ts">
	import Logo from './Logo.svelte';

	// Dekorativer, gedämpfter Hintergrund für Login/Setup-Wizard: das Kassenzettel-Logo in
	// Vielzahl, sehr niedrige Opacity ("gerade so sehbar"), langsam driftend. Reine
	// CSS-@keyframes-Animation (kein JS/Canvas), damit der globale prefers-reduced-motion-
	// Block (app.css) sie automatisch einfriert. Farbe = --color-text-faint (currentColor),
	// passt sich per Design-Token an Light/Dark an, KEINE Akzentfarbe.
	//
	// Bewusst unregelmäßig (kein Raster): variierende Position/Größe/Rotation/Timing +
	// negative animation-delays desynchronisieren die Instanzen, damit die Bewegung
	// organisch statt gleichgeschaltet wirkt.
	type Floater = {
		top: number;
		left: number;
		size: number;
		rot: number;
		dur: number;
		delay: number;
		op: number;
		variant: 'a' | 'b' | 'c';
	};

	const floaters: Floater[] = [
		{ top: 6, left: 8, size: 104, rot: -14, dur: 34, delay: -3, op: 0.07, variant: 'a' },
		{ top: 14, left: 74, size: 132, rot: 10, dur: 38, delay: -12, op: 0.06, variant: 'b' },
		{ top: 30, left: 40, size: 72, rot: -6, dur: 28, delay: -7, op: 0.08, variant: 'c' },
		{ top: 52, left: 18, size: 116, rot: 16, dur: 36, delay: -20, op: 0.06, variant: 'b' },
		{ top: 68, left: 62, size: 88, rot: -20, dur: 30, delay: -5, op: 0.07, variant: 'a' },
		{ top: 78, left: 30, size: 64, rot: 8, dur: 26, delay: -15, op: 0.08, variant: 'c' },
		{ top: 84, left: 84, size: 100, rot: -10, dur: 33, delay: -9, op: 0.06, variant: 'b' },
		{ top: 42, left: 90, size: 60, rot: 22, dur: 24, delay: -2, op: 0.07, variant: 'a' },
		{ top: 2, left: 46, size: 78, rot: 4, dur: 31, delay: -17, op: 0.07, variant: 'c' },
		{ top: 58, left: 50, size: 120, rot: -18, dur: 40, delay: -25, op: 0.05, variant: 'a' },
		{ top: 24, left: 22, size: 66, rot: 12, dur: 27, delay: -11, op: 0.08, variant: 'b' },
		{ top: 92, left: 12, size: 82, rot: -4, dur: 35, delay: -6, op: 0.06, variant: 'c' }
	];
</script>

<div class="floating-bg" aria-hidden="true">
	{#each floaters as f, i (i)}
		<span
			class="floater floater--{f.variant}"
			style="top:{f.top}%; left:{f.left}%; animation-duration:{f.dur}s; animation-delay:{f.delay}s;"
		>
			<span class="floater-inner" style="transform: rotate({f.rot}deg); --fl-op:{f.op};">
				<Logo size={f.size} />
			</span>
		</span>
	{/each}
</div>

<style>
	.floating-bg {
		position: absolute;
		inset: 0;
		overflow: hidden;
		pointer-events: none;
		z-index: 0;
		/* currentColor der Logos — gedämpfter, themenreaktiver Ton, keine Akzentfarbe */
		color: var(--color-text-faint);
	}

	.floater {
		position: absolute;
		left: 0; /* explizites Inset trotz top/left-Overrides via style — CLAUDE.md-Konvention
		            (absolute + transform braucht explizites Inset in der Achse) */
		top: 0;
		will-change: transform;
		animation-timing-function: ease-in-out;
		animation-iteration-count: infinite;
		animation-direction: alternate;
	}

	.floater-inner {
		display: block;
		opacity: var(--fl-op, 0.07);
	}

	/* Drei sanfte Drift-Pfade ("hin und her fliegen") — kleine Translation + minimale
	   Rotation, alternate loop pendelt zwischen den Endpunkten. */
	.floater--a {
		animation-name: drift-a;
	}
	.floater--b {
		animation-name: drift-b;
	}
	.floater--c {
		animation-name: drift-c;
	}

	@keyframes drift-a {
		from {
			transform: translate3d(0, 0, 0) rotate(0deg);
		}
		to {
			transform: translate3d(28px, -22px, 0) rotate(4deg);
		}
	}
	@keyframes drift-b {
		from {
			transform: translate3d(0, 0, 0) rotate(0deg);
		}
		to {
			transform: translate3d(-32px, 18px, 0) rotate(-5deg);
		}
	}
	@keyframes drift-c {
		from {
			transform: translate3d(0, 0, 0) rotate(0deg);
		}
		to {
			transform: translate3d(18px, 26px, 0) rotate(3deg);
		}
	}

	/* Dark Mode: Strichgrafik auf dunklem Grund liest schwächer — Opacity leicht anheben,
	   damit "gerade so sehbar" in beiden Modi gleich zart, aber nicht unsichtbar bleibt. */
	:global([data-theme='dark']) .floater-inner {
		opacity: calc(var(--fl-op, 0.07) * 1.4);
	}
</style>
