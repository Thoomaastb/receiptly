// Kompakt-Modus für das Mosaik-Grid der Home-Übersicht ("Zuletzt hinzugefügt").
// Reine Client-Präferenz, gleiches Persistenz-Muster wie beim Dark Mode (siehe
// theme.ts): localStorage ist der einzige Speicherort, kein Server-Roundtrip.
//
// Anders als beim Theme braucht es hier kein Anti-FOUC-Script in app.html — ein
// kurzzeitig falscher Spaltenumbruch beim ersten Paint ist visuell unauffällig
// (kein Hell/Dunkel-Flackern), daher reicht der normale Store-Init.

import { writable } from 'svelte/store';

const STORAGE_KEY = 'receiptly:mosaic-compact';

function readStoredPreference(): boolean {
	if (typeof localStorage === 'undefined') return false;
	return localStorage.getItem(STORAGE_KEY) === '1';
}

export const mosaicCompact = writable<boolean>(readStoredPreference());

export function setMosaicCompact(value: boolean): void {
	if (typeof localStorage !== 'undefined') {
		if (value) localStorage.setItem(STORAGE_KEY, '1');
		else localStorage.removeItem(STORAGE_KEY);
	}
	mosaicCompact.set(value);
}
