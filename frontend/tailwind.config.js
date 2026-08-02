/** @type {import('tailwindcss').Config} */

// Tailwind generiert Opacity-Modifier-Utilities (`bg-x/50`) nur für Custom Colors, die
// als FUNKTION definiert sind (Tailwind-Doku "Customizing your color palette" → CSS-
// Variablen). Reine String-Referenzen wie `'x': 'var(--color-x)'` liefern für `/NN`
// KEINE CSS-Regel — Tailwind generiert die Utility-Klasse dann gar nicht erst (verifiziert
// per Produktions-Build am 2026-08-01: weder `.bg-hifi-accent-tint-strong\/96` noch
// `.border-hifi-border\/60`, `.bg-hifi-surface\/70`, `.bg-hifi-surface\/80`,
// `.bg-hifi-surface\/95`, `.fill-hifi-accent\/15` tauchten im Output auf, obwohl alle
// im Markup verwendet werden — nicht nur die ursprünglich gemeldete Pill-Menü-Stelle).
// Unsere Tokens sind fertige oklch()-Werte (keine reinen Kanal-Listen wie im Standard-
// Tailwind-Beispiel mit hsl()), deshalb lösen wir das über color-mix() statt über eine
// Aufspaltung der CSS-Variablen in Kanal-Listen — app.css bleibt dadurch unverändert,
// die Light/Dark-Overrides pro Token bleiben alleinige Quelle der Wahrheit (siehe
// dortiger Kommentar), und jedes Custom-Color-Token bekommt automatisch Opacity-Support,
// nicht nur die zwei ursprünglich gemeldeten. "transparent" ist in color-mix() als
// gleicher Farbton mit Alpha 0 definiert (CSS Color 4), das Ergebnis entspricht daher
// exakt einem direkten Alpha-Kanal auf demselben oklch()-Wert.
// Ohne expliziten `/NN`-Modifier ruft Tailwind diese Funktion für JEDE Farb-Utility trotzdem
// auf (backgroundOpacity/borderOpacity/textOpacity-Core-Plugins sind standardmäßig aktiv) und
// übergibt dann NICHT `undefined`, sondern den String `var(--tw-bg-opacity, 1)` (Tailwinds
// Legacy-Mechanismus für die separaten bg-opacity-*-Utilities) — `Number(...)` davon ergibt
// NaN. Da dieses Projekt nirgends bg-opacity-*/border-opacity-*/text-opacity-* verwendet
// (verifiziert per grep), wird dieser Fall bewusst wie "kein Modifier" behandelt: `Number.
// isFinite`-Check statt eines reinen `=== undefined`-Vergleichs, sonst rendert JEDE Basis-
// Farbklasse (auch ohne "/NN") plötzlich mit `NaN%` statt der vollen Deckkraft.
function withOpacity(variable) {
	return ({ opacityValue }) => {
		const alpha = Number(opacityValue);
		return Number.isFinite(alpha)
			? `color-mix(in oklch, var(${variable}) ${alpha * 100}%, transparent)`
			: `var(${variable})`;
	};
}

export default {
	content: ['./src/**/*.{html,js,svelte,ts}'],
	// Attribut-Override statt OS-Einstellung: [data-theme="dark"] gewinnt immer,
	// dark:-Utilities folgen nie unbeabsichtigt der OS-Einstellung (siehe theme.ts).
	darkMode: ['selector', '[data-theme="dark"]'],
	theme: {
		extend: {
			colors: {
				// Alle Farben zeigen auf CSS-Variablen aus app.css — nie hartkodiert,
				// damit Light/Dark und spätere Bucket-Farben zentral gepflegt werden.
				// Über withOpacity() gewrappt (siehe Kommentar oben), damit `/NN`-Modifier
				// projektweit für JEDES Token funktionieren, nicht nur punktuell.

				// Hifi-Palette (Shell + Home, Handoff Claude Design 2026-07-04)
				'hifi-bg': withOpacity('--color-bg'),
				'hifi-surface': withOpacity('--color-surface-hifi'),
				'hifi-border': withOpacity('--color-border-hifi'),
				'hifi-text': withOpacity('--color-text-hifi'),
				'hifi-text-muted': withOpacity('--color-text-muted-hifi'),
				'hifi-text-faint': withOpacity('--color-text-faint'),
				'hifi-accent': withOpacity('--color-accent-hifi'),
				'hifi-accent-tint': withOpacity('--color-accent-tint'),
				'hifi-accent-tint-strong': withOpacity('--color-accent-tint-strong'),
				'hifi-accent-text': withOpacity('--color-accent-text'),
				'cat-electronics': withOpacity('--color-cat-electronics'),
				'cat-groceries': withOpacity('--color-cat-groceries'),
				'cat-travel': withOpacity('--color-cat-travel'),
				'cat-furniture': withOpacity('--color-cat-furniture'),
				'cat-fashion': withOpacity('--color-cat-fashion'),
				'cat-dining': withOpacity('--color-cat-dining'),
				'cat-fuel': withOpacity('--color-cat-fuel'),
				success: withOpacity('--color-success'),
				'success-bg': withOpacity('--color-success-bg'),
				'success-border': withOpacity('--color-success-border'),
				'status-warning': withOpacity('--color-status-warning'),
				'status-warning-bg': withOpacity('--color-status-warning-bg'),
				'status-warning-border': withOpacity('--color-status-warning-border'),
				danger: withOpacity('--color-danger'),
				'danger-bg': withOpacity('--color-danger-bg'),
				'danger-border': withOpacity('--color-danger-border')
			},
			fontFamily: {
				ui: 'var(--font-ui)',
				mono: 'var(--font-mono)'
			},
			borderWidth: {
				DEFAULT: '0.5px'
			},
			boxShadow: {
				// Zeigt auf --shadow-popover (app.css, light/dark) — Elevation zentral gepflegt,
				// analog zum Farb-Token-Muster. Nutzung als `shadow-popover`.
				popover: 'var(--shadow-popover)'
			}
		}
	},
	plugins: []
};
