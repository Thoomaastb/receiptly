// Geteilte Typen für die Passkey/WebAuthn-Verwaltung (Security-Hardening Phase 3) — in
// einer eigenen .ts-Datei statt aus PasskeyEnrollment.svelte re-exportiert, da .svelte-
// Module keine zuverlässig typisierbaren Named Exports neben dem Default-Component-Export
// unterstützen.

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
