import type { OCRProvider, OCRResult } from './types';

/**
 * Platzhalter für native OCR (iOS Vision Framework / Android ML Kit) über ein
 * künftiges Capacitor-Plugin. Laut Backlog erst Teil von "Mobile App" (späteres Paket).
 * isAvailable() liefert bewusst immer false, bis die native Anbindung existiert —
 * die Provider-Auswahl (siehe index.ts) fällt dann automatisch auf TesseractJS zurück.
 */
export class NativeOCRProvider implements OCRProvider {
	readonly name = 'native';

	async isAvailable(): Promise<boolean> {
		return false;
	}

	async recognize(): Promise<OCRResult> {
		throw new Error(
			'NativeOCRProvider ist noch nicht implementiert (folgt mit der Mobile-App-Integration).'
		);
	}
}
