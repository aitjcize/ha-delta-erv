"""Fan platform for Delta ERV integration."""

import logging
from typing import Any, Optional

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
from .coordinator import DeltaERVDataUpdateCoordinator

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

    # Quantize to 5% steps (0, 5, 10, ..., 100) for consistency with speed_count
    quantized_pct = round(user_percentage / 5) * 5
    quantized_pct = max(0, min(100, quantized_pct))  # Ensure 0-100 range

    # Map quantized percentage to register ranges
    # Exhaust: 10-100% user → 1-48% register
    exhaust_pct = int(
        EXHAUST_MIN_REGISTER_PCT
        + (quantized_pct - 10)
        / 90.0
        * (EXHAUST_MAX_REGISTER_PCT - EXHAUST_MIN_REGISTER_PCT)
    )

    # Supply: 10-100% user → 1-63% register
    supply_pct = int(
        SUPPLY_MIN_REGISTER_PCT
        + (quantized_pct - 10)
        / 90.0
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
        f"User {user_percentage}% (quantized: {quantized_pct}%) -> "
        f"Exhaust register: {exhaust_pct}%, Supply register: {supply_pct}%"
    )

    return supply_pct, exhaust_pct


def calculate_user_percentage(supply_pct: int, exhaust_pct: int) -> int:
    """Reverse calculation: convert fan percentages back to user percentage.

    We use exhaust register value as reference to reverse the mapping.

    Args:
        supply_pct: Supply fan percentage from register (unused)
        exhaust_pct: Exhaust fan percentage from register

    Returns:
        User-facing percentage (0-100), quantized to 5% steps
    """
    if exhaust_pct == 0:
        return 0

    # Reverse map: exhaust register 1-48% → user 10-100%
    user_pct = int(
        10
        + (exhaust_pct - EXHAUST_MIN_REGISTER_PCT)
        / (EXHAUST_MAX_REGISTER_PCT - EXHAUST_MIN_REGISTER_PCT)
        * 90
    )

    # Quantize to 5% steps
    quantized = round(user_pct / 5) * 5
    return max(0, min(100, quantized))


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Delta ERV fan platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: DeltaERVDataUpdateCoordinator = data["coordinator"]
    name = data["config"][CONF_NAME]

    async_add_entities([DeltaERVFan(coordinator, name)])


class DeltaERVFan(CoordinatorEntity[DeltaERVDataUpdateCoordinator], FanEntity):
    """Representation of a Delta ERV fan device.

    Reads state from the shared coordinator; writes go straight to the Modbus
    client and then request a coordinator refresh. Availability is inherited
    from CoordinatorEntity.
    """

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_speed_count = 20  # 20 speed levels (5% increments); device registers resolve far finer

    def __init__(self, coordinator, name):
        """Initialize the fan device."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{name}_fan"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._attr_unique_id)},
            "name": name,
            "manufacturer": "Delta",
            "model": "ERV",
        }

    @property
    def _client(self):
        """Modbus client (writes bypass the coordinator's read cache)."""
        return self.coordinator.client

    @property
    def is_on(self) -> Optional[bool]:
        """Return whether the ERV is powered on."""
        power = self.coordinator.data.get(REG_POWER)
        if power is None:
            return None
        return power == POWER_ON

    @property
    def percentage(self) -> Optional[int]:
        """Return the current speed percentage."""
        if self.is_on is not True:
            return 0
        supply = self.coordinator.data.get(REG_SUPPLY_AIR_1_PCT)
        exhaust = self.coordinator.data.get(REG_EXHAUST_AIR_1_PCT)
        if supply is None or exhaust is None:
            return None
        return calculate_user_percentage(supply, exhaust)

    async def _write_speed(self, percentage: int) -> bool:
        """Write supply/exhaust/fan-speed registers for a user percentage."""
        supply_pct, exhaust_pct = calculate_fan_percentages(percentage)

        ok_supply = await self._client.async_write_register(
            REG_SUPPLY_AIR_1_PCT, supply_pct
        )
        ok_exhaust = await self._client.async_write_register(
            REG_EXHAUST_AIR_1_PCT, exhaust_pct
        )
        if not (ok_supply and ok_exhaust):
            _LOGGER.error("Failed to set fan percentage to %s%%", percentage)
            return False

        # Select the Custom 1 fan-speed profile that honors the % registers.
        if not await self._client.async_write_register(
            REG_FAN_SPEED, FAN_SPEED_CUSTOM_1
        ):
            _LOGGER.error("Failed to set fan speed register to Custom 1")
            return False

        _LOGGER.debug("Set fan speed to %s%%", percentage)
        return True

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if percentage == 0:
            await self.async_turn_off()
            return

        percentage = max(0, min(100, percentage))

        # Write the speed registers, then power on if the ERV is currently off.
        # (Done inline rather than calling async_turn_on to avoid re-entrancy.)
        if await self._write_speed(percentage) and self.is_on is not True:
            if not await self._client.async_write_register(REG_POWER, POWER_ON):
                _LOGGER.error("Failed to turn on ERV fan")

        await self.coordinator.async_request_refresh()

    async def async_turn_on(
        self,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        if not percentage:
            # No percentage requested: reuse the current one, defaulting to 30%.
            percentage = self.percentage or 30

        await self._write_speed(percentage)
        if not await self._client.async_write_register(REG_POWER, POWER_ON):
            _LOGGER.error("Failed to turn on ERV fan")

        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        if not await self._client.async_write_register(REG_POWER, POWER_OFF):
            _LOGGER.error("Failed to turn off ERV fan")

        await self.coordinator.async_request_refresh()
