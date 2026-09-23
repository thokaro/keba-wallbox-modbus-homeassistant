"""Tests for KEBA Modbus access helpers."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from modbus_connection import ModbusError, ModbusUnit

from custom_components.keba_wallbox_modbus import keba_modbus as modbus
from custom_components.keba_wallbox_modbus.const import MIN_WRITE_INTERVAL
from custom_components.keba_wallbox_modbus.modbus import KebaModbusHub
from custom_components.keba_wallbox_modbus.registers import WRITE_REGISTER_CHARGING_CURRENT


def make_unit():
    """Return a backend-neutral unit without a network connection."""
    unit = Mock(spec=ModbusUnit)
    unit.write_register = AsyncMock()
    unit.read_holding_registers = AsyncMock(return_value=[1, 2])
    return unit


async def test_first_write_does_not_wait(monkeypatch) -> None:
    """The first register write runs immediately without a startup delay."""
    unit = make_unit()
    hub = KebaModbusHub(unit)
    sleeps: list[float] = []
    calls: list[dict[str, Any]] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    async def fake_write(address: int, value: int) -> None:
        calls.append({"address": address, "value": value})

    monkeypatch.setattr(modbus, "monotonic", lambda: 1.0)
    monkeypatch.setattr(modbus.asyncio, "sleep", fake_sleep)
    unit.write_register.side_effect = fake_write

    await hub.async_write_uint16(WRITE_REGISTER_CHARGING_CURRENT, 6000)

    assert sleeps == []
    assert calls == [{"address": WRITE_REGISTER_CHARGING_CURRENT, "value": 6000}]
    assert hub._last_write_at == 1.0


async def test_write_after_interval_does_not_wait(monkeypatch) -> None:
    """A write older than the KEBA write interval does not delay the next write."""
    unit = make_unit()
    hub = KebaModbusHub(unit)
    hub._last_write_at = 10.0
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    async def fake_write(address: int, value: int) -> None:
        pass

    monkeypatch.setattr(modbus, "monotonic", lambda: 15.0 + MIN_WRITE_INTERVAL)
    monkeypatch.setattr(modbus.asyncio, "sleep", fake_sleep)
    unit.write_register.side_effect = fake_write

    await hub.async_write_uint16(WRITE_REGISTER_CHARGING_CURRENT, 7000)

    assert sleeps == []
    assert hub._last_write_at == 15.0 + MIN_WRITE_INTERVAL


async def test_recent_write_waits_for_remaining_interval(monkeypatch) -> None:
    """A recent write delays the next write only by the missing interval."""
    unit = make_unit()
    hub = KebaModbusHub(unit)
    hub._last_write_at = 10.0
    sleeps: list[float] = []
    times = iter([12.0, 15.0])

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    async def fake_write(address: int, value: int) -> None:
        pass

    monkeypatch.setattr(modbus, "monotonic", lambda: next(times))
    monkeypatch.setattr(modbus.asyncio, "sleep", fake_sleep)
    unit.write_register.side_effect = fake_write

    await hub.async_write_uint16(WRITE_REGISTER_CHARGING_CURRENT, 7000)

    assert sleeps == [MIN_WRITE_INTERVAL - 2.0]
    assert hub._last_write_at == 15.0


async def test_recent_writes_to_same_register_are_coalesced(monkeypatch) -> None:
    """Only the newest pending value for one register is written after the delay."""
    original_sleep = asyncio.sleep
    unit = make_unit()
    hub = KebaModbusHub(unit)
    hub._last_write_at = 10.0
    calls: list[dict[str, Any]] = []
    sleeps: list[float] = []
    sleep_started = asyncio.Event()
    release_sleep = asyncio.Event()
    times = iter([12.0, 15.0])

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)
        sleep_started.set()
        await release_sleep.wait()

    async def fake_write(address: int, value: int) -> None:
        calls.append({"address": address, "value": value})

    monkeypatch.setattr(modbus, "monotonic", lambda: next(times))
    monkeypatch.setattr(modbus.asyncio, "sleep", fake_sleep)
    unit.write_register.side_effect = fake_write

    first = asyncio.create_task(
        hub.async_write_uint16(WRITE_REGISTER_CHARGING_CURRENT, 6000)
    )
    await sleep_started.wait()
    second = asyncio.create_task(
        hub.async_write_uint16(WRITE_REGISTER_CHARGING_CURRENT, 7000)
    )
    third = asyncio.create_task(
        hub.async_write_uint16(WRITE_REGISTER_CHARGING_CURRENT, 8000)
    )
    await original_sleep(0)

    release_sleep.set()
    await asyncio.gather(first, second, third)

    assert sleeps == [MIN_WRITE_INTERVAL - 2.0]
    assert calls == [{"address": WRITE_REGISTER_CHARGING_CURRENT, "value": 8000}]
    assert hub._last_write_at == 15.0


async def test_unit_requirements_and_uint32_read() -> None:
    unit = make_unit()
    hub = KebaModbusHub(unit, timeout=7)
    if hasattr(unit, "require_timeout"):
        unit.require_timeout.assert_called_once_with(7)
    else:
        assert hub._request_timeout == 7
    unit.set_message_spacing.assert_called_once_with(0.6)
    assert await hub.async_read_named_registers({"serial": 1014}) == {"serial": 65538}
    unit.read_holding_registers.assert_awaited_once_with(1014, 2)


async def test_optional_register_failure() -> None:
    unit = make_unit()
    unit.read_holding_registers.side_effect = [[0, 42], ModbusError("unsupported")]
    hub = KebaModbusHub(unit)
    assert await hub.async_read_named_registers(
        {"required": 1, "optional": 3}, optional_keys=frozenset({"optional"})
    ) == {"required": 42, "optional": None}


@pytest.mark.parametrize("reply", [ModbusError("offline"), [], [1]])
async def test_required_register_failure_and_recovery(reply) -> None:
    unit = make_unit()
    unit.read_holding_registers.side_effect = [reply, [0, 42]]
    hub = KebaModbusHub(unit)
    with pytest.raises(modbus.KebaModbusError):
        await hub.async_read_named_registers({"required": 1})
    assert await hub.async_read_named_registers({"required": 1}) == {"required": 42}
    unit.disconnect.assert_not_called()


async def test_all_optional_reads_failed() -> None:
    unit = make_unit()
    unit.read_holding_registers.side_effect = ModbusError("offline")
    with pytest.raises(modbus.KebaModbusError, match="No Modbus registers"):
        await KebaModbusHub(unit).async_read_named_registers(
            {"optional": 1}, optional_keys=frozenset({"optional"})
        )


async def test_write_failure_reaches_caller_and_next_write_recovers() -> None:
    unit = make_unit()
    unit.write_register.side_effect = [ModbusError("offline"), None]
    hub = KebaModbusHub(unit)
    with pytest.raises(modbus.KebaModbusError, match="Failed to write"):
        await hub.async_write_uint16(5004, 6000)
    await hub.async_write_uint16(5004, 7000)
    assert unit.write_register.await_count == 2


async def test_close_cancels_waiting_writes_without_disconnecting(monkeypatch) -> None:
    unit = make_unit()
    hub = KebaModbusHub(unit)
    started = asyncio.Event()

    async def wait_for_interval():
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(hub, "_respect_write_interval", wait_for_interval)
    pending = asyncio.create_task(hub.async_write_uint16(5004, 6000))
    await started.wait()
    await hub.async_close()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(pending, timeout=1)
    unit.write_register.assert_not_called()
    unit.disconnect.assert_not_called()
    with pytest.raises(modbus.KebaModbusError, match="closed"):
        await hub.async_write_uint16(5004, 7000)


async def test_close_cancels_inflight_write() -> None:
    unit = make_unit()
    hub = KebaModbusHub(unit)
    started = asyncio.Event()

    async def write(address, value):
        started.set()
        await asyncio.Event().wait()

    unit.write_register.side_effect = write
    pending = asyncio.create_task(hub.async_write_uint16(5004, 6000))
    await started.wait()
    await hub.async_close()
    # A cancellation during the network operation must also settle its caller.
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(pending, timeout=1)


@pytest.mark.parametrize("operation", ["read", "write"])
async def test_legacy_unit_honors_configured_timeout(operation) -> None:
    unit = make_unit()
    if hasattr(unit, "require_timeout"):
        del unit.require_timeout
    started = asyncio.Event()

    async def stall(*args):
        started.set()
        await asyncio.Event().wait()

    unit.read_holding_registers.side_effect = stall
    unit.write_register.side_effect = stall
    hub = KebaModbusHub(unit, timeout=0.01)
    with pytest.raises(modbus.KebaModbusError) as error:
        if operation == "read":
            await hub.async_read_named_registers({"required": 1})
        else:
            await hub.async_write_uint16(5004, 6000)
    assert started.is_set()
    assert isinstance(error.value.__cause__, TimeoutError)
    await hub.async_close()


def test_modern_unit_registers_timeout_requirement() -> None:
    unit = make_unit()
    unit.require_timeout = Mock()
    hub = KebaModbusHub(unit, timeout=7)
    unit.require_timeout.assert_called_once_with(7)
    assert hub._request_timeout is None
