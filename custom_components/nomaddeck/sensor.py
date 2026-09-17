"""Sensor platform for NomadDeck."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_HEALTH, DATA_STATUS, DOMAIN, MANUFACTURER, MODEL
from .coordinator import NomadDeckCoordinator

FLEET_STATES = ["healthy", "degraded", "error"]
SYNC_STATES = ["synced", "syncing", "offline"]
POWER_STATES = ["on", "off", "unknown"]
JOB_STATES = ["clear", "active"]


def _health(data: dict[str, Any]) -> dict[str, Any]:
    return (data or {}).get(DATA_HEALTH) or {}


def _status(data: dict[str, Any]) -> dict[str, Any]:
    return (data or {}).get(DATA_STATUS) or {}


def _fleet_state(data: dict[str, Any]) -> str:
    health = _health(data)
    if health.get("error"):
        return "error"
    return "healthy" if health.get("ok") else "degraded"


def _sync_state(data: dict[str, Any]) -> str:
    sync = _health(data).get("sync") or {}
    return str(sync.get("state") or "offline")


def _jobs(data: dict[str, Any]) -> dict[str, Any]:
    jobs = _status(data).get("jobs") or {}
    return jobs if isinstance(jobs, dict) else {}


def _jobs_active(data: dict[str, Any]) -> str:
    jobs = _jobs(data)
    for key in ("running", "queued", "active"):
        value = jobs.get(key)
        if isinstance(value, int) and value > 0:
            return "active"
    return "clear"


def _powered_on(data: dict[str, Any]) -> int:
    summary = _health(data).get("summary") or {}
    value = summary.get("power_on")
    return int(value) if isinstance(value, (int, float)) else 0


@dataclass(frozen=True, kw_only=True)
class NomadDeckSensorDescription(SensorEntityDescription):
    """Describes a NomadDeck sensor and how to read it."""

    value_fn: Callable[[dict[str, Any]], Any]


SENSORS: tuple[NomadDeckSensorDescription, ...] = (
    NomadDeckSensorDescription(
        key="fleet_health",
        name="Fleet health",
        device_class=SensorDeviceClass.ENUM,
        options=FLEET_STATES,
        value_fn=_fleet_state,
    ),
    NomadDeckSensorDescription(
        key="api_machines",
        name="Machines reachable",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="machines",
        value_fn=lambda d: (_health(d).get("summary") or {}).get("api_reachable"),
    ),
    NomadDeckSensorDescription(
        key="api_machines_expected",
        name="Machines expected",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="machines",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: (_health(d).get("summary") or {}).get("api_expected"),
    ),
    NomadDeckSensorDescription(
        key="power_targets_on",
        name="Power targets on",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="targets",
        value_fn=_powered_on,
    ),
    NomadDeckSensorDescription(
        key="findings",
        name="Findings",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="findings",
        value_fn=lambda d: len(_health(d).get("findings") or []),
    ),
    NomadDeckSensorDescription(
        key="sync_state",
        name="Sync state",
        device_class=SensorDeviceClass.ENUM,
        options=SYNC_STATES,
        value_fn=_sync_state,
    ),
    NomadDeckSensorDescription(
        key="sync_devices",
        name="Sync devices connected",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="devices",
        value_fn=lambda d: (_health(d).get("sync") or {}).get("connected_devices"),
    ),
    NomadDeckSensorDescription(
        key="sync_devices_expected",
        name="Sync devices expected",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="devices",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: (_health(d).get("sync") or {}).get("expected_devices"),
    ),
    NomadDeckSensorDescription(
        key="sync_divergences",
        name="Sync divergences",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="divergences",
        value_fn=lambda d: len((_health(d).get("sync") or {}).get("divergences") or []),
    ),
    NomadDeckSensorDescription(
        key="jobs_active",
        name="Jobs",
        device_class=SensorDeviceClass.ENUM,
        options=JOB_STATES,
        value_fn=_jobs_active,
    ),
    NomadDeckSensorDescription(
        key="last_sweep",
        name="Last fleet sweep",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _health(d).get("generated_at"),
    ),
    NomadDeckSensorDescription(
        key="version",
        name="Version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _status(d).get("version"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NomadDeck sensors."""
    coordinator: NomadDeckCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        NomadDeckSensor(coordinator, entry, description) for description in SENSORS
    ]

    known_machines: set[str] = set()
    for machine in (coordinator.data.get(DATA_HEALTH) or {}).get("machines", []):
        machine_id = machine.get("id")
        if machine_id:
            entities.append(NomadDeckMachineSensor(coordinator, entry, machine_id))
            known_machines.add(machine_id)

    async_add_entities(entities)

    def _add_new_machines() -> None:
        new_entities = []
        for machine in (coordinator.data.get(DATA_HEALTH) or {}).get("machines", []):
            machine_id = machine.get("id")
            if machine_id and machine_id not in known_machines:
                known_machines.add(machine_id)
                new_entities.append(
                    NomadDeckMachineSensor(coordinator, entry, machine_id)
                )
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_add_new_machines))


class NomadDeckSensor(CoordinatorEntity[NomadDeckCoordinator], SensorEntity):
    """A fleet-wide NomadDeck sensor."""

    entity_description: NomadDeckSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NomadDeckCoordinator,
        entry: ConfigEntry,
        description: NomadDeckSensorDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def device_info(self) -> dict[str, Any]:
        """Group all fleet sensors under one hub device."""
        return {
            "identifiers": {(DOMAIN, "control_plane")},
            "name": "NomadDeck Control Plane",
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "configuration_url": self.coordinator.base_url,
        }

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose a couple of useful details without bloating the recorder."""
        if self.entity_description.key == "version":
            health = _health(self.coordinator.data or {})
            return {"vantage": health.get("vantage")} if health.get("vantage") else None
        return None


class NomadDeckMachineSensor(CoordinatorEntity[NomadDeckCoordinator], SensorEntity):
    """Per-machine power/status sensor."""

    _attr_has_entity_name = True
    _attr_name = "Power"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = POWER_STATES

    def __init__(
        self,
        coordinator: NomadDeckCoordinator,
        entry: ConfigEntry,
        machine_id: str,
    ) -> None:
        """Initialise the per-machine sensor."""
        super().__init__(coordinator)
        self._machine_id = machine_id
        self._attr_unique_id = f"{entry.entry_id}_machine_{machine_id}_power"

    def _machine(self) -> dict[str, Any]:
        for machine in (self.coordinator.data.get(DATA_HEALTH) or {}).get("machines", []):
            if machine.get("id") == self._machine_id:
                return machine
        return {}

    @property
    def device_info(self) -> dict[str, Any]:
        """Attach the machine to its own device, linked to the hub."""
        machine = self._machine()
        return {
            "identifiers": {(DOMAIN, f"machine_{self._machine_id}")},
            "name": machine.get("hostname") or self._machine_id,
            "manufacturer": MANUFACTURER,
            "model": "NomadDeck machine",
            "via_device": (DOMAIN, "control_plane"),
            "configuration_url": self.coordinator.base_url,
        }

    @property
    def available(self) -> bool:
        """Machines without power management still report a state."""
        return super().available

    @property
    def native_value(self) -> str:
        """Return on/off/unknown for the machine's power state."""
        state = str(self._machine().get("power_state") or "").strip().lower()
        if state in ("on", "running", "started"):
            return "on"
        if state in ("off", "stopped", "shutdown"):
            return "off"
        return "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose roles and power target details for the machine."""
        machine = self._machine()
        return {
            "machine_id": self._machine_id,
            "hostname": machine.get("hostname"),
            "roles": machine.get("roles"),
            "power_kind": machine.get("power_kind"),
            "power_target": machine.get("power_target"),
        }
