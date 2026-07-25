// Feste Palette der Farb-Slot-Keys für Tags (siehe backend/app/schemas/tag.py::TagColor).
// Anders als categories.ts::CATEGORIES sind hier NUR die Slot-Keys der Palette hinterlegt,
// nicht die Tag-Instanzen selbst — Tags sind dynamische, haushaltsspezifische Backend-Daten
// (geladen per GET /api/tags), keine feste Liste wie die Kategorien.
//
// Die echten CSS-Werte für --color-tag-01 … --color-tag-24 kommen erst in einem späteren
// Designer-Schritt (B4) in app.css. Bis dahin ist tagColorVar() bewusst "unstyled" (Browser
// löst eine fehlende Custom Property als transparent/initial auf) — keine eigenen Werte hier
// erfinden.
export const TAG_COLOR_KEYS = [
	'tag-01', 'tag-02', 'tag-03', 'tag-04', 'tag-05', 'tag-06', 'tag-07', 'tag-08',
	'tag-09', 'tag-10', 'tag-11', 'tag-12', 'tag-13', 'tag-14', 'tag-15', 'tag-16',
	'tag-17', 'tag-18', 'tag-19', 'tag-20', 'tag-21', 'tag-22', 'tag-23', 'tag-24'
] as const;

export function tagColorVar(key: string): string {
	return `var(--color-${key})`;
}

export interface Tag {
	id: string;
	name: string;
	color: string;
}
