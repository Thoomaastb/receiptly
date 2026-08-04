<script lang="ts">
	import { m } from '$lib/i18n';
	import { formatDate } from '$lib/formatDate';

	// Kompakte Einzel-Serien-Trendlinie (Sparkline) — kein eigenständiges Achsen-Chart.
	// `data` MUSS bereits aufsteigend sortiert und lückenlos pro Kalendertag sein (fehlende
	// Tage mit value=0 aufgefüllt) — siehe buildDailySeries() in AiUsageHistoryModal.svelte.
	// Dadurch entspricht gleichmäßiger Index-Abstand automatisch gleichmäßigem Zeit-Abstand,
	// ohne dass hier eine echte Datums-Skala nötig ist.
	export let data: { date: string; value: number }[] = [];
	export let label: string;
	export let formatValue: (value: number) => string;

	let containerEl: HTMLDivElement;
	let width = 0;
	const height = 56;
	const padX = 6;
	const padY = 8;

	let hoverIndex: number | null = null;
	let interacting = false;

	$: n = data.length;
	$: values = data.map((d) => d.value);
	$: minV = values.length ? Math.min(...values) : 0;
	$: maxV = values.length ? Math.max(...values) : 0;
	$: range = maxV - minV;
	$: stepX = n > 1 ? (width - padX * 2) / (n - 1) : 0;
	$: points = data.map((d, i) => {
		const x = n > 1 ? padX + i * stepX : width / 2;
		const y =
			range === 0 ? height / 2 : padY + (1 - (d.value - minV) / range) * (height - padY * 2);
		return { x, y, date: d.date, value: d.value };
	});
	$: linePath = points.length
		? points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(' ')
		: '';
	$: areaPath =
		points.length > 1
			? `${linePath} L${points[points.length - 1].x.toFixed(2)},${height - 1} L${points[0].x.toFixed(2)},${height - 1} Z`
			: '';
	$: activeIndex = hoverIndex ?? (points.length ? points.length - 1 : 0);
	$: activePoint = points.length ? points[activeIndex] : null;

	$: ariaLabel =
		n === 0
			? ''
			: n === 1
				? m.aiUsageHistory.trendSummarySingleDayAriaLabel
						.replace('{label}', label)
						.replace('{date}', formatDate(data[0].date))
						.replace('{value}', formatValue(data[0].value))
				: m.aiUsageHistory.trendSummaryAriaLabel
						.replace('{label}', label)
						.replace('{start}', formatDate(data[0].date))
						.replace('{end}', formatDate(data[n - 1].date))
						.replace('{current}', formatValue(data[n - 1].value))
						.replace('{min}', formatValue(minV))
						.replace('{max}', formatValue(maxV));

	function indexFromClientX(clientX: number): number {
		if (!containerEl || n < 2) return 0;
		const rect = containerEl.getBoundingClientRect();
		const relX = clientX - rect.left - padX;
		const ratio = stepX > 0 ? relX / stepX : 0;
		return Math.min(n - 1, Math.max(0, Math.round(ratio)));
	}

	function handlePointerMove(e: PointerEvent) {
		if (n < 2) return;
		hoverIndex = indexFromClientX(e.clientX);
		interacting = true;
	}

	function handlePointerLeave() {
		hoverIndex = null;
		interacting = false;
	}
</script>

<div class="flex flex-col gap-1.5">
	<div class="flex items-baseline justify-between gap-2">
		<h3 class="text-[10.5px] font-semibold uppercase tracking-wide text-hifi-text-faint">
			{label}
		</h3>
		<div class="flex items-baseline gap-1.5">
			{#if interacting && activePoint}
				<span class="text-[10.5px] text-hifi-text-faint">{formatDate(activePoint.date)}</span>
			{/if}
			<span class="text-xs font-semibold text-hifi-text">
				{activePoint ? formatValue(activePoint.value) : formatValue(0)}
			</span>
		</div>
	</div>

	<div
		bind:this={containerEl}
		bind:clientWidth={width}
		role="img"
		aria-label={ariaLabel}
		class="relative"
		on:pointermove={handlePointerMove}
		on:pointerleave={handlePointerLeave}
	>
		{#if width > 0}
			<svg {width} {height} viewBox="0 0 {width} {height}" class="block" aria-hidden="true">
				{#if points.length > 1}
					<path d={areaPath} class="fill-hifi-accent/15" />
					<path
						d={linePath}
						class="stroke-hifi-accent"
						fill="none"
						stroke-width="2"
						stroke-linecap="round"
						stroke-linejoin="round"
					/>
					{#if activePoint}
						<line
							x1={activePoint.x}
							x2={activePoint.x}
							y1={padY - 4}
							y2={height - padY + 4}
							class="stroke-hifi-border transition-opacity duration-100 motion-reduce:transition-none {interacting
								? 'opacity-100'
								: 'opacity-0'}"
							stroke-width="1"
						/>
					{/if}
				{/if}
				{#if activePoint}
					<circle
						cx={activePoint.x}
						cy={activePoint.y}
						r="4"
						class="fill-hifi-accent stroke-hifi-surface"
						stroke-width="2"
					/>
				{/if}
			</svg>
		{/if}
	</div>
</div>
