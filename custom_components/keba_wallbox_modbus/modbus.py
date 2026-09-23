"""Bind KEBA device access to Home Assistant's shared Modbus connections."""

from __future__ import annotations

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.core import HomeAssistant
from modbus_connection import ModbusTcpParams

from .keba_modbus import KebaModbusError, KebaModbusHub
from .registers import DISCOVERY_REGISTER_MAP

__all__ = ["KebaModbusError", "KebaModbusHub", "async_probe_device"]


async def async_probe_device(
    hass: HomeAssistant,
    host: str,
    port: int,
    timeout: int,
    unit_id: int,
) -> dict[str, int | None]:
    """Probe using a temporary hold, without closing another entry's connection."""
    async with async_get_temporary_unit(
        hass, ModbusTcpParams(host=host, port=port), unit_id
    ) as unit:
        device = KebaModbusHub(unit, timeout=timeout)
        try:
            return await device.async_read_named_registers(DISCOVERY_REGISTER_MAP)
        finally:
            await device.async_close()
