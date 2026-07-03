import { NativeOCRProvider } from './native-provider';
import { TesseractProvider } from './tesseract-provider';
import type { OCRProvider } from './types';

export type { OCRProvider, OCRResult } from './types';

const providers: OCRProvider[] = [new NativeOCRProvider(), new TesseractProvider()];

/**
 * Wählt den ersten verfügbaren Provider in Prioritätsreihenfolge
 * (siehe Architektur-Doku: NativeOCR > TesseractJS > ServerOCR).
 * ServerOCR ist bewusst nicht hier gelistet — der ist laut Doku nur für
 * Re-Processing/Admin-Funktionen gedacht, nicht für den normalen Upload-Flow.
 */
export async function getOCRProvider(): Promise<OCRProvider> {
	for (const provider of providers) {
		if (await provider.isAvailable()) {
			return provider;
		}
	}
	throw new Error('Kein OCR-Provider verfügbar.');
}
