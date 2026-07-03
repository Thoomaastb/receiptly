/** @type {import('tailwindcss').Config} */
export default {
	content: ['./src/**/*.{html,js,svelte,ts}'],
	darkMode: 'media', // folgt prefers-color-scheme — kein erzwungenes Dark-Only
	theme: {
		extend: {
			colors: {
				// Alle Farben zeigen auf CSS-Variablen aus app.css — nie hartkodiert,
				// damit Light/Dark und spätere Bucket-Farben zentral gepflegt werden.
				surface: 'var(--color-surface)',
				'surface-raised': 'var(--color-surface-raised)',
				border: 'var(--color-border)',
				text: 'var(--color-text)',
				'text-muted': 'var(--color-text-muted)',
				accent: 'var(--color-accent)',
				'accent-contrast': 'var(--color-accent-contrast)',
				'bucket-household': 'var(--color-bucket-household)'
			},
			borderWidth: {
				DEFAULT: '0.5px'
			}
		}
	},
	plugins: []
};
