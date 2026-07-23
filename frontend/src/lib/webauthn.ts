// Geteilte Typen für die Passkey/WebAuthn-Verwaltung (Security-Hardening Phase 3) — in
// einer eigenen .ts-Datei statt aus PasskeyEnrollment.svelte re-exportiert, da .svelte-
// Module keine zuverlässig typisierbaren Named Exports neben dem Default-Component-Export
// unterstützen.

import { startAuthentication, type PublicKeyCredentialRequestOptionsJSON } from '@simplewebauthn/browser';

// Verwaltungsfelder eines registrierten Passkeys, wie sie GET/PATCH/POST /webauthn/...
// liefern — enthält bewusst NIE public_key/credential_id (siehe API-Vertrag).
export interface PasskeyCredentialSummary {
	id: string;
	device_label: string;
	created_at: string;
	last_used_at: string | null;
	// Backend liefert transports als einzelnen String (kommasepariert), nicht als Array —
	// gegen backend/app/schemas/webauthn.py:WebauthnCredentialResponse verifiziert.
	transports: string | null;
}

export interface PasskeyAssertionResult {
	// Bereits JSON.stringify'te Credential-Response — so, wie es der jeweilige
	// Verify-Endpoint als `credential`-Feld erwartet (siehe /webauthn/authenticate/verify
	// und /account/deletion).
	credential: string;
	options_id: string;
}

// Konto-übergreifender WebAuthn-Assertion-Helper (v0.36.0, Konto-Löschung): extrahiert die
// Options→startAuthentication-Sequenz aus login/+page.svelte::handlePasskeyLogin, die sonst
// ein zweites Mal für die Löschbestätigung dupliziert werden müsste. Macht bewusst NUR die
// Options-Anfrage + die Browser-Ceremony — der Verify-Request bleibt beim jeweiligen
// Aufrufer, weil sich der Endpoint (Login vs. Konto-Löschung) unterscheidet und
// aufrufer-spezifische Fehlerbehandlung (z.B. der Login-Sonderfall "unbekannter Username
// darf nicht von falschem Passkey unterscheidbar sein") hier nicht pauschalisiert werden
// soll. Wirft bei einem fehlgeschlagenen Options-Request einen undekorierten technischen
// Error (kein i18n-Text) — Lokalisierung der Fehlermeldung bleibt bewusst beim Aufrufer,
// damit dieselbe Helper-Funktion nicht an eine bestimmte Aufrufer-Textwahl gekoppelt wird.
export async function runPasskeyAssertion(
	optionsEndpoint: string,
	optionsBody: object = {}
): Promise<PasskeyAssertionResult> {
	const optionsRes = await fetch(optionsEndpoint, {
		method: 'POST',
		credentials: 'include',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(optionsBody)
	});
	if (!optionsRes.ok) {
		throw new Error(`passkey-options-request-failed:${optionsRes.status}`);
	}
	const { options, options_id } = await optionsRes.json();
	const optionsJSON: PublicKeyCredentialRequestOptionsJSON = JSON.parse(options);
	const credential = await startAuthentication({ optionsJSON });
	return { credential: JSON.stringify(credential), options_id };
}
