// Theme-Präferenz-Verwaltung (Dark Mode, v0.28.0, siehe concepts/dark-mode.md).
// localStorage ist bewusst der einzige Speicherort (Q2 im Konzept) — Theme ist
// gerätegebunden, kein Server-Roundtrip, kein FOUC-Risiko durch Warten auf die API.
//
// WICHTIG: STORAGE_KEY muss mit dem inline-Anti-FOUC-Script in app.html
// synchron bleiben — app.html kann dieses Modul nicht importieren (kein Build-Step
// für inline-<script>-Inhalte), daher ist der Key dort als Literal dupliziert.

export type ThemePreference = 'system' | 'light' | 'dark';
export type EffectiveTheme = 'light' | 'dark';

const STORAGE_KEY = 'receiptly:theme';

function isThemePreference(value: unknown): value is ThemePreference {
	return value === 'system' || value === 'light' || value === 'dark';
}

export function getStoredPreference(): ThemePreference {
	if (typeof localStorage === 'undefined') return 'system';
	const stored = localStorage.getItem(STORAGE_KEY);
	return isThemePreference(stored) ? stored : 'system';
}

export function resolveEffectiveTheme(pref?: ThemePreference): EffectiveTheme {
	const preference = pref ?? getStoredPreference();
	if (preference === 'system') {
		return typeof matchMedia !== 'undefined' && matchMedia('(prefers-color-scheme: dark)').matches
			? 'dark'
			: 'light';
	}
	return preference;
}

function applyTheme(effective: EffectiveTheme): void {
	document.documentElement.setAttribute('data-theme', effective);
}

// `system` wird beim Setzen sofort zu light/dark aufgelöst und geschrieben — es gibt
// zur Laufzeit nie einen Zustand ohne konkretes data-theme (vermeidet einen zweiten,
// @media-gestützten CSS-Codepfad; siehe Postmortem in app.css).
export function setPreference(pref: ThemePreference): void {
	if (pref === 'system') {
		localStorage.removeItem(STORAGE_KEY);
	} else {
		localStorage.setItem(STORAGE_KEY, pref);
	}
	applyTheme(resolveEffectiveTheme(pref));
}

// Einmal aus +layout.svelte's onMount aufrufen: wendet das aktuell gespeicherte
// Theme an und hält offene Tabs im "System"-Modus mit OS-Änderungen synchron.
export function initThemeSync(): void {
	applyTheme(resolveEffectiveTheme());

	if (typeof matchMedia === 'undefined') return;
	matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
		// Nur reagieren, wenn der Nutzer weiterhin "System" gewählt hat — eine explizite
		// Hell/Dunkel-Wahl darf nicht durch eine OS-Änderung überschrieben werden.
		if (getStoredPreference() === 'system') {
			applyTheme(resolveEffectiveTheme('system'));
		}
	});
}
