// Ungelesen-Zähler für Benachrichtigungen (v0.25.0, siehe concepts/benachrichtigungssystem.md
// und den zugehörigen Implementierungsplan). Strukturell wie lib/theme.ts (Svelte-Stores +
// Mutator-/Bootstrap-Funktionen), aber serverseitig statt localStorage-gestützt — der Zähler
// gehört dem Backend (Quelle: notifications-Tabelle), hier wird nur periodisch nachgefragt.

import { writable } from 'svelte/store';

export const unreadTotal = writable<number>(0);
export const unreadByCategory = writable<Record<string, number>>({});

interface UnreadCountResponse {
	total: number;
	by_category: Record<string, number>;
}

// Silent-fail GET, gleiches Muster wie AiUsageBadge.svelte's onMount-Fetch — ein rein
// informativer Zähler darf bei einem kurzen Backend-Ausfall einfach beim letzten bekannten
// Stand bleiben, kein Fehler-UI nötig.
export async function refreshUnreadCounts(): Promise<void> {
	try {
		const res = await fetch('/api/notifications/unread-count', { credentials: 'include' });
		if (!res.ok) return;
		const data: UnreadCountResponse = await res.json();
		unreadTotal.set(data.total);
		unreadByCategory.set(data.by_category);
	} catch {
		// s.o. — Badge bleibt beim letzten bekannten Stand, kein Fehler-UI für dieses Detail
	}
}

// Bulk-Read (v0.37.0) — Backend-Endpoint POST /notifications/read-all existiert bereits
// seit v0.34.0, nur ohne Frontend-Anbindung. Kein `category`-Filter nötig für den
// aktuellen Anwendungsfall (Glocken-Flyout "Alle als gelesen markieren" markiert wirklich
// alle, unabhängig vom aktiven Tab) — Parameter trotzdem optional gehalten, falls ein
// späterer Aufrufer nur eine Kategorie markieren will.
export async function markAllRead(category?: string): Promise<void> {
	try {
		const url = category
			? `/api/notifications/read-all?category=${encodeURIComponent(category)}`
			: '/api/notifications/read-all';
		await fetch(url, { method: 'POST', credentials: 'include' });
	} finally {
		// Zähler unabhängig vom Erfolg neu abfragen, statt ihn lokal auf 0 zu raten — bei
		// einem Fehlschlag zeigt refreshUnreadCounts() dann korrekt den unveränderten Stand.
		await refreshUnreadCounts();
	}
}

let pollHandle: ReturnType<typeof setInterval> | undefined;

// Bewusst setInterval statt des rekursiven setTimeout-mit-Attempt-Cap-Musters aus
// receipts/+page.svelte — jenes Muster ist dort explizit für einen *endlichen* Zustand
// kommentiert (Extraktion terminiert irgendwann). Badge-Polling muss unbegrenzt laufen,
// solange die App offen ist, daher kein Attempt-Cap hier.
export function startPolling(intervalMs = 30000): void {
	stopPolling();
	pollHandle = setInterval(refreshUnreadCounts, intervalMs);
}

export function stopPolling(): void {
	clearInterval(pollHandle);
	pollHandle = undefined;
}
