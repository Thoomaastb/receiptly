import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
	appId: 'com.receiptly.app',
	appName: 'receiptly',
	// Zeigt auf den bestehenden SvelteKit-Static-Build (adapter-static) —
	// exakt der Punkt von Capacitor laut Architektur-Doku: keine zweite Codebasis.
	webDir: 'build',
	server: {
		// Für lokale Entwicklung gegen den laufenden Vite-Dev-Server (optional,
		// für Produktion entfernen/auskommentieren — dann lädt die App den
		// gebauten Static-Build direkt aus dem Bundle).
		// url: 'http://localhost:5173',
		// cleartext: true
	}
};

export default config;
