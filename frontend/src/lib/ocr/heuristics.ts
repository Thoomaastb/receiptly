export interface HeuristicResult {
	receiptDate: string | null; // ISO YYYY-MM-DD
	totalAmount: number | null;
	currency: string | null;
}

// Deckt d.m.yy / dd-mm-yyyy / dd/mm/yyyy usw. ab (Trenner . - /, 1-2-stellige Tag/Monat,
// 2- oder 4-stelliges Jahr) — bewusst KEIN internationales yyyy-mm-dd-Format, deutsche
// Kassenbons schreiben praktisch immer TT.MM.JJJJ.
const DATE_PATTERN = /\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})\b/g;

// Nur Zeilen mit einem dieser Summen-Keywords betrachten, nicht den ganzen Text — sonst
// würden Einzelpositionen/Pfandbeträge fälschlich als Gesamtbetrag erkannt.
const TOTAL_LINE_PATTERN = /SUMME|TOTAL|GESAMT(BETRAG)?|ZU ZAHLEN|BETRAG/i;

// Deutsches Zahlenformat (Tausenderpunkt, Komma als Dezimaltrenner), z.B. "1.234,56".
const AMOUNT_PATTERN = /\d{1,3}(?:\.\d{3})*,\d{2}/;

function extractDate(rawText: string): string | null {
	const today = new Date();
	today.setHours(23, 59, 59, 999); // heutiges Datum als Obergrenze, ganzer Tag erlaubt

	for (const match of rawText.matchAll(DATE_PATTERN)) {
		const day = Number(match[1]);
		const month = Number(match[2]);
		let year = Number(match[3]);

		if (day < 1 || day > 31 || month < 1 || month > 12) continue;
		if (year < 100) year += 2000; // 2-stelliges Jahr → 20YY

		const candidate = new Date(year, month - 1, day);
		// new Date() rollt ungültige Tage (z.B. 31.02.) auf den Folgemonat weiter statt
		// zu werfen — Rückvergleich der Komponenten fängt das ab.
		if (
			candidate.getFullYear() !== year ||
			candidate.getMonth() !== month - 1 ||
			candidate.getDate() !== day
		) {
			continue;
		}
		if (candidate.getTime() > today.getTime()) continue; // Belegdatum darf nicht in der Zukunft liegen

		const iso = `${year.toString().padStart(4, '0')}-${month.toString().padStart(2, '0')}-${day.toString().padStart(2, '0')}`;
		return iso;
	}
	return null;
}

function extractTotalAmount(rawText: string): number | null {
	for (const line of rawText.split('\n')) {
		if (!TOTAL_LINE_PATTERN.test(line)) continue;
		const match = line.match(AMOUNT_PATTERN);
		if (!match) continue;
		const normalized = match[0].replace(/\./g, '').replace(',', '.');
		const value = parseFloat(normalized);
		if (!Number.isNaN(value)) return value;
	}
	// Bewusst KEIN "größte Zahl im Text"-Fallback (zu hohe False-Positive-Gefahr, z.B.
	// Pfandbeträge/Einzelpositionen) — lieber null liefern als raten.
	return null;
}

function extractCurrency(rawText: string): string | null {
	if (rawText.includes('€')) return 'EUR';
	if (/\bEUR\b/i.test(rawText)) return 'EUR';
	// Backend-Default "EUR" greift ohnehin serverseitig, wenn hier nichts erkannt wird.
	return null;
}

export function extractHeuristics(rawText: string): HeuristicResult {
	return {
		receiptDate: extractDate(rawText),
		totalAmount: extractTotalAmount(rawText),
		currency: extractCurrency(rawText)
	};
}
