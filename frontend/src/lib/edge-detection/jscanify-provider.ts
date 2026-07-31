import Jscanify from 'jscanify/client';
import { distance } from './geometry';
import type { BlurDetectionResult, EdgeDetectionProvider, Point } from './types';

// Variance-of-Laplacian-Schwellwert für die Unschärfe-Erkennung (Standardansatz: Bild
// graustufen, Laplace-Filter, Varianz der Antwort -- niedrige Varianz = wenige scharfe
// Kanten = unscharf). Startwert aus gängigen Referenzimplementierungen übernommen, NOCH
// NICHT gegen echte Kassenbon-Fotos aus diesem Projekt kalibriert. Bei zu vielen False
// Positives/Negatives in der Praxis hier nachjustieren.
const BLUR_VARIANCE_THRESHOLD = 100;

// Self-hosted opencv.js-Assets (siehe frontend/static/opencv/, analog
// frontend/static/tesseract/ -- kein CDN, damit kein externer Request pro Scan-Vorgang
// nötig ist). opencv.js wird bewusst als klassisches <script>-Tag geladen statt als
// ES-Modul importiert: die Emscripten-Glue-Datei prüft intern `document.currentScript`
// (siehe deren Quelltext), was nur im klassischen Script-Kontext zuverlässig funktioniert,
// nicht zwingend in einem gebündelten async-Chunk. Das Laden hier ist zusätzlich bereits
// hinter der Lazy-Loading-Grenze aus index.ts (`await import('./jscanify-provider')`).
const OPENCV_SCRIPT_URL = '/opencv/opencv.js';
const OPENCV_WASM_URL = '/opencv/opencv.wasm';

let cvScriptPromise: Promise<void> | null = null;
let cvReadyPromise: Promise<CVModule> | null = null;

function loadCvScript(): Promise<void> {
	if (!cvScriptPromise) {
		cvScriptPromise = new Promise<void>((resolve, reject) => {
			const script = document.createElement('script');
			script.src = OPENCV_SCRIPT_URL;
			script.onload = () => resolve();
			script.onerror = () => reject(new Error('opencv.js konnte nicht geladen werden.'));
			document.head.appendChild(script);
		}).catch((err) => {
			cvScriptPromise = null; // Fehlgeschlagenen Ladeversuch nicht dauerhaft cachen
			throw err;
		});
	}
	return cvScriptPromise;
}

async function loadCv(): Promise<CVModule> {
	if (!cvReadyPromise) {
		cvReadyPromise = (async () => {
			await loadCvScript();
			const factory = window.cv;
			if (typeof factory !== 'function') {
				throw new Error('opencv.js-Factory nicht gefunden (window.cv).');
			}
			const wasmResponse = await fetch(OPENCV_WASM_URL);
			if (!wasmResponse.ok) {
				throw new Error(`opencv.wasm konnte nicht geladen werden (${wasmResponse.status}).`);
			}
			const wasmBinary = await wasmResponse.arrayBuffer();
			const readyCv = await factory({ wasmBinary });
			// jscanify (src/jscanify.js) greift intern auf die freie Variable `cv` zu, nicht auf
			// einen Import -- muss also global gesetzt sein, bevor jscanify-Methoden aufgerufen
			// werden (siehe jscanify/client-Ambient-Deklaration in opencv.d.ts).
			window.cv = readyCv;
			return readyCv;
		})().catch((err) => {
			cvReadyPromise = null; // Fehlgeschlagenen Ladeversuch nicht dauerhaft cachen
			throw err;
		});
	}
	return cvReadyPromise;
}

async function toCanvas(image: HTMLImageElement | ImageBitmap): Promise<HTMLCanvasElement> {
	const width = image instanceof HTMLImageElement ? image.naturalWidth : image.width;
	const height = image instanceof HTMLImageElement ? image.naturalHeight : image.height;
	const canvas = document.createElement('canvas');
	canvas.width = width;
	canvas.height = height;
	const ctx = canvas.getContext('2d');
	if (!ctx) throw new Error('2D-Canvas-Context nicht verfügbar.');
	ctx.drawImage(image, 0, 0, width, height);
	return canvas;
}

export class JscanifyProvider implements EdgeDetectionProvider {
	readonly name = 'jscanify';
	private readonly scanner = new Jscanify();

	async detectEdges(image: HTMLImageElement | ImageBitmap): Promise<Point[] | null> {
		const cv = await loadCv();
		const canvas = await toCanvas(image);
		const mat = cv.imread(canvas);
		try {
			const contour = this.scanner.findPaperContour(mat);
			if (!contour) return null;
			let corners;
			try {
				corners = this.scanner.getCornerPoints(contour);
			} finally {
				contour.delete();
			}
			const { topLeftCorner, topRightCorner, bottomRightCorner, bottomLeftCorner } = corners;
			if (!topLeftCorner || !topRightCorner || !bottomRightCorner || !bottomLeftCorner) return null;
			return [topLeftCorner, topRightCorner, bottomRightCorner, bottomLeftCorner];
		} finally {
			mat.delete();
		}
	}

	async detectBlur(image: HTMLImageElement | ImageBitmap): Promise<BlurDetectionResult> {
		const cv = await loadCv();
		const canvas = await toCanvas(image);
		const src = cv.imread(canvas);
		const gray = new cv.Mat();
		const laplacian = new cv.Mat();
		const mean = new cv.Mat();
		const stddev = new cv.Mat();
		try {
			cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY);
			cv.Laplacian(gray, laplacian, cv.CV_64F);
			cv.meanStdDev(laplacian, mean, stddev);
			const stdDev = stddev.data64F[0];
			const variance = stdDev * stdDev;
			return { isBlurry: variance < BLUR_VARIANCE_THRESHOLD, score: variance };
		} finally {
			src.delete();
			gray.delete();
			laplacian.delete();
			mean.delete();
			stddev.delete();
		}
	}

	async extractDocument(image: HTMLImageElement | ImageBitmap, quad: Point[]): Promise<Blob> {
		if (quad.length !== 4) throw new Error('extractDocument erwartet genau 4 Eckpunkte.');
		await loadCv();
		const canvas = await toCanvas(image);
		const [topLeftCorner, topRightCorner, bottomRightCorner, bottomLeftCorner] = quad;

		// Ausgabegröße aus den tatsächlichen Kantenlängen ableiten (Mittelwert aus
		// gegenüberliegenden Kanten), statt eines festen Seitenverhältnisses -- das
		// entzerrte Ergebnis behält damit ungefähr die Proportionen des fotografierten
		// Belegs statt ihn zu stauchen/strecken.
		const resultWidth = Math.max(1, Math.round((distance(topLeftCorner, topRightCorner) + distance(bottomLeftCorner, bottomRightCorner)) / 2));
		const resultHeight = Math.max(1, Math.round((distance(topLeftCorner, bottomLeftCorner) + distance(topRightCorner, bottomRightCorner)) / 2));

		const resultCanvas = this.scanner.extractPaper(canvas, resultWidth, resultHeight, {
			topLeftCorner,
			topRightCorner,
			bottomLeftCorner,
			bottomRightCorner
		});
		if (!resultCanvas) throw new Error('Zuschnitt fehlgeschlagen -- keine Kontur extrahierbar.');

		return new Promise<Blob>((resolve, reject) => {
			resultCanvas.toBlob(
				(blob) => (blob ? resolve(blob) : reject(new Error('Zuschnitt konnte nicht als Bild exportiert werden.'))),
				'image/jpeg',
				0.92
			);
		});
	}
}
