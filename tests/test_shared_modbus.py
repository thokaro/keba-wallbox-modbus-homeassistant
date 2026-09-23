"""Shared connection ownership and config-flow probe regression tests."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.components.modbus import connection
from modbus_connection import ModbusConnection, ModbusError, ModbusTcpParams, ModbusUnit
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.keba_wallbox_modbus.const import DOMAIN
from custom_components.keba_wallbox_modbus.coordinator import KebaDataUpdateCoordinator
from custom_components.keba_wallbox_modbus.modbus import KebaModbusError, async_probe_device
from custom_components.keba_wallbox_modbus.registers import DISCOVERY_REGISTER_MAP


@pytest.fixture
def backend():
    """Replace only the network backend, retaining HA's real connection manager."""
    unit = Mock(spec=ModbusUnit)
    unit.read_holding_registers = AsyncMock(return_value=[0, 42])
    client = Mock(spec=ModbusConnection)
    client.for_unit.return_value = unit
    client.close = AsyncMock()
    with patch.object(connection, "ModbusConnection", return_value=client) as factory:
        yield factory, client, unit


@pytest.mark.parametrize("failure", [False, True])
async def test_temporary_probe_releases_its_connection(hass, backend, failure):
    factory, client, unit = backend
    if failure:
        unit.read_holding_registers.side_effect = ModbusError("offline")
        with pytest.raises(KebaModbusError):
            await async_probe_device(hass, "wallbox.local", 502, 7, 255)
    else:
        result = await async_probe_device(hass, "wallbox.local", 502, 7, 255)
        assert result == dict.fromkeys(DISCOVERY_REGISTER_MAP, 42)
    factory.assert_called_once_with(ModbusTcpParams(host="wallbox.local", port=502))
    client.for_unit.assert_called_once_with(255)
    if hasattr(unit, "require_timeout"):
        unit.require_timeout.assert_called_once_with(7)
    client.close.assert_awaited_once()


async def test_probe_and_unload_preserve_other_consumers(hass, backend):
    factory, client, unit = backend
    entries = [
        MockConfigEntry(domain=DOMAIN, data={"host": "wallbox.local", "unit_id": unit_id})
        for unit_id in (255, 1)
    ]
    coordinators = [KebaDataUpdateCoordinator(hass, entry) for entry in entries]
    factory.assert_called_once()
    assert [call.args[0] for call in client.for_unit.call_args_list] == [255, 1]

    await async_probe_device(hass, "wallbox.local", 502, 5, 255)
    client.close.assert_not_called()
    unit.read_holding_registers.side_effect = ModbusError("offline")
    with pytest.raises(KebaModbusError):
        await async_probe_device(hass, "wallbox.local", 502, 5, 255)
    client.close.assert_not_called()

    await coordinators[0].async_shutdown()
    await entries[0]._async_process_on_unload(hass)
    client.close.assert_not_called()
    await coordinators[1].async_shutdown()
    await entries[1]._async_process_on_unload(hass)
    client.close.assert_awaited_once()
    unit.disconnect.assert_not_called()
