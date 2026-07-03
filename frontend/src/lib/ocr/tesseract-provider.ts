import { createWorker } from 'tesseract.js';
import type { OCRProvider, OCRResult } from './types';

/**
 * Browser-Fallback per WASM (~10 MB, langsamer als native OCR).
 * Läuft komplett client-seitig — das Originalbild verlässt das Gerät nie,
 * nur der extrahierte Text geht später an die API.
 */
export class TesseractProvider implements OCRProvider {
	readonly name = 'tesseract';

	async isAvailable(): Promise<boolean> {
		// Immer verfügbar im Browser — dient als garantierter Fallback
		return true;
	}

	async recognize(file: File, onProgress?: (fraction: number) => void): Promise<OCRResult> {
		const worker = await createWorker('deu', 1, {
			logger: (m) => {
				if (m.status === 'recognizing text' && onProgress) {
					onProgress(m.progress);
				}
			}
		});

		try {
			const {
				data: { text, confidence }
			} = await worker.recognize(file);
			return { text, confidence: confidence / 100 };
		} finally {
			await worker.terminate();
		}
	}
}
