"""Fan platform for Delta ERV integration."""

import logging
from typing import Any, Optional

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import (
    DOMAIN,
    FAN_SPEED_1,
    FAN_SPEED_2,
    FAN_SPEED_3,
    POWER_OFF,
    POWER_ON,
    REG_FAN_SPEED,
    REG_POWER,
)

_LOGGER = logging.getLogger(__name__)

# Fan speed mapping - ordered from lowest to highest
ORDERED_NAMED_FAN_SPEEDS = ["Low", "Medium", "High"]

# Mapping between register values and speed names
SPEED_TO_REG = {
    "Low": FAN_SPEED_1,  # 0x04 (風量 1)
    "Medium": FAN_SPEED_2,  # 0x05 (風量 2)
    "High": FAN_SPEED_3,  # 0x06 (風量 3)
}

REG_TO_SPEED = {v: k for k, v in SPEED_TO_REG.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Delta ERV fan platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    config = data["config"]
    client = data["client"]

    name = config[CONF_NAME]

    async_add_entities(
        [DeltaERVFan(hass, name, client)],
        True,
    )


class DeltaERVFan(FanEntity):
    """Representation of a Delta ERV fan device."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_speed_count = len(ORDERED_NAMED_FAN_SPEEDS)

    def __init__(self, hass, name, client):
        """Initialize the fan device."""
        self.hass = hass
        self._client = client
        self._attr_unique_id = f"{name}_fan"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._attr_unique_id)},
            "name": name,
            "manufacturer": "Delta",
            "model": "ERV",
        }

        # Initialize state variables
        self._attr_is_on = False
        self._attr_percentage = None
        self._current_speed_name = None

    @property
    def percentage(self) -> Optional[int]:
        """Return the current speed percentage."""
        return self._attr_percentage

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(ORDERED_NAMED_FAN_SPEEDS)

    async def async_update(self) -> None:
        """Update the state of the fan device."""
        # Get power status
        power_result = await self._client.async_read_register(REG_POWER)
        if power_result:
            power_status = power_result.registers[0]
            self._attr_is_on = power_status == POWER_ON
        else:
            _LOGGER.error("Failed to read power status")
            return

        # Get the fan speed setting
        fan_speed_result = await self._client.async_read_register(REG_FAN_SPEED)

        if fan_speed_result:
            fan_speed_reg = fan_speed_result.registers[0]
            speed_name = REG_TO_SPEED.get(fan_speed_reg, "Medium")
            self._current_speed_name = speed_name

            if self._attr_is_on:
                # Convert named speed to percentage
                self._attr_percentage = ordered_list_item_to_percentage(
                    ORDERED_NAMED_FAN_SPEEDS, speed_name
                )
            else:
                self._attr_percentage = 0
        else:
            _LOGGER.error("Failed to read fan speed")

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if percentage == 0:
            await self.async_turn_off()
            return

        # Convert percentage to named speed
        speed_name = percentage_to_ordered_list_item(
            ORDERED_NAMED_FAN_SPEEDS, percentage
        )

        # Get register value for the speed
        reg_value = SPEED_TO_REG.get(speed_name, FAN_SPEED_2)

        # Set fan speed
        success = await self._client.async_write_register(
            REG_FAN_SPEED, reg_value
        )

        if success:
            self._attr_percentage = percentage
            self._current_speed_name = speed_name

            # If fan was off, turn it on
            if not self._attr_is_on:
                await self.async_turn_on()
        else:
            _LOGGER.error("Failed to set fan speed to %s", speed_name)

    async def async_turn_on(
        self,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        # Set power on
        success = await self._client.async_write_register(REG_POWER, POWER_ON)

        if success:
            self._attr_is_on = True

            # If percentage is specified, set it
            if percentage is not None:
                await self.async_set_percentage(percentage)
            elif self._attr_percentage is None or self._attr_percentage == 0:
                # Set to low speed if no previous speed
                await self.async_set_percentage(
                    ordered_list_item_to_percentage(
                        ORDERED_NAMED_FAN_SPEEDS, "Low"
                    )
                )
        else:
            _LOGGER.error("Failed to turn on ERV fan")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        success = await self._client.async_write_register(REG_POWER, POWER_OFF)

        if success:
            self._attr_is_on = False
            self._attr_percentage = 0
        else:
            _LOGGER.error("Failed to turn off ERV fan")
