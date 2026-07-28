"""DataUpdateCoordinator for the Delta ERV integration."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DOMAIN,
    REG_ABNORMAL_STATUS,
    REG_BYPASS_FUNCTION,
    REG_EXHAUST_AIR_1_PCT,
    REG_EXHAUST_FAN_SPEED,
    REG_INDOOR_RETURN_TEMP,
    REG_INTERNAL_CIRCULATION,
    REG_OUTDOOR_TEMP,
    REG_POWER,
    REG_SUPPLY_AIR_1_PCT,
    REG_SUPPLY_FAN_SPEED,
    REG_SYSTEM_STATUS,
)
from .modbus import DeltaERVModbusClient

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=5)

# Read first each cycle. If it fails the ERV is treated as offline and we raise
# UpdateFailed immediately (one connect attempt) instead of trying every
# register in turn.
_PROBE_REGISTER = REG_POWER

# Every register the entities need, polled once per cycle and shared via .data.
_REGISTERS = (
    REG_POWER,
    REG_SUPPLY_AIR_1_PCT,
    REG_EXHAUST_AIR_1_PCT,
    REG_SUPPLY_FAN_SPEED,
    REG_EXHAUST_FAN_SPEED,
    REG_BYPASS_FUNCTION,
    REG_ABNORMAL_STATUS,
    REG_OUTDOOR_TEMP,
    REG_INDOOR_RETURN_TEMP,
    REG_SYSTEM_STATUS,
    REG_INTERNAL_CIRCULATION,
)


class DeltaERVDataUpdateCoordinator(
    DataUpdateCoordinator[dict[int, int | None]]
):
    """Poll all Delta ERV registers once per cycle and share the result.

    ``data`` maps register address -> raw register value (or None if that one
    register failed / is not supported on this model while the device is
    otherwise reachable). When the ERV is unreachable the probe read returns
    None and we raise UpdateFailed, flipping every CoordinatorEntity to
    "unavailable".
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: DeltaERVModbusClient,
        name: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({name})",
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[int, int | None]:
        """Fetch all registers; raise UpdateFailed if the ERV is offline."""
        # Probe first so an offline unit fails fast (one connect attempt).
        probe = await self.client.async_read_register(_PROBE_REGISTER)
        if probe is None:
            raise UpdateFailed("Delta ERV unreachable (Modbus read failed)")

        data: dict[int, int | None] = {_PROBE_REGISTER: probe.registers[0]}
        for register in _REGISTERS:
            if register == _PROBE_REGISTER:
                continue
            result = await self.client.async_read_register(register)
            data[register] = result.registers[0] if result else None
        return data
