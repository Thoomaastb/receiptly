// Feste Kategorien statt Freitext — Farben sind im Hifi-Design-System bereits als
// --color-cat-* Tokens angelegt (siehe app.css), nur die Zuweisung fehlte bisher.

// Manche Kategorien brauchen Zusatzfelder, die für andere Kategorien irrelevant sind
// (z.B. Kilometerstand nur bei "Tanken"). Werte landen in Receipt.custom_fields (JSONB) —
// bewusst generisch statt eigener Spalten pro Feld, siehe backend/app/models/receipt.py.
export interface CategoryFieldDef {
	key: string;
	label: string;
	type: 'number' | 'text';
	unit?: string;
}

export interface CategoryDef {
	value: string;
	label: string;
	colorVar: string;
	fields?: CategoryFieldDef[];
}

export const CATEGORIES: CategoryDef[] = [
	{ value: 'electronics', label: 'Elektronik', colorVar: 'var(--color-cat-electronics)' },
	{ value: 'groceries', label: 'Lebensmittel', colorVar: 'var(--color-cat-groceries)' },
	{ value: 'travel', label: 'Reisen', colorVar: 'var(--color-cat-travel)' },
	{ value: 'furniture', label: 'Möbel', colorVar: 'var(--color-cat-furniture)' },
	{ value: 'fashion', label: 'Mode', colorVar: 'var(--color-cat-fashion)' },
	{ value: 'dining', label: 'Restaurant', colorVar: 'var(--color-cat-dining)' },
	{
		value: 'fuel',
		label: 'Tanken',
		colorVar: 'var(--color-cat-fuel)',
		fields: [{ key: 'odometer_km', label: 'Kilometerstand', type: 'number', unit: 'km' }]
	}
];

export function categoryLabel(value: string | null): string | null {
	return value ? (CATEGORIES.find((c) => c.value === value)?.label ?? value) : null;
}

export function categoryColor(value: string | null): string {
	return CATEGORIES.find((c) => c.value === value)?.colorVar ?? 'var(--color-text-muted-hifi)';
}

export function categoryFields(value: string | null): CategoryFieldDef[] {
	return value ? (CATEGORIES.find((c) => c.value === value)?.fields ?? []) : [];
}
