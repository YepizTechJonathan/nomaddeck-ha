"""Binary sensor platform for NomadDeck."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_HEALTH, DOMAIN, MANUFACTURER
from .coordinator import NomadDeckCoordinator


def _health(data: dict[str, Any]) -> dict[str, Any]:
    return (data or {}).get(DATA_HEALTH) or {}


@dataclass(frozen=True, kw_only=True)
class NomadDeckBinaryDescription(BinarySensorEntityDescription):
    """Describes a fleet-wide NomadDeck binary sensor."""

    value_fn: Callable[[dict[str, Any]], bool]


BINARY_SENSORS: tuple[NomadDeckBinaryDescription, ...] = (
    NomadDeckBinaryDescription(
        key="fleet_ok",
        name="Fleet OK",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: not bool(_health(d).get("ok")),
    ),
    NomadDeckBinaryDescription(
        key="sync_ok",
        name="Sync OK",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: not bool((_health(d).get("sync") or {}).get("healthy")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NomadDeck binary sensors, including one per machine."""
    coordinator: NomadDeckCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[BinarySensorEntity] = [
        NomadDeckBinarySensor(coordinator, entry, description)
        for description in BINARY_SENSORS
    ]

    known_machines: set[str] = set()
    for machine in (coordinator.data.get(DATA_HEALTH) or {}).get("machines", []):
        machine_id = machine.get("id")
        if machine_id:
            entities.append(NomadDeckMachineReachability(coordinator, entry, machine_id))
            known_machines.add(machine_id)

    async_add_entities(entities)

    def _add_new_machines() -> None:
        new_entities = []
        for machine in (coordinator.data.get(DATA_HEALTH) or {}).get("machines", []):
            machine_id = machine.get("id")
            if machine_id and machine_id not in known_machines:
                known_machines.add(machine_id)
                new_entities.append(
                    NomadDeckMachineReachability(coordinator, entry, machine_id)
                )
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_add_new_machines))


class NomadDeckBinarySensor(CoordinatorEntity[NomadDeckCoordinator], BinarySensorEntity):
    """A fleet-wide problem binary sensor."""

    entity_description: NomadDeckBinaryDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NomadDeckCoordinator,
        entry: ConfigEntry,
        description: NomadDeckBinaryDescription,
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def device_info(self) -> dict[str, Any]:
        """Group under the control-plane device."""
        return {
            "identifiers": {(DOMAIN, "control_plane")},
            "name": "NomadDeck Control Plane",
            "manufacturer": MANUFACTURER,
            "configuration_url": self.coordinator.base_url,
        }

    @property
    def is_on(self) -> bool:
        """Return True when the problem is present."""
        return bool(self.entity_description.value_fn(self.coordinator.data or {}))


class NomadDeckMachineReachability(CoordinatorEntity[NomadDeckCoordinator], BinarySensorEntity):
    """Whether a machine's NomadDeck API is answering."""

    _attr_has_entity_name = True
    _attr_name = "API reachable"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self,
        coordinator: NomadDeckCoordinator,
        entry: ConfigEntry,
        machine_id: str,
    ) -> None:
        """Initialise the reachability sensor."""
        super().__init__(coordinator)
        self._machine_id = machine_id
        self._attr_unique_id = f"{entry.entry_id}_machine_{machine_id}_api"

    def _machine(self) -> dict[str, Any]:
        for machine in (self.coordinator.data.get(DATA_HEALTH) or {}).get("machines", []):
            if machine.get("id") == self._machine_id:
                return machine
        return {}

    @property
    def device_info(self) -> dict[str, Any]:
        """Attach to the machine device."""
        machine = self._machine()
        return {
            "identifiers": {(DOMAIN, f"machine_{self._machine_id}")},
            "name": machine.get("hostname") or self._machine_id,
            "manufacturer": MANUFACTURER,
            "model": "NomadDeck machine",
            "via_device": (DOMAIN, "control_plane"),
        }

    @property
    def is_on(self) -> bool:
        """Return whether the machine API answered."""
        return bool(self._machine().get("api_ok"))
