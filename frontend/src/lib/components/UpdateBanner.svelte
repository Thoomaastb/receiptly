<script lang="ts">
	import { m } from '$lib/i18n';

	export let latestVersion: string;
	export let releaseUrl: string;
	export let isAdmin: boolean;

	// Dismiss-Zustand bewusst in localStorage statt Backend -- rein browserlokale UI-
	// Präferenz ohne Cross-Device-Bedarf. Schlüssel enthält die Version selbst, damit eine
	// neuere Version den Banner automatisch wieder zeigt, auch wenn eine ältere Version
	// bereits weggeklickt wurde.
	const DISMISS_KEY = 'receiptly-dismissed-update-version';

	function isDismissed(version: string): boolean {
		if (typeof localStorage === 'undefined') return false;
		return localStorage.getItem(DISMISS_KEY) === version;
	}

	let dismissed = isDismissed(latestVersion);

	function dismiss() {
		dismissed = true;
		if (typeof localStorage !== 'undefined') {
			localStorage.setItem(DISMISS_KEY, latestVersion);
		}
	}

	$: versionText = m.updateBanner.versionText.replace('{version}', latestVersion);
</script>

{#if !dismissed}
	<div class="mb-2 rounded-[14px] bg-hifi-accent-tint p-3">
		<div class="mb-1 flex items-center justify-between gap-2">
			<span class="flex items-center gap-1.5 text-xs font-bold text-hifi-accent-text">
				<span aria-hidden="true">🚀</span>
				{m.updateBanner.title}
			</span>
			<button
				type="button"
				on:click={dismiss}
				aria-label={m.updateBanner.dismissAriaLabel}
				class="-m-1.5 flex-none rounded-full p-1.5 text-hifi-text-faint transition-colors hover:text-hifi-text"
			>
				✕
			</button>
		</div>
		<p class="text-xs text-hifi-text-muted">{versionText}</p>
		{#if isAdmin}
			<a
				href={releaseUrl}
				target="_blank"
				rel="noopener"
				class="mt-1.5 inline-block text-xs font-semibold text-hifi-accent-text hover:underline"
			>
				{m.updateBanner.releaseNotesLink} →
			</a>
		{/if}
	</div>
{/if}
