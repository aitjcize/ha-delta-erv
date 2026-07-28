"""Select platform for Delta ERV integration."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BYPASS_AUTO,
    BYPASS_BYPASS,
    BYPASS_HEAT_EXCHANGE,
    DOMAIN,
    INTERNAL_CIRC_HEAT_EXCHANGE,
    INTERNAL_CIRC_INTERNAL,
    POWER_ON,
    REG_BYPASS_FUNCTION,
    REG_INTERNAL_CIRCULATION,
    REG_POWER,
)
from .coordinator import DeltaERVDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Bypass mode mapping
BYPASS_MODES = {
    "Heat Exchange": BYPASS_HEAT_EXCHANGE,
    "Bypass": BYPASS_BYPASS,
    "Auto": BYPASS_AUTO,
}
BYPASS_MODES_REVERSE = {v: k for k, v in BYPASS_MODES.items()}

# Internal circulation mapping
INTERNAL_CIRC_MODES = {
    "Heat Exchange": INTERNAL_CIRC_HEAT_EXCHANGE,
    "Internal Circulation": INTERNAL_CIRC_INTERNAL,
}
INTERNAL_CIRC_MODES_REVERSE = {v: k for k, v in INTERNAL_CIRC_MODES.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Delta ERV select platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: DeltaERVDataUpdateCoordinator = data["coordinator"]
    name = data["config"][CONF_NAME]

    async_add_entities(
        [
            DeltaERVBypassSelect(coordinator, name),
            DeltaERVInternalCirculationSelect(coordinator, name),
        ]
    )


class DeltaERVSelectBase(
    CoordinatorEntity[DeltaERVDataUpdateCoordinator], SelectEntity
):
    """Base select bound to the shared coordinator.

    Availability is inherited from CoordinatorEntity (unavailable when the ERV
    is unreachable). Writes are gated on the device being powered on.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator, name):
        """Initialize the selector."""
        super().__init__(coordinator)
        self._device_name = name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{name}_fan")},
            "name": name,
            "manufacturer": "Delta",
            "model": "ERV",
        }

    @property
    def _client(self):
        """Modbus client (writes bypass the coordinator's read cache)."""
        return self.coordinator.client

    async def _require_power_on(self) -> bool:
        """Return True if the ERV is on; log and return False otherwise."""
        power = await self._client.async_read_register(REG_POWER)
        return bool(power) and power.registers[0] == POWER_ON


class DeltaERVBypassSelect(DeltaERVSelectBase):
    """Representation of Delta ERV Bypass Mode selector."""

    _attr_name = "Bypass Mode"
    _attr_options = list(BYPASS_MODES.keys())

    def __init__(self, coordinator, name):
        """Initialize the bypass selector."""
        super().__init__(coordinator, name)
        self._attr_unique_id = f"{name}_bypass_mode"

    @property
    def current_option(self):
        """Return the current bypass mode."""
        value = self.coordinator.data.get(REG_BYPASS_FUNCTION)
        if value is None:
            return None
        return BYPASS_MODES_REVERSE.get(value, "Heat Exchange")

    async def async_select_option(self, option: str) -> None:
        """Change the bypass mode."""
        if not await self._require_power_on():
            _LOGGER.error("Cannot change bypass mode when ERV is off")
            return

        mode_value = BYPASS_MODES.get(option)
        if mode_value is None:
            _LOGGER.error("Unknown bypass mode: %s", option)
            return

        if await self._client.async_write_register(
            REG_BYPASS_FUNCTION, mode_value
        ):
            _LOGGER.info("Bypass mode changed to %s", option)
        else:
            _LOGGER.error("Failed to set bypass mode to %s", option)

        await self.coordinator.async_request_refresh()


class DeltaERVInternalCirculationSelect(DeltaERVSelectBase):
    """Representation of Delta ERV Internal Circulation Mode selector."""

    _attr_name = "Internal Circulation Mode"
    _attr_options = list(INTERNAL_CIRC_MODES.keys())

    def __init__(self, coordinator, name):
        """Initialize the internal circulation selector."""
        super().__init__(coordinator, name)
        self._attr_unique_id = f"{name}_internal_circulation_mode"

    @property
    def current_option(self):
        """Return the current internal circulation mode."""
        value = self.coordinator.data.get(REG_INTERNAL_CIRCULATION)
        if value is None:
            return None
        return INTERNAL_CIRC_MODES_REVERSE.get(value, "Heat Exchange")

    async def async_select_option(self, option: str) -> None:
        """Change the internal circulation mode."""
        if not await self._require_power_on():
            _LOGGER.error(
                "Cannot change internal circulation mode when ERV is off"
            )
            return

        mode_value = INTERNAL_CIRC_MODES.get(option)
        if mode_value is None:
            _LOGGER.error("Unknown internal circulation mode: %s", option)
            return

        if await self._client.async_write_register(
            REG_INTERNAL_CIRCULATION, mode_value
        ):
            _LOGGER.info("Internal circulation mode changed to %s", option)
        else:
            _LOGGER.error(
                "Failed to set internal circulation mode to %s", option
            )

        await self.coordinator.async_request_refresh()
