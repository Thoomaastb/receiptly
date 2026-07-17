/** @type {import('tailwindcss').Config} */
export default {
	content: ['./src/**/*.{html,js,svelte,ts}'],
	// Attribut-Override statt OS-Einstellung: [data-theme="dark"] gewinnt immer,
	// dark:-Utilities folgen nie unbeabsichtigt der OS-Einstellung (siehe theme.ts).
	darkMode: ['selector', '[data-theme="dark"]'],
	theme: {
		extend: {
			colors: {
				// Alle Farben zeigen auf CSS-Variablen aus app.css — nie hartkodiert,
				// damit Light/Dark und spätere Bucket-Farben zentral gepflegt werden.

				// Hifi-Palette (Shell + Home, Handoff Claude Design 2026-07-04)
				'hifi-bg': 'var(--color-bg)',
				'hifi-surface': 'var(--color-surface-hifi)',
				'hifi-border': 'var(--color-border-hifi)',
				'hifi-text': 'var(--color-text-hifi)',
				'hifi-text-muted': 'var(--color-text-muted-hifi)',
				'hifi-text-faint': 'var(--color-text-faint)',
				'hifi-accent': 'var(--color-accent-hifi)',
				'hifi-accent-tint': 'var(--color-accent-tint)',
				'hifi-accent-text': 'var(--color-accent-text)',
				'cat-electronics': 'var(--color-cat-electronics)',
				'cat-groceries': 'var(--color-cat-groceries)',
				'cat-travel': 'var(--color-cat-travel)',
				'cat-furniture': 'var(--color-cat-furniture)',
				'cat-fashion': 'var(--color-cat-fashion)',
				'cat-dining': 'var(--color-cat-dining)',
				'cat-fuel': 'var(--color-cat-fuel)',
				success: 'var(--color-success)',
				'success-bg': 'var(--color-success-bg)',
				'success-border': 'var(--color-success-border)',
				'status-warning': 'var(--color-status-warning)',
				'status-warning-bg': 'var(--color-status-warning-bg)',
				'status-warning-border': 'var(--color-status-warning-border)',
				danger: 'var(--color-danger)',
				'danger-bg': 'var(--color-danger-bg)',
				'danger-border': 'var(--color-danger-border)'
			},
			fontFamily: {
				ui: 'var(--font-ui)',
				mono: 'var(--font-mono)'
			},
			borderWidth: {
				DEFAULT: '0.5px'
			}
		}
	},
	plugins: []
};
