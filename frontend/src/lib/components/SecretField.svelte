<script lang="ts">
	// Wiederverwendbares Eingabefeld für Secrets ohne Klartext-Rückgabe vom Backend (API-Keys,
	// SMTP-Passwort — nur ein `isSet`-Flag). Siehe CLAUDE.md → "Design-Konvention: Secrets/
	// nicht einsehbare Felder": kein natives type="password"-Punkte-Placeholder, sondern ein
	// geblurrter Fake-Platzhalter mit "Ändern"-Auslöser. Gilt NICHT für aktive Passwort-
	// Eingabefelder (Login/Registrierung) — dort bleibt natives type="password" Standard.
	//
	// Label wird bewusst nicht von dieser Komponente gerendert (analog zu CustomSelect) — die
	// aufrufende Seite rendert es selbst und reicht die id über `labelledBy` durch.

	// Fixer, projektweit identischer Fake-String für den Blur-Platzhalter — bewusst kein
	// lesbares Wort, damit er auch bei nur leichter Unschärfe nicht als echter Wert lesbar
	// wird. aria-hidden, da der Hinweistext im Label die Screenreader-Kommunikation übernimmt.
	const FAKE_PLACEHOLDER = 'x7K$mQ9p&Zv2#wL8nR4tYc¤fG6';

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
