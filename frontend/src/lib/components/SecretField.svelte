<script lang="ts">
	// Wiederverwendbares Eingabefeld für Secrets, deren gespeicherter Wert nie im Klartext
	// vom Backend zurückkommt (API-Keys, SMTP-Passwort o.ä. — nur ein `isSet`-Flag). Siehe
	// CLAUDE.md → "Design-Konvention: Secrets/nicht einsehbare Felder": kein natives
	// type="password"-Punkte-Placeholder für den "bereits hinterlegt"-Zustand, sondern ein
	// geblurrter Fake-Platzhalter mit explizitem "Ändern"-Auslöser. Gilt NICHT für aktive
	// Passwort-Eingabefelder (Login/Registrierung/Passwort-Ändern) — dort bleibt natives
	// type="password" Standard.
	//
	// Label wird bewusst NICHT von dieser Komponente gerendert (analog zu CustomSelect) —
	// die aufrufende Seite rendert das <span id="…"> selbst und reicht die id über
	// `labelledBy` durch, damit Hinweistexte ("bereits hinterlegt — leer lassen, um ihn zu
	// behalten") pro Anwendungsfall frei formuliert werden können.

	// Fixer Fake-String für den geblurrten Platzhalter — bewusst ohne echten Aussagewert
	// und projektweit identisch, damit das Muster überall gleich aussieht. aria-hidden im
	// Markup, da er nichts Sinnvolles zum Vorlesen beiträgt (der Hinweistext im Label
	// übernimmt die Screenreader-Kommunikation "bereits hinterlegt").
	const FAKE_PLACEHOLDER = 'wirdnievollständigangezeigt';

	// Ob bereits ein Wert hinterlegt ist (entspricht has_api_key / password_set etc.).
	export let isSet: boolean;
	// Neuer Klartext-Wert — leer bleibt = bestehenden Wert serverseitig behalten.
	export let value = '';
	// Bindable: true = echtes Eingabefeld sichtbar. Default folgt isSet beim ersten Rendern;
	// die aufrufende Seite kann nach erfolgreichem Speichern gezielt zurücksetzen
	// (bind:editing, dazu value auf '' setzen).
	export let editing = !isSet;
	export let disabled = false;
	export let labelledBy: string | undefined = undefined;
	export let placeholder = '';
	export let autocomplete: 'new-password' | 'off' = 'new-password';
	export let changeButtonLabel = 'Ändern';
	export let changeButtonAriaLabel: string | undefined = undefined;
	export let cancelButtonLabel = 'Abbrechen';

	function startEditing() {
		editing = true;
	}

	function cancelEditing() {
		value = '';
		editing = false;
	}
</script>

{#if isSet && !editing}
	<div class="flex items-center gap-3">
		<span
			aria-hidden="true"
			class="pointer-events-none select-none whitespace-nowrap rounded border border-hifi-border bg-hifi-surface px-2 py-2 text-sm text-hifi-text-faint blur-sm"
		>
			{FAKE_PLACEHOLDER}
		</span>
		<button
			type="button"
			on:click={startEditing}
			{disabled}
			aria-label={changeButtonAriaLabel}
			class="flex-none rounded-[8px] border border-hifi-border px-2.5 py-1.5 text-[12.5px] font-medium text-hifi-text transition-colors hover:bg-hifi-accent-tint hover:text-hifi-accent-text disabled:opacity-50"
		>
			{changeButtonLabel}
		</button>
	</div>
{:else}
	<div class="flex items-center gap-2">
		<input
			type="password"
			bind:value
			{disabled}
			{placeholder}
			{autocomplete}
			aria-labelledby={labelledBy}
			class="w-full rounded border border-hifi-border bg-hifi-surface p-2 disabled:opacity-50"
		/>
		{#if isSet}
			<button
				type="button"
				on:click={cancelEditing}
				{disabled}
				class="flex-none whitespace-nowrap text-[12.5px] font-medium text-hifi-text-muted transition-colors hover:text-hifi-text disabled:opacity-50"
			>
				{cancelButtonLabel}
			</button>
		{/if}
	</div>
{/if}
