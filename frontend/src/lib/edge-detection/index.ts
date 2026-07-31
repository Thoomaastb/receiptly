import type { EdgeDetectionProvider } from './types';

export type { BlurDetectionResult, EdgeDetectionProvider, Point } from './types';

let providerPromise: Promise<EdgeDetectionProvider> | null = null;

/**
 * Lazy-Loading-Grenze für jscanify + opencv.js (~5.9 MB inkl. WASM) -- der dynamische
 * Import hier ist die Code-Splitting-Grenze, die Vite/Rollup automatisch in einen eigenen
 * Chunk auslagert. `jscanify-provider` NIEMALS eager/statisch importieren, sonst landet
 * die gesamte CV-Bibliothek im initialen Bundle, obwohl sie nur bei aktivierter
 * Kantenerkennung gebraucht wird (siehe UploadFlow.svelte, maybeStartCropDetection()).
 */
export async function getEdgeDetectionProvider(): Promise<EdgeDetectionProvider> {
	if (!providerPromise) {
		providerPromise = import('./jscanify-provider')
			.then((mod) => new mod.JscanifyProvider())
			.catch((err) => {
				providerPromise = null; // Fehlgeschlagenen Ladeversuch nicht dauerhaft cachen
				throw err;
			});
	}
	return providerPromise;
}
