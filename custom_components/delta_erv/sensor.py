"""Sensor platform for Delta ERV integration."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
from .coordinator import DeltaERVDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Delta ERV sensor platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: DeltaERVDataUpdateCoordinator = data["coordinator"]
    name = data["config"][CONF_NAME]

    sensors = [
        DeltaERVTemperatureSensor(
            coordinator,
            name,
            "outdoor_temp",
            "Outdoor Temperature",
            REG_OUTDOOR_TEMP,
        ),
        DeltaERVTemperatureSensor(
            coordinator,
            name,
            "indoor_temp",
            "Indoor Return Temperature",
            REG_INDOOR_RETURN_TEMP,
        ),
        DeltaERVSpeedSensor(
            coordinator,
            name,
            "supply_fan_speed",
            "Supply Fan Speed",
            REG_SUPPLY_FAN_SPEED,
        ),
        DeltaERVSpeedSensor(
            coordinator,
            name,
            "exhaust_fan_speed",
            "Exhaust Fan Speed",
            REG_EXHAUST_FAN_SPEED,
        ),
        DeltaERVStatusSensor(
            coordinator,
            name,
            "abnormal_status",
            "Abnormal Status",
            REG_ABNORMAL_STATUS,
        ),
        DeltaERVStatusSensor(
            coordinator,
            name,
            "system_status",
            "System Status",
            REG_SYSTEM_STATUS,
        ),
    ]

    async_add_entities(sensors)


class DeltaERVBaseSensor(
    CoordinatorEntity[DeltaERVDataUpdateCoordinator], SensorEntity
):
    """Base class for Delta ERV sensors.

    In addition to device-level availability (from CoordinatorEntity), a sensor
    reports "unavailable" when its own register could not be read — e.g. a
    register that is not supported on this ERV model.
    """

    _attr_has_entity_name = True

    def __init__(
        self, coordinator, device_name, sensor_id, sensor_name, register
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._register = register
        self._attr_unique_id = f"{device_name}_{sensor_id}"
        self._attr_name = sensor_name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{device_name}_fan")},
            "name": device_name,
            "manufacturer": "Delta",
            "model": "ERV",
        }

    @property
    def available(self) -> bool:
        """Available only when the device is up AND this register was read."""
        return (
            super().available
            and self.coordinator.data.get(self._register) is not None
        )


class DeltaERVTemperatureSensor(DeltaERVBaseSensor):
    """Temperature sensor for Delta ERV."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self):
        """Temperature is a signed 16-bit integer in °C."""
        raw_value = self.coordinator.data.get(self._register)
        if raw_value is None:
            return None
        # Convert from unsigned to signed if necessary
        if raw_value > 32767:
            raw_value -= 65536
        return float(raw_value)


class DeltaERVSpeedSensor(DeltaERVBaseSensor):
    """Fan speed sensor for Delta ERV."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "rpm"
    _attr_icon = "mdi:fan"

    @property
    def native_value(self):
        """Return the fan speed in RPM."""
        return self.coordinator.data.get(self._register)


class DeltaERVStatusSensor(DeltaERVBaseSensor):
    """Status sensor for Delta ERV."""

    _attr_icon = "mdi:information"

    @property
    def native_value(self):
        """Derive a human-readable status from the status register bits."""
        status_value = self.coordinator.data.get(self._register)
        if status_value is None:
            return None

        if self._register == REG_ABNORMAL_STATUS:
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
            return "Error" if has_error else "Normal"

        if self._register == REG_SYSTEM_STATUS:
            return "Running" if bool(status_value & 0x0001) else "Stopped"

        return f"0x{status_value:04X}"

    @property
    def extra_state_attributes(self):
        """Return the decoded status bits."""
        status_value = self.coordinator.data.get(self._register)
        if status_value is None:
            return {}

        if self._register == REG_ABNORMAL_STATUS:
            return {
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

        if self._register == REG_SYSTEM_STATUS:
            return {
                "running": bool(status_value & 0x0001),
                "bypass_active": bool(status_value & 0x0010),
                "internal_circulation": bool(status_value & 0x0020),
                "low_temp_protection": bool(status_value & 0x0040),
                "raw_value": f"0x{status_value:04X}",
            }

        return {}
