// Feste de-DE-Formatierung statt Browser-Locale — konsistent mit dem Rest der App
// (Settings-Zeitstempel nutzen ebenfalls hartes 'de-DE'). Echte i18n mit Sprachumschaltung
// ist laut Backlog bewusst auf nach v1.0.0 verschoben; die UI-Texte sind ohnehin komplett
// Deutsch, ein browser-abhängiges Datumsformat würde nur zu einer inkonsistenten Mischung
// führen (z.B. deutsche Labels neben englischem "7/22/2026").
export function formatDate(isoDate: string): string {
	return new Date(isoDate).toLocaleDateString('de-DE', { dateStyle: 'medium' });
}
