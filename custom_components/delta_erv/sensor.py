"""Sensor platform for Delta ERV integration."""

import logging
from typing import Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    REG_ABNORMAL_STATUS,
    REG_EXHAUST_FAN_SPEED,
    REG_INDOOR_RETURN_TEMP,
    REG_OUTDOOR_TEMP,
    REG_SUPPLY_FAN_SPEED,
    REG_SYSTEM_STATUS,
    STATUS_EEPROM_ERROR,
    STATUS_EXHAUST_FAN_ERROR,
    STATUS_INDOOR_TEMP_ERROR,
    STATUS_OUTDOOR_TEMP_ERROR,
    STATUS_SUPPLY_FAN_ERROR,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Delta ERV sensor platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    config = data["config"]
    client = data["client"]

    name = config[CONF_NAME]

    sensors = [
        DeltaERVTemperatureSensor(
            hass,
            name,
            client,
            "outdoor_temp",
            "Outdoor Temperature",
            REG_OUTDOOR_TEMP,
        ),
        DeltaERVTemperatureSensor(
            hass,
            name,
            client,
            "indoor_temp",
            "Indoor Return Temperature",
            REG_INDOOR_RETURN_TEMP,
        ),
        DeltaERVSpeedSensor(
            hass,
            name,
            client,
            "supply_fan_speed",
            "Supply Fan Speed",
            REG_SUPPLY_FAN_SPEED,
        ),
        DeltaERVSpeedSensor(
            hass,
            name,
            client,
            "exhaust_fan_speed",
            "Exhaust Fan Speed",
            REG_EXHAUST_FAN_SPEED,
        ),
        DeltaERVStatusSensor(
            hass,
            name,
            client,
            "abnormal_status",
            "Abnormal Status",
            REG_ABNORMAL_STATUS,
        ),
        DeltaERVStatusSensor(
            hass,
            name,
            client,
            "system_status",
            "System Status",
            REG_SYSTEM_STATUS,
        ),
    ]

    async_add_entities(sensors, True)


class DeltaERVBaseSensor(SensorEntity):
    """Base class for Delta ERV sensors."""

    _attr_has_entity_name = True

    def __init__(
        self, hass, device_name, client, sensor_id, sensor_name, register
    ):
        """Initialize the sensor."""
        self.hass = hass
        self._client = client
        self._register = register
        self._attr_unique_id = f"{device_name}_{sensor_id}"
        self._attr_name = sensor_name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{device_name}_fan")},
            "name": device_name,
            "manufacturer": "Delta",
            "model": "ERV",
        }


class DeltaERVTemperatureSensor(DeltaERVBaseSensor):
    """Temperature sensor for Delta ERV."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    async def async_update(self) -> None:
        """Update the sensor state."""
        result = await self._client.async_read_register(self._register)

        if result:
            # Temperature is stored as signed 16-bit integer in °C
            raw_value = result.registers[0]

            # Convert from unsigned to signed if necessary
            if raw_value > 32767:
                temperature = raw_value - 65536
            else:
                temperature = raw_value

            self._attr_native_value = float(temperature)
            self._attr_available = True
        else:
            _LOGGER.debug(
                "Failed to read temperature from register 0x%04X (may not be available on this model)",
                self._register,
            )
            self._attr_available = False
            self._attr_native_value = None


class DeltaERVSpeedSensor(DeltaERVBaseSensor):
    """Fan speed sensor for Delta ERV."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "rpm"
    _attr_icon = "mdi:fan"

    async def async_update(self) -> None:
        """Update the sensor state."""
        result = await self._client.async_read_register(self._register)

        if result:
            # Fan speed is in RPM
            self._attr_native_value = result.registers[0]
            self._attr_available = True
        else:
            _LOGGER.debug(
                "Failed to read fan speed from register 0x%04X (may not be available on this model)",
                self._register,
            )
            self._attr_available = False
            self._attr_native_value = None


class DeltaERVStatusSensor(DeltaERVBaseSensor):
    """Status sensor for Delta ERV."""

    _attr_icon = "mdi:information"

    async def async_update(self) -> None:
        """Update the sensor state."""
        result = await self._client.async_read_register(self._register)
        if result:
            status_value = result.registers[0]

            if self._register == REG_ABNORMAL_STATUS:
                # Parse abnormal status bits
                has_error = bool(
                    status_value
                    & (
                        STATUS_EEPROM_ERROR
                        | STATUS_INDOOR_TEMP_ERROR
                        | STATUS_OUTDOOR_TEMP_ERROR
                        | STATUS_EXHAUST_FAN_ERROR
                        | STATUS_SUPPLY_FAN_ERROR
                    )
                )

                self._attr_native_value = "Error" if has_error else "Normal"
                self._attr_extra_state_attributes = {
                    "eeprom_error": bool(status_value & STATUS_EEPROM_ERROR),
                    "indoor_temp_error": bool(
                        status_value & STATUS_INDOOR_TEMP_ERROR
                    ),
                    "outdoor_temp_error": bool(
                        status_value & STATUS_OUTDOOR_TEMP_ERROR
                    ),
                    "exhaust_fan_error": bool(
                        status_value & STATUS_EXHAUST_FAN_ERROR
                    ),
                    "supply_fan_error": bool(
                        status_value & STATUS_SUPPLY_FAN_ERROR
                    ),
                    "raw_value": f"0x{status_value:04X}",
                }

            elif self._register == REG_SYSTEM_STATUS:
                # Parse system status (register 0x13)
                # Main status shows if running
                is_running = bool(status_value & 0x0001)
                self._attr_native_value = "Running" if is_running else "Stopped"

                self._attr_extra_state_attributes = {
                    "running": is_running,
                    "bypass_active": bool(status_value & 0x0010),
                    "internal_circulation": bool(status_value & 0x0020),
                    "low_temp_protection": bool(status_value & 0x0040),
                    "raw_value": f"0x{status_value:04X}",
                }
            else:
                # For other status registers, show raw hex value
                self._attr_native_value = f"0x{status_value:04X}"
                self._attr_extra_state_attributes = {}

            self._attr_available = True
        else:
            _LOGGER.debug(
                "Failed to read status from register 0x%04X (may not be available on this model)",
                self._register,
            )
            self._attr_available = False
            self._attr_native_value = None
