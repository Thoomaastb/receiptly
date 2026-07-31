// Automatische Kantenerkennung beim Beleg-Scannen. Reine Client-Präferenz,
// gleiches Persistenz-Muster wie beim Dark Mode (siehe theme.ts): localStorage
// ist der einzige Speicherort, kein Server-Roundtrip.
//
// Anders als bei mosaicDensity.ts ist der Default hier bewusst `true` — die
// Kantenerkennung soll standardmäßig aktiv sein, ausschalten ist die Ausnahme.

import { writable } from 'svelte/store';

const STORAGE_KEY = 'receiptly:auto-crop';

function readStoredPreference(): boolean {
	if (typeof localStorage === 'undefined') return true;
	const stored = localStorage.getItem(STORAGE_KEY);
	if (stored === null) return true;
	return stored === '1';
}

export const autoCropEnabled = writable<boolean>(readStoredPreference());

export function setAutoCropEnabled(value: boolean): void {
	if (typeof localStorage !== 'undefined') {
		localStorage.setItem(STORAGE_KEY, value ? '1' : '0');
	}
	autoCropEnabled.set(value);
}
