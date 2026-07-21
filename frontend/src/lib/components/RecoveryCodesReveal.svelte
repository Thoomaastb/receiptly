<script lang="ts">
	import { m } from '$lib/i18n';

	// Wird sowohl am Ende des Enrollment-Flows (TotpEnrollment) als auch nach dem
	// Neu-Generieren bestehender Codes gezeigt — beides Mal ist es der einzige Moment,
	// in dem die Codes im Klartext verfügbar sind.
	export let codes: string[];

	let copied = false;
	let copyTimeout: ReturnType<typeof setTimeout> | undefined;

	async function copyAll() {
		try {
			await navigator.clipboard.writeText(codes.join('\n'));
			copied = true;
			clearTimeout(copyTimeout);
			copyTimeout = setTimeout(() => (copied = false), 2000);
		} catch {
			// Clipboard-API evtl. ohne Berechtigung/HTTPS nicht verfügbar — Codes bleiben
			// zum manuellen Abschreiben sichtbar, kein Fehler-UI nötig für dieses Detail
		}
	}
</script>

<div>
	<div class="mb-3 rounded-[14px] border border-status-warning-border bg-status-warning-bg p-3 text-sm leading-relaxed">
		{m.totpSetup.recoveryWarning}
	</div>
	<ul class="mb-3 grid grid-cols-2 gap-x-4 gap-y-1.5 rounded-[10px] border border-hifi-border bg-hifi-bg p-3.5 font-mono text-sm text-hifi-text">
		{#each codes as code (code)}
			<li>{code}</li>
		{/each}
	</ul>
	<button
		type="button"
		on:click={copyAll}
		class="rounded-[10px] border border-hifi-border px-3.5 py-2 text-[13px] font-medium text-hifi-text transition-colors hover:bg-hifi-accent-tint hover:text-hifi-accent-text"
	>
		{copied ? m.totpSetup.recoveryCopyAllCopied : m.totpSetup.recoveryCopyAll}
	</button>
</div>
