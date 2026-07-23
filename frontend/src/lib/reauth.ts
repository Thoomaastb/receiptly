// Geteilte Typen für den Re-Verifizierungs-Dialog (ReauthDialog.svelte) — in einer eigenen
// .ts-Datei statt aus der .svelte-Komponente re-exportiert, da .svelte-Module keine
// zuverlässig typisierbaren Named Exports neben dem Default-Component-Export unterstützen
// (gleiches Muster wie PasskeyCredentialSummary in webauthn.ts). Aufrufer wie
// settings/security/+page.svelte brauchen diesen Typ für ihre eigenen onSubmit-Handler.

export type ReauthPayload =
	| { current_password: string }
	| { code: string }
	// Seit v0.36.0 (Konto-Löschung): dritte Re-Auth-Methode Passkey.
	| { passkey_credential: string; passkey_options_id: string };

export type ReauthResult = { ok: true; data?: unknown } | { ok: false; error: string };
