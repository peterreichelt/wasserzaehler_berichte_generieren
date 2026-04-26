from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import dotenv_values

from ...exceptions import ConfigError, PlanRadarApiError


logger = logging.getLogger(__name__)


class PlanRadarClient:
    """Kapselt HTTP-Zugriffe auf die PlanRadar-API inklusive Retry-Logik."""

    def __init__(
        self,
        *,
        base_url: str,
        customer_id: str,
        api_key: str,
        request_pause_seconds: float = 2.1,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        """Initialisiert den PlanRadar-Client.

        Args:
            base_url: Basis-URL der PlanRadar-API.
            customer_id: PlanRadar-Kunden-ID.
            api_key: API-Schlüssel.
            request_pause_seconds: Pause zwischen zwei Requests.
            timeout_seconds: Timeout pro Request.
            max_retries: Maximale Anzahl an Wiederholungen.
        """
        self.base_url = base_url.rstrip("/")
        self.customer_id = customer_id
        self.request_pause_seconds = request_pause_seconds
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._last_request_at = 0.0
        self._session = requests.Session()
        self._session.headers.update(
            {
                "X-PlanRadar-API-Key": api_key,
                "accept": "application/json",
            }
        )

    @classmethod
    def from_env_files(
        cls,
        *,
        customer_id: str,
        env_files: list[str],
        request_pause_seconds: float,
        base_url: str = "https://www.planradar.com",
    ) -> "PlanRadarClient":
        """Erzeugt einen API-Client auf Basis der konfigurierten Umgebungsdateien."""
        api_key: str | None = None
        for candidate in env_files:
            path = Path(candidate)
            if path.name != ".env":
                continue
            if not path.exists():
                continue
            values = dotenv_values(path)
            api_key = values.get("PLANRADAR_API_KEY") or values.get("API_KEY")
            if api_key:
                break
        if not api_key:
            raise ConfigError(
                "Es wurde kein gültiger PlanRadar-API-Schlüssel gefunden. Legen Sie eine .env-Datei an und setzen Sie dort PLANRADAR_API_KEY."
            )
        return cls(
            base_url=base_url,
            customer_id=customer_id,
            api_key=api_key,
            request_pause_seconds=request_pause_seconds,
        )

    def _wait_for_rate_limit(self) -> None:
        """Erzwingt eine Mindestpause zwischen zwei API-Anfragen."""
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.request_pause_seconds:
            time.sleep(self.request_pause_seconds - elapsed)

    def get_json(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Lädt eine JSON-Antwort von der PlanRadar-API."""
        url = f"{self.base_url}{path}"
        response = self._request("GET", url, timeout=self.timeout_seconds, failure_label=path)
        try:
            return response.json()
        except ValueError as exc:
            raise PlanRadarApiError(f"PlanRadar hat ungültiges JSON für {path} zurückgegeben.") from exc
        raise PlanRadarApiError(f"Die PlanRadar-Anfrage ist nach mehreren Versuchen fehlgeschlagen: {path}")

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
        headers: dict[str, str] | None = None,
        failure_label: str,
    ) -> requests.Response:
        """Führt einen generischen HTTP-Request mit Retry- und Fehlerlogik aus."""
        backoff = self.request_pause_seconds
        for attempt in range(1, self.max_retries + 1):
            self._wait_for_rate_limit()
            response = self._session.request(
                method,
                url,
                params=params,
                timeout=timeout or self.timeout_seconds,
                headers=headers,
            )
            self._last_request_at = time.monotonic()
            if response.status_code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                logger.warning(
                    "PlanRadar-Anfrage für %s ist mit %s fehlgeschlagen. Neuer Versuch in %.1fs.",
                    response.status_code,
                    failure_label,
                    backoff,
                )
                time.sleep(backoff)
                backoff *= 2
                continue
            if response.status_code >= 400:
                raise PlanRadarApiError(
                    f"PlanRadar-Anfrage für {failure_label} fehlgeschlagen: HTTP {response.status_code} - {response.text[:400]}"
                )
            return response
        raise PlanRadarApiError(f"Die PlanRadar-Anfrage ist nach mehreren Versuchen fehlgeschlagen: {failure_label}")

    def download_file(self, url: str, destination: Path, *, timeout_seconds: float | None = None) -> None:
        """Lädt eine Datei von einer URL direkt auf das Dateisystem herunter."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        response = self._request(
            "GET",
            url,
            timeout=timeout_seconds or self.timeout_seconds,
            headers={"accept": "*/*"},
            failure_label=url,
        )
        destination.write_bytes(response.content)

    def get_paginated(self, path: str, *, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Lädt alle Seiten eines Listenendpunkts nacheinander ein."""
        combined: list[dict[str, Any]] = []
        page = 1
        while True:
            request_params = dict(params or {})
            request_params.setdefault("page", page)
            payload = self.get_json(path, params=request_params)
            data = payload.get("data") or []
            if not isinstance(data, list):
                raise PlanRadarApiError(f"Für {path} wurde eine Listen-Antwort erwartet.")
            combined.extend(data)
            meta = payload.get("meta") or {}
            count = meta.get("count")
            if len(data) == 0 or (isinstance(count, int) and len(combined) >= count):
                return combined
            page += 1
