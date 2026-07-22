// Message-Katalog (Deutsch) für die im TOTP/Security-Policy-Paket neu eingeführten
// UI-Texte. Das Projekt hat aktuell keine i18n-Bibliothek eingebunden und liefert nur
// Deutsch aus — dieser Katalog hält aber schon strukturell fest, dass neue Texte nicht
// direkt im Markup hartkodiert werden, sondern über Message-Keys laufen, damit eine
// spätere Mehrsprachigkeit ohne Nacharbeit an diesen Stellen möglich ist. Bestehende,
// bereits vor diesem Paket hartkodierte Texte an anderer Stelle im Projekt wurden bewusst
// NICHT rückwirkend migriert (außerhalb des Auftragsumfangs).
//
// Bei echtem Mehrsprachigkeits-Bedarf: dieses Modul um z.B. `en.ts` erweitern und in
// `index.ts` je nach gewählter Locale auflösen — dafür wäre dann auch eine echte
// i18n-Bibliothek (z.B. svelte-i18n) sinnvoll; das wurde hier bewusst nicht eingeführt,
// siehe Abschlussbericht.

export const de = {
	common: {
		checking: 'Wird geprüft …'
	},

	// Zweiter Login-Schritt (TOTP-Code oder Recovery-Code)
	auth: {
		totpStep: {
			title: 'Zwei-Faktor-Authentifizierung',
			description: 'Gib den 6-stelligen Code aus deiner Authenticator-App ein — oder einen deiner Recovery-Codes, falls du keinen Zugriff mehr auf die App hast.',
			codeLabel: 'Code',
			codeHint: '6-stelliger Code oder Recovery-Code im Format XXXXX-XXXXX',
			codePlaceholder: '123456',
			submit: 'Bestätigen',
			submitting: 'Wird geprüft …',
			backToPassword: 'Zurück zur Anmeldung',
			errorInvalidCode: 'Ungültiger Code.',
			errorExpired: 'Anmeldung abgelaufen oder ungültig — bitte erneut einloggen.',
			genericError: 'Bestätigung fehlgeschlagen — bitte erneut versuchen.'
		}
	},

	// TOTP-Einrichtung (Enrollment-Flow: Intro → QR/Bestätigung → Recovery-Codes)
	totpSetup: {
		startButton: 'Zwei-Faktor-Authentifizierung einrichten',
		startButtonLoading: 'Wird vorbereitet …',
		enrollError: 'Einrichtung konnte nicht gestartet werden — bitte erneut versuchen.',
		settingsIntroDescription: 'Schützt dein Konto zusätzlich zum Passwort mit einem zeitbasierten Code aus einer Authenticator-App (z. B. Aegis, Google Authenticator, 1Password).',
		gateIntroDescription: 'Als Administrator-Konto ist die Einrichtung verpflichtend. Scanne den QR-Code mit einer Authenticator-App und bestätige mit dem angezeigten Code.',
		qrInstructions: 'QR-Code mit einer Authenticator-App scannen, oder den Schlüssel manuell eingeben.',
		manualKeyLabel: 'Schlüssel für die manuelle Eingabe',
		copyKeyButton: 'Kopieren',
		copyKeyButtonCopied: 'Kopiert',
		confirmCodeLabel: 'Bestätigungscode',
		confirmCodeHint: '6-stelliger Code aus der Authenticator-App',
		confirmSubmit: 'Bestätigen',
		confirmSubmitting: 'Wird bestätigt …',
		confirmError: 'Ungültiger Code — bitte erneut versuchen.',
		cancelButton: 'Abbrechen',
		recoveryHeading: 'Deine Recovery-Codes',
		recoveryWarning: 'Jetzt sichern — diese Codes werden nur dieses eine Mal angezeigt und danach nicht erneut abrufbar. Nutze sie, falls du keinen Zugriff mehr auf deine Authenticator-App hast.',
		recoveryCopyAll: 'Alle kopieren',
		recoveryCopyAllCopied: 'Kopiert',
		recoveryDoneButton: 'Ich habe die Codes gesichert'
	},

	// Aktiv-Zustand-Verwaltung in den Sicherheitseinstellungen (Regenerate/Disable)
	totpManage: {
		sectionTitle: 'Zwei-Faktor-Authentifizierung',
		sectionDescription: 'Zusätzlicher Anmeldeschritt per Authenticator-App oder Recovery-Code.',
		statusActiveLabel: 'Aktiv',
		statusInactiveLabel: 'Inaktiv',
		adminLockedNote: 'Für Administrator-Konten ist die Zwei-Faktor-Authentifizierung verpflichtend und kann nicht deaktiviert werden.',
		regenerateButton: 'Neue Recovery-Codes generieren',
		regenerateError: 'Recovery-Codes konnten nicht neu generiert werden.',
		regenerateDialogTitle: 'Neue Recovery-Codes generieren',
		regenerateDialogDescription: 'Bestätige dich, um einen neuen Satz Recovery-Codes zu erzeugen. Die bisherigen Codes werden dabei ungültig.',
		regenerateDialogSubmit: 'Neu generieren',
		disableButton: 'Deaktivieren',
		disableError: 'Deaktivieren fehlgeschlagen.',
		disableDialogTitle: 'Zwei-Faktor-Authentifizierung deaktivieren',
		disableDialogDescription: 'Bestätige dich, um die Zwei-Faktor-Authentifizierung für dieses Konto zu deaktivieren.',
		disableDialogSubmit: 'Deaktivieren'
	},

	// Wiederverwendbarer Re-Verifizierungs-Dialog (Passwort ODER TOTP-Code)
	reauth: {
		methodPasswordLabel: 'Passwort',
		methodTotpLabel: 'TOTP-Code',
		passwordFieldLabel: 'Aktuelles Passwort',
		codeFieldLabel: 'Code aus der Authenticator-App',
		submitting: 'Wird geprüft …',
		closeAriaLabel: 'Schließen',
		genericError: 'Bestätigung fehlgeschlagen — bitte erneut versuchen.'
	},

	// Globales Zwangs-Gate für Admins ohne abgeschlossene TOTP-Einrichtung
	gate: {
		heading: 'Zwei-Faktor-Authentifizierung erforderlich',
		description: 'Als Administrator ist die Einrichtung der Zwei-Faktor-Authentifizierung verpflichtend, bevor du fortfahren kannst.'
	},

	// Admin-Seite Sicherheitsrichtlinien
	securityPolicy: {
		policyCardTitle: 'Sicherheitsrichtlinien',
		policyCardDescription: 'Gilt für alle Mitglieder dieses Haushalts.',
		totpRequiredLabel: 'TOTP-Pflicht für den Haushalt',
		totpRequiredDescription: 'Zwingt auch Nicht-Admin-Mitglieder zur Einrichtung von Zwei-Faktor-Authentifizierung.',
		retentionLabel: 'Audit-Log-Aufbewahrung',
		retentionDescription: 'Wie lange Sicherheitsereignisse gespeichert bleiben, bevor sie automatisch gelöscht werden.',
		retentionOption30: '30 Tage',
		retentionOption90: '90 Tage',
		retentionOption180: '180 Tage',
		retentionOption365: '365 Tage',
		logUsernameLabel: 'Fehlgeschlagene Login-Versuche mit Benutzername protokollieren',
		logUsernameDescription: 'Speichert den eingegebenen Benutzernamen bei fehlgeschlagenen Anmeldeversuchen im Audit-Log.',
		saveButton: 'Speichern',
		saveButtonSaving: 'Speichert …',
		saveSuccess: 'Gespeichert.',
		saveError: 'Speichern fehlgeschlagen.',
		loadError: 'Sicherheitsrichtlinien konnten nicht geladen werden.',
		accessDenied: 'Diese Einstellungen sind nur für Admins sichtbar.',
		auditCardTitle: 'Aktivität im Haushalt',
		auditCardDescription: 'Sicherheitsrelevante Ereignisse aller Mitglieder dieses Haushalts.',
		auditEmpty: 'Noch keine Aktivität.',
		auditLoadError: 'Aktivität konnte nicht geladen werden.',
		auditLoadMore: 'Mehr laden'
	},

	// Admin-Seite E-Mail-Versand (SMTP)
	smtp: {
		cardTitle: 'E-Mail-Versand (SMTP)',
		cardDescription: 'Steuert, über welchen Mailserver Benachrichtigungen und Testmails verschickt werden.',
		lockedBannerPrefix: 'Der SMTP-Server ist serverseitig fest konfiguriert:',
		hostLabel: 'Host',
		portLabel: 'Port',
		usernameLabel: 'Benutzername (optional)',
		passwordLabel: 'Passwort',
		passwordSetHint: 'bereits hinterlegt',
		passwordChangeButton: 'Ändern',
		passwordChangeAriaLabel: 'Passwort ändern',
		passwordCancelButton: 'Abbrechen',
		fromEmailLabel: 'Absender-E-Mail',
		encryptionLabel: 'Verschlüsselung',
		encryptionStarttls: 'STARTTLS (Port 587)',
		encryptionSsl: 'SSL/TLS (Port 465)',
		saveButton: 'Speichern',
		saveButtonSaving: 'Speichert …',
		saveSuccess: 'Gespeichert.',
		saveError: 'Speichern fehlgeschlagen.',
		loadError: 'Einstellungen konnten nicht geladen werden.',
		accessDenied: 'Diese Einstellungen sind nur für Admins sichtbar.',
		testCardTitle: 'Testmail',
		testCardDescription: 'Verschickt eine Testmail an deine eigene E-Mail-Adresse, um die Konfiguration zu prüfen.',
		testButton: 'Testmail senden',
		testButtonSending: 'Wird gesendet …',
		testSuccess: 'Testmail an deine Adresse verschickt — bitte Posteingang prüfen.',
		testError: 'Testmail konnte nicht gesendet werden.',
		testUnavailableHint: 'SMTP muss zuerst konfiguriert und gespeichert werden, bevor eine Testmail verschickt werden kann.'
	}
} as const;
