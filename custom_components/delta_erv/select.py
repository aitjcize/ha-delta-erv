"""Select platform for Delta ERV integration."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
    config = data["config"]
    client = data["client"]

    name = config[CONF_NAME]

    async_add_entities(
        [
            DeltaERVBypassSelect(hass, name, client),
            DeltaERVInternalCirculationSelect(hass, name, client),
        ],
        True,
    )


class DeltaERVBypassSelect(SelectEntity):
    """Representation of Delta ERV Bypass Mode selector."""

    _attr_has_entity_name = True
    _attr_name = "Bypass Mode"
    _attr_options = list(BYPASS_MODES.keys())

    def __init__(self, hass, name, client):
        """Initialize the bypass selector."""
        self.hass = hass
        self._client = client
        self._attr_unique_id = f"{name}_bypass_mode"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{name}_fan")},
            "name": name,
            "manufacturer": "Delta",
            "model": "ERV",
        }
        self._attr_current_option = None

    async def async_update(self) -> None:
        """Update the current bypass mode."""
        result = await self._client.async_read_register(REG_BYPASS_FUNCTION)
        if result:
            mode_value = result.registers[0]
            self._attr_current_option = BYPASS_MODES_REVERSE.get(
                mode_value, "Heat Exchange"
            )
        else:
            _LOGGER.error("Failed to read bypass mode")

    async def async_select_option(self, option: str) -> None:
        """Change the bypass mode."""
        # Check if machine is on
        power_result = await self._client.async_read_register(REG_POWER)
        if not power_result or power_result.registers[0] != POWER_ON:
            _LOGGER.error("Cannot change bypass mode when ERV is off")
            return

        mode_value = BYPASS_MODES.get(option)
        if mode_value is not None:
            success = await self._client.async_write_register(
                REG_BYPASS_FUNCTION, mode_value
            )
            if success:
                self._attr_current_option = option
                _LOGGER.info(f"Bypass mode changed to {option}")
            else:
                _LOGGER.error(f"Failed to set bypass mode to {option}")
        else:
            _LOGGER.error(f"Unknown bypass mode: {option}")


class DeltaERVInternalCirculationSelect(SelectEntity):
    """Representation of Delta ERV Internal Circulation Mode selector."""

    _attr_has_entity_name = True
    _attr_name = "Internal Circulation Mode"
    _attr_options = list(INTERNAL_CIRC_MODES.keys())

    def __init__(self, hass, name, client):
        """Initialize the internal circulation selector."""
        self.hass = hass
        self._client = client
        self._attr_unique_id = f"{name}_internal_circulation_mode"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{name}_fan")},
            "name": name,
            "manufacturer": "Delta",
            "model": "ERV",
        }
        self._attr_current_option = None

    async def async_update(self) -> None:
        """Update the current internal circulation mode."""
        result = await self._client.async_read_register(
            REG_INTERNAL_CIRCULATION
        )
        if result:
            mode_value = result.registers[0]
            self._attr_current_option = INTERNAL_CIRC_MODES_REVERSE.get(
                mode_value, "Heat Exchange"
            )
        else:
            _LOGGER.error("Failed to read internal circulation mode")

    async def async_select_option(self, option: str) -> None:
        """Change the internal circulation mode."""
        # Check if machine is on
        power_result = await self._client.async_read_register(REG_POWER)
        if not power_result or power_result.registers[0] != POWER_ON:
            _LOGGER.error(
                "Cannot change internal circulation mode when ERV is off"
            )
            return

        mode_value = INTERNAL_CIRC_MODES.get(option)
        if mode_value is not None:
            success = await self._client.async_write_register(
                REG_INTERNAL_CIRCULATION, mode_value
            )
            if success:
                self._attr_current_option = option
                _LOGGER.info(f"Internal circulation mode changed to {option}")
            else:
                _LOGGER.error(
                    f"Failed to set internal circulation mode to {option}"
                )
        else:
            _LOGGER.error(f"Unknown internal circulation mode: {option}")
