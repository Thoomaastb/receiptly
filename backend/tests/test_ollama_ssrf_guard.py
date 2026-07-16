"""
Security-Review-Härtung: _validate_ollama_host() in app/api/settings.py (SSRF-Schutz beim
Speichern von PUT /settings/ai-provider). Reine Funktion ohne DB-Abhängigkeit — testbar wie
test_pii_redaction.py, hier aber async (DNS-Auflösung läuft über asyncio.to_thread), daher
über asyncio.run() ausgeführt statt pytest-asyncio (das im Projekt nicht konfiguriert ist).

Für IP-Literale (z.B. "169.254.169.254") braucht getaddrinfo() keine echte DNS-Anfrage —
das ist rein lokales Parsen und damit ohne Netzwerkzugriff deterministisch testbar. Für den
Compose-Servicenamen-Fall wird getaddrinfo() bewusst gemockt, damit der Test nicht vom
tatsächlichen DNS-Verhalten der jeweiligen Testumgebung abhängt.
"""

import asyncio
import socket
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.api.settings import _validate_ollama_host


def _run(endpoint_url: str) -> None:
    asyncio.run(_validate_ollama_host(endpoint_url))


def test_cloud_metadata_ip_is_rejected():
    with pytest.raises(HTTPException) as exc_info:
        _run("http://169.254.169.254/")
    assert exc_info.value.status_code == 400


def test_loopback_ip_is_rejected():
    with pytest.raises(HTTPException) as exc_info:
        _run("http://127.0.0.1:11434")
    assert exc_info.value.status_code == 400


def test_private_range_ip_is_rejected():
    with pytest.raises(HTTPException) as exc_info:
        _run("http://10.0.0.5:11434")
    assert exc_info.value.status_code == 400


def test_public_ip_is_accepted():
    # Kein SSRF-Ziel -> darf nicht blockiert werden (wirft nichts)
    _run("http://8.8.8.8/")


def test_unresolvable_compose_service_name_is_accepted():
    # "ollama" löst in diesem Prozess nicht auf (kein Docker-DNS außerhalb des Containers)
    # -- der Normalfall für self-hosted Compose-Deployments. Ein DNS-Fehler darf NICHT als
    # Ablehnungsgrund gewertet werden, sonst wäre "http://ollama:11434" kategorisch verboten.
    with patch("app.api.settings.socket.getaddrinfo", side_effect=socket.gaierror):
        _run("http://ollama:11434")  # wirft nicht


def test_url_without_hostname_is_not_blocked():
    # Kein gültiger Host geparst (z.B. leerer/kaputter URL-Rest) -> nichts zu prüfen,
    # nicht Aufgabe dieser Funktion, ein ungültiges Format abzulehnen.
    _run("not-a-url")
