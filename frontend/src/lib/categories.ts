// Feste Kategorien statt Freitext — Farben sind im Hifi-Design-System bereits als
// --color-cat-* Tokens angelegt (siehe app.css), nur die Zuweisung fehlte bisher.
export const CATEGORIES: { value: string; label: string; colorVar: string }[] = [
	{ value: 'electronics', label: 'Elektronik', colorVar: 'var(--color-cat-electronics)' },
	{ value: 'groceries', label: 'Lebensmittel', colorVar: 'var(--color-cat-groceries)' },
	{ value: 'travel', label: 'Reisen', colorVar: 'var(--color-cat-travel)' },
	{ value: 'furniture', label: 'Möbel', colorVar: 'var(--color-cat-furniture)' },
	{ value: 'fashion', label: 'Mode', colorVar: 'var(--color-cat-fashion)' },
	{ value: 'dining', label: 'Restaurant', colorVar: 'var(--color-cat-dining)' }
];

export function categoryLabel(value: string | null): string | null {
	return value ? (CATEGORIES.find((c) => c.value === value)?.label ?? value) : null;
}

export function categoryColor(value: string | null): string {
	return CATEGORIES.find((c) => c.value === value)?.colorVar ?? 'var(--color-text-muted)';
}
