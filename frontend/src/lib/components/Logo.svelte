<script lang="ts">
	// Angedeuteter Kassenzettel — App-Logo. Zuvor als identischer Inline-SVG-Pfad an 6
	// Stellen dupliziert (login/forgot/reset/+layout 3x/ReceiptRow), hier als eine Quelle
	// konsolidiert. stroke default 'currentColor' → Farbe steuert der Aufrufer per
	// text-color-Klasse; für die weißen Instanzen auf Accent-Hintergrund stroke="white".
	export let size: number = 19;
	export let stroke: string = 'currentColor';
	export let strokeWidth: number = 1.8;
	let className: string = '';
	export { className as class };
</script>

<svg
	width={size}
	height={size}
	viewBox="0 0 24 24"
	fill="none"
	{stroke}
	stroke-width={strokeWidth}
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"
	class={className}
>
	<path d="M6 3h9l3 3v15H6z" />
	<path d="M9 9h6M9 13h6M9 17h3" />
</svg>
