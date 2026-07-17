export interface ParsedUserAgent {
	browser: string;
	os: string;
}

/**
 * Grobe Heuristik, kein Fingerprinting — reicht für die Sitzungsliste in den
 * Sicherheitseinstellungen (Browser-/Geräte-Familie, keine Versionsdetails).
 * Reihenfolge ist bewusst gewählt: Edge-UAs enthalten "Chrome", Chrome-UAs
 * enthalten "Safari" — spezifischere Marker müssen vor den generischeren geprüft werden.
 */
export function parseUserAgent(ua: string): ParsedUserAgent {
	const browser = detectBrowser(ua);
	const os = detectOs(ua);
	return { browser, os };
}

function detectBrowser(ua: string): string {
	if (!ua) return 'Unbekannt';
	if (ua.includes('Edg/')) return 'Edge';
	if (ua.includes('OPR/') || ua.includes('Opera')) return 'Opera';
	if (ua.includes('Firefox/')) return 'Firefox';
	if (ua.includes('CriOS')) return 'Chrome (iOS)';
	if (ua.includes('Chrome/')) return 'Chrome';
	if (ua.includes('Safari/')) return 'Safari';
	return 'Unbekannter Browser';
}

function detectOs(ua: string): string {
	if (!ua) return 'Unbekannt';
	if (ua.includes('iPhone') || ua.includes('iPad')) return 'iOS';
	if (ua.includes('Android')) return 'Android';
	if (ua.includes('Windows')) return 'Windows';
	if (ua.includes('Mac OS X') || ua.includes('Macintosh')) return 'macOS';
	if (ua.includes('Linux')) return 'Linux';
	return 'Unbekanntes Betriebssystem';
}
