"""
HTML-E-Mail-Templates im receiptly-Hifi-Design.

Für E-Mail-Clients angepasst: table-basiertes Layout (Outlook), alle Styles inline,
kein oklch()/Flexbox/Grid, keine externen Assets/Web-Fonts (DSGVO). Die Hex-Werte sind
aus den OKLCH-Design-Tokens in frontend/src/app.css umgerechnet, Kontrast auf WCAG AA
geprüft (Fließtext >= 4.5:1, Button-Label weiß auf Akzent = 4.62:1).

Aufbau bewusst schlank: _shell() liefert die gemeinsame Hülle (Wordmark, Karte, Footer),
render_*()-Funktionen füllen nur den Karteninhalt. Weitere Mail-Typen (z.B. Einladung)
ergänzen künftig eine eigene render_*()-Funktion über dieselbe Hülle.

**Jede** von send_email() verschickte Mail MUSS über eine render_*()-Funktion hier laufen
(kein text_body-only-Versand) — 2026-07-22 wurde die Benachrichtigungs-Mail als Lücke
gemeldet (lief nur als Plain-Text), seitdem verbindliche Regel statt Einzelfall-Fix.

Jede Karte trägt ein Eyebrow-Badge (_eyebrow()) mit Severity-Farbe (`kind`): info=blau,
warnung=orange, fehler/sicherheit=rot (Nutzer-Vorgabe 2026-07-22) — als Indikator für die
Mail-Art auf einen Blick, nicht nur Text-Label.
"""

from __future__ import annotations

from html import escape

# --- Farb-Tokens: OKLCH (app.css) -> E-Mail-sichere Hex-Approximation ---------------
# Light ist die robuste Basis; Dark-Gegenstücke greifen nur via prefers-color-scheme.
_C = {
    "bg": "#FAF8F4",  # --color-bg
    "surface": "#FEFDFA",  # --color-surface-hifi
    "border": "#E0DED8",  # --color-border-hifi
    "text": "#191A24",  # --color-text-hifi
    "muted": "#61626F",  # --color-text-muted-hifi (5.92:1 auf surface)
    "accent": "#7D5EE0",  # --color-accent-hifi (Button-Fläche)
    "accent_tint": "#EAE8FF",  # --color-accent-tint (Akzent-Hintergrund)
    "accent_text": "#5A34B4",  # --color-accent-text (6.76:1 auf accent-tint)
    # Severity-Indikator fürs Eyebrow-Badge (Nutzer-Vorgabe 2026-07-22): info=blau,
    # warnung=orange, fehler/sicherheit=rot. Orange/Rot sind exakte Umrechnungen der
    # bestehenden --color-status-warning/--color-danger-Tokens (app.css); "info" gibt es
    # als App-Design-Token bisher nicht — hier neu mit demselben L/C-Profil wie warning,
    # nur Hue 235 (klares Blau, komplementär zur Akzent-Hue 280), damit es sich ins
    # bestehende Farbschema einfügt statt eine beliebige Farbe zu erfinden.
    "info": "#008CD1",
    "info_tint": "#DFF6FF",
    "warning": "#BB6A00",  # --color-status-warning
    "warning_tint": "#FFEFDD",  # --color-status-warning-bg
    "danger": "#BE222A",  # --color-danger
    "danger_tint": "#FFEDEB",  # --color-danger-bg
    "white": "#FFFFFF",
    # Dark-Gegenstücke
    "d_bg": "#0E0D0A",
    "d_surface": "#171612",
    "d_border": "#302E29",
    "d_text": "#E5E7F2",
    "d_muted": "#9C9DA9",
    "d_accent_tint": "#242136",
    "d_accent_text": "#BDB0FF",
    "d_info": "#40BEFD",
    "d_info_tint": "#122733",
    "d_warning": "#E9A03E",
    "d_warning_tint": "#2F2110",
    "d_danger": "#F66D67",
    "d_danger_tint": "#331D1B",
}

# kind -> (Tint-Key, Text-Key) fürs Eyebrow-Badge, siehe _eyebrow(). "accent" bleibt als
# neutrale/Marken-Variante erhalten (kein Severity-Indikator, sondern der bisherige
# Purpur-Badge-Look für Fälle ohne info/warnung/gefahr-Einstufung).
_KIND_COLORS: dict[str, tuple[str, str]] = {
    "info": ("info_tint", "info"),
    "warning": ("warning_tint", "warning"),
    "danger": ("danger_tint", "danger"),
    "accent": ("accent_tint", "accent_text"),
}

# Font-Stack: die meisten Clients fallen auf den System-/Arial-Fallback zurück.
_FONT = (
    "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', "
    "Roboto, Helvetica, Arial, sans-serif"
)
_RADIUS_CARD = "16px"  # Karten-Radius (app.css)
_RADIUS_CTRL = "10px"  # Button-/Input-Radius (app.css)


def _eyebrow(label: str, kind: str = "accent") -> str:
    """
    Farblich kodiertes Badge am Kartenkopf. `kind` ∈ {"info", "warning", "danger",
    "accent"} — steuert sowohl die inline Light-Mode-Farbe hier als auch (über die
    `em-eyebrow-{kind}`-Klasse) die Dark-Mode-Farbe in _shell()'s <style>-Block.
    """
    tint_key, text_key = _KIND_COLORS[kind]
    label_txt = escape(label)
    return (
        f'<span class="em-eyebrow-{kind}" style="display:inline-block;'
        f"background-color:{_C[tint_key]};color:{_C[text_key]};font-family:{_FONT};"
        f"font-size:12px;font-weight:700;letter-spacing:0.04em;text-transform:uppercase;"
        f'padding:6px 12px;border-radius:999px;">{label_txt}</span>'
    )


def _button(href: str, label: str) -> str:
    """
    Outlook-kompatibler CTA: VML-roundrect (mso) + <a>-Padding-Muster (alle anderen).
    Kein <button> — Outlook rendert das nicht zuverlässig. arcsize 21% ~= 10px/48px.
    """
    href_attr = escape(href, quote=True)
    label_txt = escape(label)
    return f"""\
<!--[if mso]>
<v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word" href="{href_attr}" style="height:48px;v-text-anchor:middle;width:280px;" arcsize="21%" strokecolor="{_C['accent']}" fillcolor="{_C['accent']}">
<w:anchorlock/>
<center style="color:{_C['white']};font-family:{_FONT};font-size:16px;font-weight:bold;">{label_txt}</center>
</v:roundrect>
<![endif]-->
<!--[if !mso]><!-- -->
<a href="{href_attr}" style="display:inline-block;background-color:{_C['accent']};color:{_C['white']};font-family:{_FONT};font-size:16px;font-weight:700;line-height:20px;text-decoration:none;padding:14px 32px;border-radius:{_RADIUS_CTRL};mso-padding-alt:0;">{label_txt}</a>
<!--<![endif]-->"""


def _shell(*, subject: str, preheader: str, card_inner: str) -> str:
    """
    Gemeinsame Mail-Hülle: Doc-Head (mso/color-scheme), Seitenhintergrund, zentrierter
    600px-Container, Wordmark, Karte (Radius 16px), dezenter Footer. Der dark-Block ist
    ein Nice-to-have; inline-Light bleibt die verlässliche Basis.
    """
    subj = escape(subject)
    pre = escape(preheader)
    return f"""\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "https://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="https://www.w3.org/1999/xhtml" lang="de">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<meta http-equiv="X-UA-Compatible" content="IE=edge" />
<meta name="color-scheme" content="light dark" />
<meta name="supported-color-schemes" content="light dark" />
<title>{subj}</title>
<!--[if mso]>
<noscript><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml></noscript>
<![endif]-->
<style>
  body {{ margin:0; padding:0; width:100% !important; -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%; }}
  table {{ border-collapse:collapse; }}
  a {{ color:{_C['accent_text']}; }}
  @media only screen and (max-width:600px) {{
    .em-card-pad {{ padding:28px 24px !important; }}
    .em-wrap-pad {{ padding:24px 12px !important; }}
  }}
  @media (prefers-color-scheme: dark) {{
    .em-bg {{ background-color:{_C['d_bg']} !important; }}
    .em-card {{ background-color:{_C['d_surface']} !important; border-color:{_C['d_border']} !important; }}
    .em-text {{ color:{_C['d_text']} !important; }}
    .em-muted {{ color:{_C['d_muted']} !important; }}
    .em-infobox {{ background-color:{_C['d_accent_tint']} !important; color:{_C['d_accent_text']} !important; }}
    .em-infobox * {{ color:{_C['d_accent_text']} !important; }}
    .em-eyebrow-accent {{ background-color:{_C['d_accent_tint']} !important; color:{_C['d_accent_text']} !important; }}
    .em-eyebrow-info {{ background-color:{_C['d_info_tint']} !important; color:{_C['d_info']} !important; }}
    .em-eyebrow-warning {{ background-color:{_C['d_warning_tint']} !important; color:{_C['d_warning']} !important; }}
    .em-eyebrow-danger {{ background-color:{_C['d_danger_tint']} !important; color:{_C['d_danger']} !important; }}
    .em-divider {{ border-color:{_C['d_border']} !important; }}
  }}
</style>
</head>
<body class="em-bg" style="margin:0;padding:0;background-color:{_C['bg']};">
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;line-height:1px;color:{_C['bg']};opacity:0;">{pre}</div>
<table role="presentation" class="em-bg" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:{_C['bg']};">
<tr>
<td align="center" class="em-wrap-pad" style="padding:40px 16px;">
<!--[if mso]><table role="presentation" width="600" align="center" cellpadding="0" cellspacing="0" border="0"><tr><td><![endif]-->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;margin:0 auto;">
<tr>
<td style="padding:0 4px 20px 4px;font-family:{_FONT};">
<span class="em-text" style="font-family:{_FONT};font-size:22px;font-weight:800;letter-spacing:-0.02em;color:{_C['text']};">receipt<span style="color:{_C['accent']};">ly</span></span>
</td>
</tr>
<tr>
<td class="em-card" style="background-color:{_C['surface']};border:1px solid {_C['border']};border-radius:{_RADIUS_CARD};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>
<td class="em-card-pad" style="padding:40px 40px;font-family:{_FONT};">
{card_inner}
</td>
</tr>
</table>
</td>
</tr>
<tr>
<td style="padding:24px 4px 0 4px;font-family:{_FONT};">
<p class="em-muted" style="margin:0;font-family:{_FONT};font-size:12px;line-height:18px;color:{_C['muted']};">
receiptly &middot; Belege automatisch erfasst<br />
Diese Nachricht wurde automatisch versendet &mdash; bitte antworte nicht darauf.
</p>
</td>
</tr>
</table>
<!--[if mso]></td></tr></table><![endif]-->
</td>
</tr>
</table>
</body>
</html>"""


def render_test_email() -> str:
    """Rendert die Admin-Testmail (Einstellungen -> Sicherheitsrichtlinien) als HTML-String."""
    card_inner = f"""\
{_eyebrow("SMTP-Test", "info")}
<h1 class="em-text" style="margin:18px 0 0 0;font-family:{_FONT};font-size:26px;line-height:32px;font-weight:800;letter-spacing:-0.02em;color:{_C['text']};">Testmail erfolgreich</h1>
<p class="em-muted" style="margin:14px 0 0 0;font-family:{_FONT};font-size:16px;line-height:24px;color:{_C['muted']};">
Wenn du das hier liest, ist dein SMTP-Versand korrekt konfiguriert — Passwort-Reset- und andere Systemmails sollten damit zuverlässig ankommen.
</p>"""
    return _shell(
        subject="receiptly – Testmail",
        preheader="SMTP-Versand funktioniert — diese Testmail kam erfolgreich an.",
        card_inner=card_inner,
    )


def render_password_reset_email(reset_link: str) -> str:
    """
    Rendert die Passwort-Reset-Mail als vollständigen HTML-String.

    :param reset_link: absoluter Reset-Link (wird HTML-escaped in href + Fallback-Text).
    :returns: fertiges HTML-Dokument für send_email(..., html_body=...).
    """
    link_txt = escape(reset_link)  # sichtbarer Fallback-Link
    button = _button(reset_link, "Neues Passwort vergeben")
    card_inner = f"""\
{_eyebrow("Kontosicherheit", "danger")}
<h1 class="em-text" style="margin:18px 0 0 0;font-family:{_FONT};font-size:26px;line-height:32px;font-weight:800;letter-spacing:-0.02em;color:{_C['text']};">Passwort zur&uuml;cksetzen</h1>
<p class="em-muted" style="margin:14px 0 0 0;font-family:{_FONT};font-size:16px;line-height:24px;color:{_C['muted']};">
Hallo,<br />
f&uuml;r dein receiptly-Konto wurde ein Passwort-Reset angefordert. Klicke auf den Button, um ein neues Passwort zu vergeben.
</p>
<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:28px 0 0 0;">
<tr><td align="left">{button}</td></tr>
</table>
<p class="em-muted" style="margin:22px 0 0 0;font-family:{_FONT};font-size:13px;line-height:20px;color:{_C['muted']};">
Button funktioniert nicht? Kopiere diesen Link in deinen Browser:<br />
<a href="{escape(reset_link, quote=True)}" style="color:{_C['accent_text']};word-break:break-all;">{link_txt}</a>
</p>
<div class="em-infobox" style="margin:28px 0 0 0;background-color:{_C['accent_tint']};border-radius:{_RADIUS_CTRL};padding:12px 16px;font-family:{_FONT};font-size:14px;line-height:20px;color:{_C['accent_text']};font-weight:600;">
Der Link ist 30 Minuten g&uuml;ltig.
</div>
<div class="em-divider" style="margin:28px 0 0 0;border-top:1px solid {_C['border']};font-size:0;line-height:0;">&nbsp;</div>
<p class="em-muted" style="margin:20px 0 0 0;font-family:{_FONT};font-size:13px;line-height:20px;color:{_C['muted']};">
Falls du das nicht angefordert hast, kannst du diese E-Mail ignorieren &mdash; dein Passwort bleibt unver&auml;ndert.
</p>"""
    return _shell(
        subject="receiptly – Passwort zurücksetzen",
        preheader="Setze dein receiptly-Passwort zurück — der Link ist 30 Minuten gültig.",
        card_inner=card_inner,
    )


# category (Notification.category, siehe app/models/notification.py) -> Eyebrow-Label +
# Severity-Kind. Nutzer-Vorgabe 2026-07-22: info=blau, warnung=orange, fehler/sicherheit=rot.
# "garantie" ist eine Fristerinnerung (noch nichts falsch, aber Aufmerksamkeit nötig) ->
# warning/orange. "sicherheit" faellt unter die "sicherheit"-rot-Regel des Nutzers direkt.
# Unbekannte Kategorien (zukünftige Typen) fallen auf "info"/blau zurück statt zu crashen.
_CATEGORY_EYEBROW: dict[str, tuple[str, str]] = {
    "garantie": ("Garantie", "warning"),
    "sicherheit": ("Sicherheit", "danger"),
}


def render_notification_email(*, category: str, title: str, body: str, link: str | None = None) -> str:
    """
    Rendert eine Benachrichtigungs-Mail (Benachrichtigungssystem, v0.25) als HTML-String —
    einziger send_email(...)-Aufrufer, der bislang OHNE html_body auskam (2026-07-22 als
    Lücke gemeldet: "Mail-Templates scheinen nicht überall zu greifen").

    :param category: `Notification.category` ("garantie"/"sicherheit"/künftige Werte) —
        bestimmt Eyebrow-Label und Farb-Indikator (siehe _CATEGORY_EYEBROW).
    :param link: bereits ABSOLUTER Link (Aufrufer hängt `settings.public_app_url` selbst
        vor den app-relativen Pfad, siehe services/notifications.py — analog dazu, wie
        render_password_reset_email() ebenfalls einen fertigen absoluten Link entgegennimmt,
        nicht relativ + Base-URL getrennt).
    :returns: fertiges HTML-Dokument für send_email(..., html_body=...).
    """
    eyebrow_label, kind = _CATEGORY_EYEBROW.get(category, ("Hinweis", "info"))
    title_txt = escape(title)
    body_txt = escape(body)
    cta = ""
    if link is not None:
        button = _button(link, "Ansehen")
        cta = f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:28px 0 0 0;">
<tr><td align="left">{button}</td></tr>
</table>"""
    card_inner = f"""\
{_eyebrow(eyebrow_label, kind)}
<h1 class="em-text" style="margin:18px 0 0 0;font-family:{_FONT};font-size:26px;line-height:32px;font-weight:800;letter-spacing:-0.02em;color:{_C['text']};">{title_txt}</h1>
<p class="em-muted" style="margin:14px 0 0 0;font-family:{_FONT};font-size:16px;line-height:24px;color:{_C['muted']};">
{body_txt}
</p>{cta}"""
    return _shell(
        subject=f"receiptly – {title}",
        preheader=body,
        card_inner=card_inner,
    )
