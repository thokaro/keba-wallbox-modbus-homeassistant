"""Central description metadata for KEBA sensors."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.helpers.entity import EntityCategory

from .decoding import (
    describe_product,
    format_firmware_version,
    format_serial_number,
    scale_energy_to_kwh,
    scale_milliamps,
    scale_milliwatts,
    scale_tenth_percent,
    scale_volts,
)
from .profiles import KebaProfile
from .registers import (
    CABLE_STATE_MAP,
    CHARGER_STATUS_MAP,
    CHARGING_STATE_MAP,
    FAST_CHARGING_STATE_MAP,
    KEY_ACTIVE_POWER,
    KEY_CABLE_STATE,
    KEY_CHARGING_STATE,
    KEY_CHARGER_STATUS,
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
)
from .coordinator import KebaDataUpdateCoordinator


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


def _charger_status(data: Mapping[str, Any]) -> Optional[str]:
    """Return the EVSE A/B/C status from charging and cable state."""
    charging_state = data.get(KEY_CHARGING_STATE)
    if charging_state == 3:
        return "C"

    cable_state = data.get(KEY_CABLE_STATE)
    if cable_state is not None:
        return "B" if cable_state & (1 << 2) else "A"

    return CHARGER_STATUS_MAP.get(charging_state)


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


def _enum_sensor(
    *,
    key: str,
    name: str,
    icon: str,
    mapping: Mapping[int, str],
    required_key: Optional[str] = None,
) -> KebaSensorDescription:
    """Build an enum sensor description from a simple mapping."""
    return KebaSensorDescription(
        key=key,
        name=name,
        icon=icon,
        device_class=SensorDeviceClass.ENUM,
        options=tuple(mapping.values()),
        required_key=required_key,
        value_fn=lambda _, data: _enum_value(data, key, mapping),
    )


def _scaled_sensor(
    *,
    key: str,
    name: str,
    device_class: SensorDeviceClass,
    native_unit: str,
    scaler: Callable[[Optional[int]], Optional[float]],
    state_class: Optional[SensorStateClass] = SensorStateClass.MEASUREMENT,
    precision: Optional[int] = None,
) -> KebaSensorDescription:
    """Build a simple scaled numeric sensor description."""
    return KebaSensorDescription(
        key=key,
        name=name,
        device_class=device_class,
        native_unit_of_measurement=native_unit,
        state_class=state_class,
        suggested_display_precision=precision,
        value_fn=lambda _, data: scaler(data.get(key)),
    )


SENSOR_DESCRIPTIONS: tuple[KebaSensorDescription, ...] = (
    _enum_sensor(
        key=KEY_CHARGING_STATE,
        name="Charging state",
        icon="mdi:ev-station",
        mapping=CHARGING_STATE_MAP,
    ),
    KebaSensorDescription(
        key=KEY_CHARGER_STATUS,
        name="Charger status",
        icon="mdi:ev-plug-type2",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=tuple(dict.fromkeys(CHARGER_STATUS_MAP.values())),
        value_fn=lambda _, data: _charger_status(data),
    ),
    _enum_sensor(
        key=KEY_CABLE_STATE,
        name="Cable state",
        icon="mdi:power-plug",
        mapping=CABLE_STATE_MAP,
    ),
    KebaSensorDescription(
        key=KEY_ERROR_CODE,
        name="Error code",
        icon="mdi:alert-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda _, data: data.get(KEY_ERROR_CODE),
        attributes_fn=lambda _, data: _error_attributes(data),
    ),
    _scaled_sensor(
        key=KEY_CURRENT_L1,
        name="Phase 1 current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit=UnitOfElectricCurrent.AMPERE,
        scaler=scale_milliamps,
        precision=2,
    ),
    _scaled_sensor(
        key=KEY_CURRENT_L2,
        name="Phase 2 current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit=UnitOfElectricCurrent.AMPERE,
        scaler=scale_milliamps,
        precision=2,
    ),
    _scaled_sensor(
        key=KEY_CURRENT_L3,
        name="Phase 3 current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit=UnitOfElectricCurrent.AMPERE,
        scaler=scale_milliamps,
        precision=2,
    ),
    _scaled_sensor(
        key=KEY_ACTIVE_POWER,
        name="Active power",
        device_class=SensorDeviceClass.POWER,
        native_unit=UnitOfPower.WATT,
        scaler=scale_milliwatts,
        precision=0,
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
    _scaled_sensor(
        key=KEY_VOLTAGE_L1,
        name="Phase 1 voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit=UnitOfElectricPotential.VOLT,
        scaler=scale_volts,
        precision=0,
    ),
    _scaled_sensor(
        key=KEY_VOLTAGE_L2,
        name="Phase 2 voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit=UnitOfElectricPotential.VOLT,
        scaler=scale_volts,
        precision=0,
    ),
    _scaled_sensor(
        key=KEY_VOLTAGE_L3,
        name="Phase 3 voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit=UnitOfElectricPotential.VOLT,
        scaler=scale_volts,
        precision=0,
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
    _scaled_sensor(
        key=KEY_MAX_CHARGING_CURRENT,
        name="Charging current limit",
        device_class=SensorDeviceClass.CURRENT,
        native_unit=UnitOfElectricCurrent.AMPERE,
        scaler=scale_milliamps,
        state_class=None,
        precision=2,
    ),
    _scaled_sensor(
        key=KEY_MAX_SUPPORTED_CURRENT,
        name="Maximum supported current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit=UnitOfElectricCurrent.AMPERE,
        scaler=scale_milliamps,
        state_class=None,
        precision=2,
    ),
    _enum_sensor(
        key=KEY_FAST_CHARGING_STATE,
        name="Fast charging state",
        icon="mdi:flash",
        mapping=FAST_CHARGING_STATE_MAP,
        required_key=KEY_FAST_CHARGING_STATE,
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


def is_supported_sensor(
    description: KebaSensorDescription,
    profile: KebaProfile,
) -> bool:
    """Return whether a sensor is supported by the active wallbox profile."""
    return description.required_key is None or profile.supports_key(description.required_key)


__all__ = [
    "KebaSensorDescription",
    "SENSOR_DESCRIPTIONS",
    "is_supported_sensor",
]
