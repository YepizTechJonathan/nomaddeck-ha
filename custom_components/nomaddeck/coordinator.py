"""DataUpdateCoordinator for NomadDeck."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DATA_HEALTH,
    DATA_STATUS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ENDPOINT_HEALTH,
    ENDPOINT_STATUS,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 20


class NomadDeckCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch fleet health and system status from the NomadDeck control plane."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"

    @property
    def control_plane_id(self) -> str | None:
        """Return the control plane's machine id, if known."""
        health = (self.data or {}).get(DATA_HEALTH) or {}
        for machine in health.get("machines", []):
            if "control" in (machine.get("roles") or []):
                return machine.get("id")
        return None

    async def _async_get(self, session, path: str) -> dict[str, Any]:
        """Fetch one JSON document from the control plane."""
        try:
            async with session.get(self.base_url + path, timeout=REQUEST_TIMEOUT) as resp:
                if resp.status != 200:
                    raise UpdateFailed(
                        f"NomadDeck API {path} returned HTTP {resp.status}"
                    )
                return await resp.json(content_type=None)
        except UpdateFailed:
            raise
        except Exception as err:  # noqa: BLE001 - surfaced to HA as UpdateFailed
            raise UpdateFailed(f"Error talking to NomadDeck at {self.base_url}: {err}") from err

    async def _async_update_data(self) -> dict[str, Any]:
        """Poll both endpoints; health is mandatory, status is best-effort."""
        session = async_get_clientsession(self.hass)

        health = await self._async_get(session, ENDPOINT_HEALTH)
        if not isinstance(health, dict) or "machines" not in health:
            raise UpdateFailed("NomadDeck fleet-health payload was not understood")

        try:
            status = await self._async_get(session, ENDPOINT_STATUS)
        except UpdateFailed as err:
            _LOGGER.debug("NomadDeck status endpoint unavailable: %s", err)
            status = {}

        return {DATA_HEALTH: health, DATA_STATUS: status}
