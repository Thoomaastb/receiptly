export interface Point {
	x: number;
	y: number;
}

export interface BlurDetectionResult {
	isBlurry: boolean;
	// Variance-of-Laplacian-Wert -- je niedriger, desto unschärfer. Kein normierter Bereich
	// (0..1), sondern ein roher Varianz-Wert, siehe BLUR_VARIANCE_THRESHOLD in
	// jscanify-provider.ts.
	score: number;
}

export interface EdgeDetectionProvider {
	readonly name: string;

	/** Liefert die 4 Eckpunkte einer erkannten Beleg-Kontur in Bild-Pixel-Koordinaten
	 *  (Reihenfolge: oben-links, oben-rechts, unten-rechts, unten-links), oder `null`, wenn
	 *  keine plausible Kontur gefunden wurde. */
	detectEdges(image: HTMLImageElement | ImageBitmap): Promise<Point[] | null>;

	/** Unschärfe-Heuristik (Variance-of-Laplacian) auf dem ganzen Bild. */
	detectBlur(image: HTMLImageElement | ImageBitmap): Promise<BlurDetectionResult>;

	/** Perspektivisch entzerrter Ausschnitt entlang der 4 Eckpunkte (gleiche Reihenfolge wie
	 *  bei {@link detectEdges}), in voller Auflösung des übergebenen Bildes. Liefert ein
	 *  JPEG-Blob. */
	extractDocument(image: HTMLImageElement | ImageBitmap, quad: Point[]): Promise<Blob>;
}
