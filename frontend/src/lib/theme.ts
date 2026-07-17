// Theme-Präferenz-Verwaltung (Dark Mode, v0.28.0, siehe concepts/dark-mode.md).
// localStorage ist bewusst der einzige Speicherort (Q2 im Konzept) — Theme ist
// gerätegebunden, kein Server-Roundtrip, kein FOUC-Risiko durch Warten auf die API.
//
// WICHTIG: STORAGE_KEY muss mit dem inline-Anti-FOUC-Script in app.html
// synchron bleiben — app.html kann dieses Modul nicht importieren (kein Build-Step
// für inline-<script>-Inhalte), daher ist der Key dort als Literal dupliziert.
//
// Zustand liegt in Svelte-Stores (nicht in lokalem Komponenten-State), damit jede
// Stelle, die das Theme anzeigt oder ändert (Topbar-Toggle, ggf. weitere UI),
// automatisch synchron bleibt — unabhängig davon, wo die Änderung ausgelöst wurde.

import { derived, writable, type Readable } from 'svelte/store';

export type ThemePreference = 'system' | 'light' | 'dark';
export type EffectiveTheme = 'light' | 'dark';

const STORAGE_KEY = 'receiptly:theme';

function isThemePreference(value: unknown): value is ThemePreference {
	return value === 'system' || value === 'light' || value === 'dark';
}

function readStoredPreference(): ThemePreference {
	if (typeof localStorage === 'undefined') return 'system';
	const stored = localStorage.getItem(STORAGE_KEY);
	return isThemePreference(stored) ? stored : 'system';
}

function readSystemPrefersDark(): boolean {
	return typeof matchMedia !== 'undefined' && matchMedia('(prefers-color-scheme: dark)').matches;
}

export const themePreference = writable<ThemePreference>(readStoredPreference());
const systemPrefersDark = writable<boolean>(readSystemPrefersDark());

// Effektives Theme: bei 'system' das gerade aktive OS-Theme, sonst die explizite Wahl.
export const effectiveTheme: Readable<EffectiveTheme> = derived(
	[themePreference, systemPrefersDark],
	([$pref, $sysDark]) => ($pref === 'system' ? ($sysDark ? 'dark' : 'light') : $pref)
);

function applyTheme(effective: EffectiveTheme): void {
	document.documentElement.setAttribute('data-theme', effective);
}

export function setPreference(pref: ThemePreference): void {
	if (pref === 'system') localStorage.removeItem(STORAGE_KEY);
	else localStorage.setItem(STORAGE_KEY, pref);
	themePreference.set(pref);
}

let syncInitialized = false;

// Einmal aus +layout.svelte's onMount aufrufen: wendet jede effektive Theme-Änderung
// auf <html> an und hält offene Tabs im "System"-Modus mit OS-Änderungen synchron.
export function initThemeSync(): void {
	if (syncInitialized) return;
	syncInitialized = true;

	effectiveTheme.subscribe((value) => applyTheme(value));

	if (typeof matchMedia === 'undefined') return;
	matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
		systemPrefersDark.set(e.matches);
	});
}
