"""Decoding and scaling helpers for KEBA wallboxes."""

from __future__ import annotations

from typing import Mapping, Optional

from .const import MODEL_KEY_P30, MODEL_KEY_P40
from .profiles import model_name_for_key

P30_PRODUCT_CONNECTOR_MAP = {
    "0": "socket",
    "1": "cable",
}
P30_PRODUCT_CURRENT_MAP = {
    "1": "13 A",
    "2": "16 A",
    "3": "20 A",
    "4": "32 A",
}
P30_PRODUCT_SERIES_MAP = {
    "0": "x-series",
    "1": "c-series",
}
P30_PRODUCT_METERING_MAP = {
    "1": "standard meter",
    "2": "MID meter",
    "3": "nationally certified meter",
}
P30_PRODUCT_RFID_MAP = {
    "0": "no",
    "1": "yes",
}

P40_PRODUCT_CURRENT_MAP = {
    "1": "16 A",
    "2": "32 A",
}
P40_PRODUCT_CONNECTOR_MAP = {
    "1": "cable",
    "2": "socket",
}
P40_PRODUCT_PHASE_MAP = {
    "1": "1-phase",
    "2": "3-phase",
    "3": "3-to-1 switching",
    "4": "rotation",
}
P40_PRODUCT_METERING_MAP = {
    "0": "none",
    "1": "energy meter",
    "2": "MID meter",
    "3": "legal meter",
}
P40_PRODUCT_RFID_MAP = {
    "0": "no",
    "1": "yes",
}
P40_PRODUCT_BUTTON_MAP = {
    "0": "no",
    "1": "yes",
}

P30_PRODUCT_FIELDS: tuple[tuple[str, int, Mapping[str, str]], ...] = (
    ("connector", 1, P30_PRODUCT_CONNECTOR_MAP),
    ("supported_current", 2, P30_PRODUCT_CURRENT_MAP),
    ("device_series", 3, P30_PRODUCT_SERIES_MAP),
    ("metering", 4, P30_PRODUCT_METERING_MAP),
    ("rfid", 5, P30_PRODUCT_RFID_MAP),
)

P40_PRODUCT_FIELDS: tuple[tuple[str, int, Mapping[str, str]], ...] = (
    ("supported_current", 1, P40_PRODUCT_CURRENT_MAP),
    ("connector", 2, P40_PRODUCT_CONNECTOR_MAP),
    ("phase_capability", 3, P40_PRODUCT_PHASE_MAP),
    ("metering", 4, P40_PRODUCT_METERING_MAP),
    ("rfid", 5, P40_PRODUCT_RFID_MAP),
    ("button", 6, P40_PRODUCT_BUTTON_MAP),
)

MODEL_PRODUCT_FIELDS = {
    MODEL_KEY_P30: (6, P30_PRODUCT_FIELDS),
    MODEL_KEY_P40: (7, P40_PRODUCT_FIELDS),
}


def _decode_digit(raw: str, mapping: Mapping[str, str]) -> str:
    """Decode a single product digit with a readable fallback."""
    return mapping.get(raw, f"unknown ({raw})")


def _decode_product_fields(
    digits: str,
    fields: tuple[tuple[str, int, Mapping[str, str]], ...],
) -> dict[str, str]:
    """Decode structured product digits to readable attributes."""
    return {
        attribute: _decode_digit(digits[index], mapping)
        for attribute, index, mapping in fields
    }


def describe_product(raw: Optional[int], model_key: Optional[str]) -> dict[str, str | int]:
    """Return decoded product details for register 1016."""
    if raw is None:
        return {}

    attributes: dict[str, str | int] = {
        "raw": raw,
        "detected_model": model_name_for_key(model_key),
    }

    if model_key in MODEL_PRODUCT_FIELDS:
        width, fields = MODEL_PRODUCT_FIELDS[model_key]
        attributes.update(_decode_product_fields(str(raw).zfill(width), fields))

    return attributes


def scale_milliamps(raw: Optional[int]) -> Optional[float]:
    """Convert milliamps to amps."""
    if raw is None:
        return None
    return round(raw / 1000, 3)


def scale_milliwatts(raw: Optional[int]) -> Optional[float]:
    """Convert milliwatts to watts."""
    if raw is None:
        return None
    return round(raw / 1000, 1)


def scale_energy_to_kwh(
    raw: Optional[int],
    *,
    model_key: Optional[str],
    firmware_raw: Optional[int],
) -> Optional[float]:
    """Convert KEBA energy registers to kWh, including the P40 pre-1.2.1 bug."""
    if raw is None:
        return None

    divisor = 10000
    if model_key == MODEL_KEY_P40 and firmware_raw is not None and firmware_raw < 10201:
        divisor = 1000

    return round(raw / divisor, 4)


def scale_volts(raw: Optional[int]) -> Optional[float]:
    """Return the voltage value in volts."""
    if raw is None:
        return None
    return float(raw)


def scale_tenth_percent(raw: Optional[int]) -> Optional[float]:
    """Convert 0.1 percent to percent."""
    if raw is None:
        return None
    return round(raw / 10, 1)


def format_firmware_version(
    raw: Optional[int], *, model_key: Optional[str] = None
) -> Optional[str]:
    """Format the model-specific firmware version."""
    if raw is None:
        return None

    if model_key == MODEL_KEY_P40:
        major = raw // 10000
        minor = (raw // 100) % 100
        patch = raw % 100
        return f"{major}.{minor}.{patch}"

    major = (raw >> 24) & 0xFF
    minor = (raw >> 16) & 0xFF
    patch = (raw >> 8) & 0xFF
    return f"{major}.{minor}.{patch}"


def format_serial_number(raw: Optional[int]) -> Optional[str]:
    """Format the serial number as a string."""
    if raw is None:
        return None
    return str(raw)


__all__ = [
    "describe_product",
    "format_firmware_version",
    "format_serial_number",
    "scale_energy_to_kwh",
    "scale_milliamps",
    "scale_milliwatts",
    "scale_tenth_percent",
    "scale_volts",
]
