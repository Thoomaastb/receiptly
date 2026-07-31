// Minimale Ambient-Typen für die self-gehostete opencv.js-Laufzeit (siehe
// static/opencv/opencv.js + jscanify-provider.ts) und für jscanify selbst -- keine der
// beiden Bibliotheken bringt eigene TS-Typen mit. Bewusst nur die tatsächlich genutzte
// Teilmenge der opencv.js-API, kein vollständiges Typing (das wäre eine eigenständige,
// tausende Zeilen große Typdefinition für eine komplette C++-API-Oberfläche).
//
// Datei ohne eigene import/export-Statements auf oberster Ebene -- dadurch ein "globales"
// Ambient-Script, alle Interfaces sind projektweit ohne Import nutzbar (wie DOM-lib-Typen).

interface CVMat {
	delete(): void;
	readonly data32S: Int32Array;
	readonly data64F: Float64Array;
	readonly rows: number;
	readonly cols: number;
}

interface CVMatVector {
	size(): number;
	get(index: number): CVMat;
	delete(): void;
}

// Marker-Typen ohne genutzte Member -- Size/Scalar werden nur konstruiert und
// weitergereicht, nie ausgelesen.
type CVSize = Record<string, never>;
type CVScalar = Record<string, never>;

interface CVRotatedRect {
	center: { x: number; y: number };
}

interface CVModule {
	Mat: new (...args: unknown[]) => CVMat;
	MatVector: new () => CVMatVector;
	Size: new (width: number, height: number) => CVSize;
	Scalar: new (...args: number[]) => CVScalar;

	imread(source: HTMLCanvasElement | HTMLImageElement): CVMat;
	imshow(canvas: HTMLCanvasElement, mat: CVMat): void;
	Canny(src: CVMat, dst: CVMat, threshold1: number, threshold2: number): void;
	GaussianBlur(src: CVMat, dst: CVMat, ksize: CVSize, sigmaX: number, sigmaY: number, borderType: number): void;
	threshold(src: CVMat, dst: CVMat, thresh: number, maxval: number, type: number): number;
	findContours(image: CVMat, contours: CVMatVector, hierarchy: CVMat, mode: number, method: number): void;
	contourArea(contour: CVMat): number;
	minAreaRect(contour: CVMat): CVRotatedRect;
	cvtColor(src: CVMat, dst: CVMat, code: number): void;
	Laplacian(src: CVMat, dst: CVMat, ddepth: number): void;
	meanStdDev(src: CVMat, mean: CVMat, stddev: CVMat): void;
	matFromArray(rows: number, cols: number, type: number, array: number[]): CVMat;
	getPerspectiveTransform(src: CVMat, dst: CVMat): CVMat;
	warpPerspective(
		src: CVMat,
		dst: CVMat,
		M: CVMat,
		dsize: CVSize,
		flags: number,
		borderMode: number,
		borderValue: CVScalar
	): void;

	readonly BORDER_DEFAULT: number;
	readonly THRESH_OTSU: number;
	readonly RETR_CCOMP: number;
	readonly CHAIN_APPROX_SIMPLE: number;
	readonly COLOR_RGBA2GRAY: number;
	readonly CV_64F: number;
	readonly CV_32FC2: number;
	readonly CV_8UC4: number;
	readonly INTER_LINEAR: number;
	readonly BORDER_CONSTANT: number;
}

// Emscripten-MODULARIZE-Factory aus opencv.js (self-hosted als klassisches <script>-Tag
// geladen, siehe jscanify-provider.ts::loadCvScript). Direkt nach dem Laden des Scripts ist
// `window.cv` noch diese Factory, nicht das fertige Modul -- erst der Aufruf mit dem per
// fetch() nachgeladenen wasmBinary liefert das initialisierte CVModule.
type CVFactory = (options?: { wasmBinary?: ArrayBuffer }) => Promise<CVModule>;

interface Window {
	cv?: CVFactory | CVModule;
}

// jscanify liefert keine eigenen Typen mit. Nur der Browser-Client-Export
// (`jscanify/client`, siehe dessen package.json `exports`-Feld) wird hier genutzt -- der
// Node-Export (Default-Import `jscanify`) hängt an `canvas`/`jsdom` und wird bewusst nicht
// typisiert, da im Browser-Bundle nie referenziert.
declare module 'jscanify/client' {
	export interface JscanifyCornerPoints {
		topLeftCorner?: { x: number; y: number };
		topRightCorner?: { x: number; y: number };
		bottomLeftCorner?: { x: number; y: number };
		bottomRightCorner?: { x: number; y: number };
	}

	export default class Jscanify {
		findPaperContour(img: CVMat): CVMat | null;
		getCornerPoints(contour: CVMat): JscanifyCornerPoints;
		extractPaper(
			image: HTMLCanvasElement | HTMLImageElement,
			resultWidth: number,
			resultHeight: number,
			cornerPoints?: {
				topLeftCorner: { x: number; y: number };
				topRightCorner: { x: number; y: number };
				bottomLeftCorner: { x: number; y: number };
				bottomRightCorner: { x: number; y: number };
			}
		): HTMLCanvasElement | null;
	}
}
