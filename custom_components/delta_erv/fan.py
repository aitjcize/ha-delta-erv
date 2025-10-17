"""Fan platform for Delta ERV integration."""

import logging
from typing import Any, Optional

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    EXHAUST_MAX_REGISTER_PCT,
    EXHAUST_MIN_REGISTER_PCT,
    FAN_SPEED_CUSTOM_1,
    POWER_OFF,
    POWER_ON,
    REG_EXHAUST_AIR_1_PCT,
    REG_FAN_SPEED,
    REG_POWER,
    REG_SUPPLY_AIR_1_PCT,
    SUPPLY_MAX_REGISTER_PCT,
    SUPPLY_MIN_REGISTER_PCT,
)

_LOGGER = logging.getLogger(__name__)

# We use only Custom 1 (0x01) and dynamically set the percentage
# This gives us full 0-100% granular control


def calculate_fan_percentages(user_percentage: int) -> tuple[int, int]:
    """Calculate supply and exhaust percentages to maintain positive pressure.

    Strategy:
    Map user's 0-100% to each fan's register range:
    - Exhaust: 0% → 0, 1-100% → 1-48% register
    - Supply: 0% → 0, 1-100% → 1-62% register

    The device has non-linear register mapping:
    - 0% register = fan off
    - 1% register = min RPM (400/380)
    - 48%/62% register = max RPM (1840/2300)

    Args:
        user_percentage: User's desired fan speed (0-100%)

    Returns:
        Tuple of (supply_pct, exhaust_pct)
    """
    if user_percentage == 0:
        return 0, 0

    # Map user 1-100% to register ranges
    # Exhaust: 1-100% user → 1-48% register
    exhaust_pct = int(
        EXHAUST_MIN_REGISTER_PCT
        + (user_percentage - 1)
        / 99.0
        * (EXHAUST_MAX_REGISTER_PCT - EXHAUST_MIN_REGISTER_PCT)
    )

    # Supply: 1-100% user → 1-62% register
    supply_pct = int(
        SUPPLY_MIN_REGISTER_PCT
        + (user_percentage - 1)
        / 99.0
        * (SUPPLY_MAX_REGISTER_PCT - SUPPLY_MIN_REGISTER_PCT)
    )

    # Clamp to valid ranges
    exhaust_pct = max(
        EXHAUST_MIN_REGISTER_PCT, min(EXHAUST_MAX_REGISTER_PCT, exhaust_pct)
    )
    supply_pct = max(
        SUPPLY_MIN_REGISTER_PCT, min(SUPPLY_MAX_REGISTER_PCT, supply_pct)
    )

    _LOGGER.debug(
        f"User {user_percentage}% -> Exhaust register: {exhaust_pct}%, "
        f"Supply register: {supply_pct}%"
    )

    return supply_pct, exhaust_pct


def calculate_user_percentage(supply_pct: int, exhaust_pct: int) -> int:
    """Reverse calculation: convert fan percentages back to user percentage.

    We use exhaust register value as reference to reverse the mapping.

    Args:
        supply_pct: Supply fan percentage from register (unused)
        exhaust_pct: Exhaust fan percentage from register

    Returns:
        User-facing percentage (0-100)
    """
    if exhaust_pct == 0:
        return 0

    # Reverse map: exhaust register 1-48% → user 1-100%
    user_pct = int(
        1
        + (exhaust_pct - EXHAUST_MIN_REGISTER_PCT)
        / (EXHAUST_MAX_REGISTER_PCT - EXHAUST_MIN_REGISTER_PCT)
        * 99
    )

    return max(0, min(100, user_pct))


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
    _attr_speed_count = 100  # Enable fine-grained control (1% increments)

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

    @property
    def percentage(self) -> Optional[int]:
        """Return the current speed percentage."""
        return self._attr_percentage

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

        # Read current percentages from both fans
        if self._attr_is_on:
            supply_pct_result = await self._client.async_read_register(
                REG_SUPPLY_AIR_1_PCT
            )
            exhaust_pct_result = await self._client.async_read_register(
                REG_EXHAUST_AIR_1_PCT
            )

            if supply_pct_result and exhaust_pct_result:
                supply_pct = supply_pct_result.registers[0]
                exhaust_pct = exhaust_pct_result.registers[0]
                # Convert back to user-facing percentage
                self._attr_percentage = calculate_user_percentage(
                    supply_pct, exhaust_pct
                )
            else:
                # Fallback to default if read fails
                if self._attr_percentage is None:
                    self._attr_percentage = 30  # Default to 30%
        else:
            self._attr_percentage = 0

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if percentage == 0:
            await self.async_turn_off()
            return

        # Ensure percentage is within valid range
        percentage = max(0, min(100, percentage))

        # Calculate appropriate supply and exhaust percentages for positive pressure
        supply_pct, exhaust_pct = calculate_fan_percentages(percentage)

        # Write calculated percentages to supply and exhaust registers (0x07 and 0x0A)
        success_supply = await self._client.async_write_register(
            REG_SUPPLY_AIR_1_PCT, supply_pct
        )
        success_exhaust = await self._client.async_write_register(
            REG_EXHAUST_AIR_1_PCT, exhaust_pct
        )

        if success_supply and success_exhaust:
            # Set fan speed to Custom 1 (0x01)
            success_speed = await self._client.async_write_register(
                REG_FAN_SPEED, FAN_SPEED_CUSTOM_1
            )

            if success_speed:
                self._attr_percentage = percentage
                _LOGGER.debug(f"Set fan speed to {percentage}%")

                # If fan was off, turn it on
                if not self._attr_is_on:
                    await self.async_turn_on(percentage=percentage)
            else:
                _LOGGER.error("Failed to set fan speed register to Custom 1")
        else:
            _LOGGER.error(f"Failed to set fan percentage to {percentage}%")

    async def async_turn_on(
        self,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        # If percentage is specified, set it first
        if percentage is not None:
            await self.async_set_percentage(percentage)
        elif self._attr_percentage is None or self._attr_percentage == 0:
            # Default to 30% (low speed) if no previous speed
            await self.async_set_percentage(30)

        # Set power on
        success = await self._client.async_write_register(REG_POWER, POWER_ON)

        if success:
            self._attr_is_on = True
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
