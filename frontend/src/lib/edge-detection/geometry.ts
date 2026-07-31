// Reine Geometrie-Hilfsfunktionen ohne DOM-/OpenCV-Abhängigkeit -- bewusst von
// jscanify-provider.ts getrennt, damit die Plausibilitätsprüfung und Koordinaten-Umrechnung
// unabhängig von der (schweren, lazy geladenen) CV-Bibliothek testbar/lesbar bleiben.

import type { Point } from './types';

// Toleranz in Bild-Pixeln, um wie weit ein erkannter Eckpunkt über den Bildrand
// hinausragen darf, bevor die Kontur als unplausibel verworfen wird -- die
// Konturerkennung liefert bei randnah fotografierten Belegen gelegentlich Punkte 1-2px
// außerhalb der eigentlichen Bildfläche.
const BOUNDS_TOLERANCE_PX = 4;

// Mindestanteil der Bildfläche, den die erkannte Kontur einnehmen muss, um als plausibler
// Beleg-Zuschnitt zu gelten -- verhindert, dass z.B. ein kleiner erkannter Fleck oder
// Schatten als "Kontur" durchgeht. Startwert, ggf. anhand echter Belegfotos nachjustieren.
const MIN_AREA_RATIO = 0.15;

/**
 * Prüft, ob ein erkanntes Viereck als plausibler Beleg-Zuschnitt gelten kann: 4 Punkte,
 * innerhalb der Bildgrenzen (mit Toleranz), ausreichend Fläche, und konvex (kein
 * Selbstüberschneiden der Kanten).
 */
export function isPlausibleQuad(quad: Point[], width: number, height: number): boolean {
	if (quad.length !== 4) return false;
	if (width <= 0 || height <= 0) return false;

	for (const p of quad) {
		if (p.x < -BOUNDS_TOLERANCE_PX || p.x > width + BOUNDS_TOLERANCE_PX) return false;
		if (p.y < -BOUNDS_TOLERANCE_PX || p.y > height + BOUNDS_TOLERANCE_PX) return false;
	}

	const area = Math.abs(shoelaceArea(quad));
	if (area < MIN_AREA_RATIO * width * height) return false;

	return isConvex(quad);
}

function shoelaceArea(points: Point[]): number {
	let sum = 0;
	for (let i = 0; i < points.length; i++) {
		const a = points[i];
		const b = points[(i + 1) % points.length];
		sum += a.x * b.y - b.x * a.y;
	}
	return sum / 2;
}

// Grobe Konvexitätsprüfung über die Vorzeichen der Kreuzprodukte aufeinanderfolgender
// Kanten -- wechselt das Vorzeichen, überschneiden sich Kanten oder das Viereck ist
// einwärts eingedellt.
function isConvex(points: Point[]): boolean {
	let sign = 0;
	for (let i = 0; i < points.length; i++) {
		const a = points[i];
		const b = points[(i + 1) % points.length];
		const c = points[(i + 2) % points.length];
		const cross = (b.x - a.x) * (c.y - b.y) - (b.y - a.y) * (c.x - b.x);
		if (cross === 0) continue; // kollinear -- kein Vorzeichenwechsel, aber auch kein Verstoß
		if (sign === 0) sign = Math.sign(cross);
		else if (Math.sign(cross) !== sign) return false;
	}
	return true;
}

/** Die 4 Bildecken als Fallback-Viereck, im Uhrzeigersinn (oben-links, oben-rechts,
 *  unten-rechts, unten-links) -- gleiche Reihenfolge wie EdgeDetectionProvider.detectEdges. */
export function imageCorners(width: number, height: number): Point[] {
	return [
		{ x: 0, y: 0 },
		{ x: width, y: 0 },
		{ x: width, y: height },
		{ x: 0, y: height }
	];
}

export function clampPoint(point: Point, width: number, height: number): Point {
	return {
		x: Math.min(Math.max(point.x, 0), width),
		y: Math.min(Math.max(point.y, 0), height)
	};
}

export function distance(a: Point, b: Point): number {
	return Math.hypot(a.x - b.x, a.y - b.y);
}

/**
 * Rechnet Pointer-Client-Koordinaten (z.B. aus einem PointerEvent) in Bild-Pixel-
 * Koordinaten um. Setzt voraus, dass der übergebene Container exakt im Bildseitenverhältnis
 * dargestellt wird (siehe ReceiptCropCorrector.svelte, `aspect-ratio`-Style) -- dann ist die
 * Umrechnung eine reine lineare Skalierung ohne Letterboxing-Versatz.
 */
export function clientToImagePoint(
	clientX: number,
	clientY: number,
	containerRect: { left: number; top: number; width: number; height: number },
	imageWidth: number,
	imageHeight: number
): Point {
	if (containerRect.width === 0 || containerRect.height === 0) {
		return { x: 0, y: 0 };
	}
	return {
		x: ((clientX - containerRect.left) / containerRect.width) * imageWidth,
		y: ((clientY - containerRect.top) / containerRect.height) * imageHeight
	};
}
