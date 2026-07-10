import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		port: 5173,
		host: true,
		proxy: {
			// Kein rewrite: das Backend hängt seine Router selbst unter "/api" (siehe
			// app/main.py), genau wie die Prod-nginx-Config sie unverändert durchreicht
			// (siehe frontend/nginx.conf). Ein "/api"-Strip hier führte dazu, dass jeder
			// API-Call im Dev-Server (`npm run dev`) mit 404 vom Backend fehlschlug.
			'/api': {
				target: 'http://localhost:8000',
				changeOrigin: true
			}
		}
	}
});
