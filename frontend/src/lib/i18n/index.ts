import { de } from './de';

// Einziger Einstiegspunkt für Message-Keys — Komponenten importieren ausschließlich `m`,
// nie `de` direkt. Sobald eine zweite Locale existiert, wird hier nach der aktiven
// Sprache aufgelöst, ohne dass Call-Sites sich ändern müssen.
export const m = de;
