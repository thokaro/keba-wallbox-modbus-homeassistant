"""Sensor platform for KEBA Wallbox Modbus."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CABLE_STATE_MAP,
    CHARGING_STATE_MAP,
    DOMAIN,
    KebaProfile,
    KEY_ACTIVE_POWER,
    KEY_CABLE_STATE,
    KEY_CHARGING_STATE,
    KEY_CURRENT_L1,
    KEY_CURRENT_L2,
    KEY_CURRENT_L3,
    KEY_ERROR_CODE,
    KEY_FAST_CHARGING_STATE,
    KEY_FIRMWARE_VERSION,
    KEY_HARDWARE_REVISION_DEVICE,
    KEY_HARDWARE_REVISION_MS10,
    KEY_MAX_CHARGING_CURRENT,
    KEY_MAX_SUPPORTED_CURRENT,
    KEY_POWER_FACTOR,
    KEY_PRODUCT,
    KEY_SERIAL_NUMBER,
    KEY_SESSION_ENERGY,
    KEY_TOTAL_ENERGY,
    KEY_VOLTAGE_L1,
    KEY_VOLTAGE_L2,
    KEY_VOLTAGE_L3,
    FAST_CHARGING_STATE_MAP,
    describe_product,
    format_firmware_version,
    format_serial_number,
    scale_milliamps,
    scale_milliwatts,
    scale_energy_to_kwh,
    scale_tenth_percent,
    scale_volts,
)
from .coordinator import KebaDataUpdateCoordinator
from .entity import KebaEntity


def _enum_value(
    data: Mapping[str, Any], key: str, mapping: Mapping[int, str]
) -> Optional[str]:
    raw = data.get(key)
    if raw is None:
        return None
    return mapping.get(raw, f"unknown ({raw})")


def _error_attributes(data: Mapping[str, Any]) -> Optional[Dict[str, str]]:
    raw = data.get(KEY_ERROR_CODE)
    if raw is None:
        return None
    return {"hex": f"0x{raw:08X}"}


def _product_attributes(
    coordinator: KebaDataUpdateCoordinator,
    data: Mapping[str, Any],
) -> Optional[Mapping[str, Any]]:
    raw = data.get(KEY_PRODUCT)
    if raw is None:
        return None
    return describe_product(raw, coordinator.model_key)


@dataclass(frozen=True)
class KebaSensorDescription(SensorEntityDescription):
    """Describe a KEBA sensor entity."""

    value_fn: Callable[[KebaDataUpdateCoordinator, Mapping[str, Any]], Any] = field(
        default=lambda _, __: None
    )
    attributes_fn: Optional[
        Callable[
            [KebaDataUpdateCoordinator, Mapping[str, Any]],
            Optional[Mapping[str, Any]],
        ]
    ] = None
    options: Optional[tuple[str, ...]] = None
    required_key: Optional[str] = None


SENSOR_DESCRIPTIONS: tuple[KebaSensorDescription, ...] = (
    KebaSensorDescription(
        key=KEY_CHARGING_STATE,
        name="Charging state",
        icon="mdi:ev-station",
        device_class=SensorDeviceClass.ENUM,
        options=tuple(CHARGING_STATE_MAP.values()),
        value_fn=lambda _, data: _enum_value(data, KEY_CHARGING_STATE, CHARGING_STATE_MAP),
    ),
    KebaSensorDescription(
        key=KEY_CABLE_STATE,
        name="Cable state",
        icon="mdi:power-plug",
        device_class=SensorDeviceClass.ENUM,
        options=tuple(CABLE_STATE_MAP.values()),
        value_fn=lambda _, data: _enum_value(data, KEY_CABLE_STATE, CABLE_STATE_MAP),
    ),
    KebaSensorDescription(
        key=KEY_ERROR_CODE,
        name="Error code",
        icon="mdi:alert-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda _, data: data.get(KEY_ERROR_CODE),
        attributes_fn=lambda _, data: _error_attributes(data),
    ),
    KebaSensorDescription(
        key=KEY_CURRENT_L1,
        name="Phase 1 current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda _, data: scale_milliamps(data.get(KEY_CURRENT_L1)),
    ),
    KebaSensorDescription(
        key=KEY_CURRENT_L2,
        name="Phase 2 current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda _, data: scale_milliamps(data.get(KEY_CURRENT_L2)),
    ),
    KebaSensorDescription(
        key=KEY_CURRENT_L3,
        name="Phase 3 current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda _, data: scale_milliamps(data.get(KEY_CURRENT_L3)),
    ),
    KebaSensorDescription(
        key=KEY_ACTIVE_POWER,
        name="Active power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda _, data: scale_milliwatts(data.get(KEY_ACTIVE_POWER)),
    ),
    KebaSensorDescription(
        key=KEY_TOTAL_ENERGY,
        name="Total energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        value_fn=lambda coordinator, data: scale_energy_to_kwh(
            data.get(KEY_TOTAL_ENERGY),
            model_key=coordinator.model_key,
            firmware_raw=coordinator.firmware_version_raw,
        ),
    ),
    KebaSensorDescription(
        key=KEY_SESSION_ENERGY,
        name="Session energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        value_fn=lambda coordinator, data: scale_energy_to_kwh(
            data.get(KEY_SESSION_ENERGY),
            model_key=coordinator.model_key,
            firmware_raw=coordinator.firmware_version_raw,
        ),
    ),
    KebaSensorDescription(
        key=KEY_VOLTAGE_L1,
        name="Phase 1 voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda _, data: scale_volts(data.get(KEY_VOLTAGE_L1)),
    ),
    KebaSensorDescription(
        key=KEY_VOLTAGE_L2,
        name="Phase 2 voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda _, data: scale_volts(data.get(KEY_VOLTAGE_L2)),
    ),
    KebaSensorDescription(
        key=KEY_VOLTAGE_L3,
        name="Phase 3 voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda _, data: scale_volts(data.get(KEY_VOLTAGE_L3)),
    ),
    KebaSensorDescription(
        key=KEY_POWER_FACTOR,
        name="Power factor",
        icon="mdi:sine-wave",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda _, data: scale_tenth_percent(data.get(KEY_POWER_FACTOR)),
    ),
    KebaSensorDescription(
        key=KEY_MAX_CHARGING_CURRENT,
        name="Charging current limit",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        value_fn=lambda _, data: scale_milliamps(data.get(KEY_MAX_CHARGING_CURRENT)),
    ),
    KebaSensorDescription(
        key=KEY_MAX_SUPPORTED_CURRENT,
        name="Maximum supported current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        value_fn=lambda _, data: scale_milliamps(data.get(KEY_MAX_SUPPORTED_CURRENT)),
    ),
    KebaSensorDescription(
        key=KEY_FAST_CHARGING_STATE,
        name="Fast charging state",
        icon="mdi:flash",
        device_class=SensorDeviceClass.ENUM,
        options=tuple(FAST_CHARGING_STATE_MAP.values()),
        required_key=KEY_FAST_CHARGING_STATE,
        value_fn=lambda _, data: _enum_value(
            data, KEY_FAST_CHARGING_STATE, FAST_CHARGING_STATE_MAP
        ),
    ),
    KebaSensorDescription(
        key=KEY_SERIAL_NUMBER,
        name="Serial number",
        icon="mdi:identifier",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda _, data: format_serial_number(data.get(KEY_SERIAL_NUMBER)),
        attributes_fn=_product_attributes,
    ),
    KebaSensorDescription(
        key=KEY_FIRMWARE_VERSION,
        name="Firmware version",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator, data: format_firmware_version(
            data.get(KEY_FIRMWARE_VERSION),
            model_key=coordinator.model_key,
        ),
    ),
    KebaSensorDescription(
        key=KEY_HARDWARE_REVISION_DEVICE,
        name="Hardware revision device",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        required_key=KEY_HARDWARE_REVISION_DEVICE,
        value_fn=lambda _, data: data.get(KEY_HARDWARE_REVISION_DEVICE),
    ),
    KebaSensorDescription(
        key=KEY_HARDWARE_REVISION_MS10,
        name="Hardware revision MS10",
        icon="mdi:circuit-board",
        entity_category=EntityCategory.DIAGNOSTIC,
        required_key=KEY_HARDWARE_REVISION_MS10,
        value_fn=lambda _, data: data.get(KEY_HARDWARE_REVISION_MS10),
    ),
)


def _is_supported_sensor(
    description: KebaSensorDescription,
    profile: KebaProfile,
) -> bool:
    """Return whether a sensor is supported by the active wallbox profile."""
    return description.required_key is None or profile.supports_key(description.required_key)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEBA wallbox sensors."""
    coordinator: KebaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        KebaSensorEntity(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
        if _is_supported_sensor(description, coordinator.profile)
    )


class KebaSensorEntity(KebaEntity, SensorEntity):
    """Representation of a KEBA sensor."""

    entity_description: KebaSensorDescription

    def __init__(
        self,
        coordinator: KebaDataUpdateCoordinator,
        description: KebaSensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        if description.options is not None:
            self._attr_options = list(description.options)

    @property
    def native_value(self) -> Any:
        """Return the current sensor value."""
        return self.entity_description.value_fn(
            self.coordinator,
            self.coordinator.data or {},
        )

    @property
    def extra_state_attributes(self) -> Optional[Mapping[str, Any]]:
        """Return extra attributes for the sensor."""
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(
            self.coordinator,
            self.coordinator.data or {},
        )
