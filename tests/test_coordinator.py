"""Tests for KEBA coordinator helper behavior."""

from __future__ import annotations

import asyncio

from custom_components.keba_wallbox_modbus import coordinator as coordinator_module
from custom_components.keba_wallbox_modbus.const import (
    CONF_SLOW_RUNTIME_POLL_INTERVAL,
    SLOW_RUNTIME_POLL_INTERVAL,
    WRITE_ASSUMPTION_TTL,
    WRITE_READBACK_RETRY_DELAY,
)
from custom_components.keba_wallbox_modbus.coordinator import KebaDataUpdateCoordinator
from custom_components.keba_wallbox_modbus.profiles import P30_PROFILE
from custom_components.keba_wallbox_modbus.registers import (
    KEY_ACTIVE_POWER,
    KEY_CABLE_STATE,
    KEY_MAX_CHARGING_CURRENT,
    KEY_MAX_SUPPORTED_CURRENT,
    KEY_PHASE_SWITCH_SOURCE,
    KEY_POWER_FACTOR,
    KEY_TOTAL_ENERGY,
    KEY_VOLTAGE_L1,
    KEY_VOLTAGE_L2,
    KEY_VOLTAGE_L3,
    WRITE_REGISTER_CHARGING_CURRENT,
)


class FakeHub:
    """Minimal Modbus hub for coordinator refresh tests."""

    def __init__(self, readbacks: list[int] | None = None) -> None:
        self.reads = []
        self._readbacks = readbacks or [8_000]

    async def async_read_named_registers(self, registers, *, optional_keys=frozenset()):
        """Record the requested registers and return one readback value."""
        self.reads.append((dict(registers), optional_keys))
        if len(self._readbacks) > 1:
            value = self._readbacks.pop(0)
        else:
            value = self._readbacks[0]
        return {KEY_MAX_CHARGING_CURRENT: value}


class FakeHass:
    """Minimal hass task scheduler for coordinator background tasks."""

    def __init__(self) -> None:
        self.tasks = []

    def async_create_task(self, target, name=None):
        """Schedule a background task."""
        task = asyncio.create_task(target, name=name)
        self.tasks.append(task)
        return task


async def test_targeted_register_refresh_updates_coordinator_data() -> None:
    """A targeted refresh reads only the requested keys and publishes new data."""
    coordinator = KebaDataUpdateCoordinator.__new__(KebaDataUpdateCoordinator)
    coordinator._profile = P30_PROFILE
    coordinator.data = {KEY_ACTIVE_POWER: 4_000_000}
    coordinator.hub = FakeHub()
    updates = []

    def async_set_updated_data(data):
        updates.append(data)

    coordinator.async_set_updated_data = async_set_updated_data

    await coordinator.async_refresh_register_keys([KEY_MAX_CHARGING_CURRENT])

    assert coordinator.hub.reads == [
        ({KEY_MAX_CHARGING_CURRENT: 1100}, frozenset({KEY_MAX_CHARGING_CURRENT}))
    ]
    assert updates == [
        {
            KEY_ACTIVE_POWER: 4_000_000,
            KEY_MAX_CHARGING_CURRENT: 8_000,
        }
    ]


async def test_targeted_register_refresh_ignores_unrequested_fast_keys() -> None:
    """Targeted refresh avoids a complete fast poll after writes."""
    coordinator = KebaDataUpdateCoordinator.__new__(KebaDataUpdateCoordinator)
    coordinator._profile = P30_PROFILE
    coordinator.data = {KEY_ACTIVE_POWER: 4_000_000}
    coordinator.hub = FakeHub()
    coordinator.async_set_updated_data = lambda data: None

    await coordinator.async_refresh_register_keys([KEY_MAX_CHARGING_CURRENT])

    registers, _ = coordinator.hub.reads[0]
    assert KEY_MAX_CHARGING_CURRENT in registers
    assert KEY_ACTIVE_POWER not in registers
    assert KEY_CABLE_STATE not in registers


async def test_only_latest_write_intent_runs_follow_up() -> None:
    """Coalesced writes only publish and refresh the newest write intent."""
    coordinator = KebaDataUpdateCoordinator.__new__(KebaDataUpdateCoordinator)
    coordinator._profile = P30_PROFILE
    coordinator.data = {KEY_ACTIVE_POWER: 4_000_000}
    coordinator.hub = FakeHub()
    writes = []
    updates = []
    first_started = asyncio.Event()
    second_started = asyncio.Event()
    release_writes = asyncio.Event()

    async def async_write_register(address: int, value: int) -> None:
        writes.append((address, value))
        if len(writes) == 1:
            first_started.set()
        if len(writes) == 2:
            second_started.set()
        await release_writes.wait()

    def async_set_updated_data(data):
        coordinator.data = data
        updates.append(dict(data))

    coordinator.async_write_register = async_write_register
    coordinator.async_set_updated_data = async_set_updated_data

    first = asyncio.create_task(
        coordinator.async_write_register_and_refresh(
            WRITE_REGISTER_CHARGING_CURRENT,
            6_000,
            assume_values={KEY_MAX_CHARGING_CURRENT: 6_000},
            refresh_keys=(KEY_MAX_CHARGING_CURRENT,),
        )
    )
    await first_started.wait()
    second = asyncio.create_task(
        coordinator.async_write_register_and_refresh(
            WRITE_REGISTER_CHARGING_CURRENT,
            8_000,
            assume_values={KEY_MAX_CHARGING_CURRENT: 8_000},
            refresh_keys=(KEY_MAX_CHARGING_CURRENT,),
        )
    )
    await second_started.wait()

    release_writes.set()
    assert await asyncio.gather(first, second) == [False, True]

    assert writes == [
        (WRITE_REGISTER_CHARGING_CURRENT, 6_000),
        (WRITE_REGISTER_CHARGING_CURRENT, 8_000),
    ]
    assert coordinator.hub.reads == [
        ({KEY_MAX_CHARGING_CURRENT: 1100}, frozenset({KEY_MAX_CHARGING_CURRENT}))
    ]
    assert all(update.get(KEY_MAX_CHARGING_CURRENT) != 6_000 for update in updates)
    assert updates[-1][KEY_MAX_CHARGING_CURRENT] == 8_000


async def test_superseded_background_write_refresh_is_skipped(monkeypatch) -> None:
    """A delayed readback from an older write does not run after a newer intent."""
    coordinator = KebaDataUpdateCoordinator.__new__(KebaDataUpdateCoordinator)
    coordinator._profile = P30_PROFILE
    coordinator.data = {KEY_ACTIVE_POWER: 4_000_000}
    coordinator.hass = FakeHass()
    coordinator.hub = FakeHub()
    updates = []
    sleep_started = asyncio.Event()
    release_sleep = asyncio.Event()

    async def async_write_register(address: int, value: int) -> None:
        return None

    async def fake_sleep(delay: float) -> None:
        sleep_started.set()
        await release_sleep.wait()

    def async_set_updated_data(data):
        coordinator.data = data
        updates.append(dict(data))

    coordinator.async_write_register = async_write_register
    coordinator.async_set_updated_data = async_set_updated_data
    monkeypatch.setattr(coordinator_module.asyncio, "sleep", fake_sleep)

    assert await coordinator.async_write_register_and_refresh(
        WRITE_REGISTER_CHARGING_CURRENT,
        6_000,
        assume_values={KEY_MAX_CHARGING_CURRENT: 6_000},
        refresh_keys=(KEY_MAX_CHARGING_CURRENT,),
        refresh_delay=1,
        background_refresh=True,
    )
    await sleep_started.wait()

    assert await coordinator.async_write_register_and_refresh(
        WRITE_REGISTER_CHARGING_CURRENT,
        8_000,
        assume_values={KEY_MAX_CHARGING_CURRENT: 8_000},
        refresh_keys=(KEY_MAX_CHARGING_CURRENT,),
        background_refresh=True,
    )

    await coordinator.hass.tasks[-1]
    release_sleep.set()
    await asyncio.gather(*coordinator.hass.tasks)

    assert coordinator.hub.reads == [
        ({KEY_MAX_CHARGING_CURRENT: 1100}, frozenset({KEY_MAX_CHARGING_CURRENT}))
    ]
    assert updates[0][KEY_MAX_CHARGING_CURRENT] == 6_000
    assert updates[-1][KEY_MAX_CHARGING_CURRENT] == 8_000


async def test_stale_write_readback_is_not_published(monkeypatch) -> None:
    """An early stale readback does not flip the UI back to the previous value."""
    coordinator = KebaDataUpdateCoordinator.__new__(KebaDataUpdateCoordinator)
    coordinator._profile = P30_PROFILE
    coordinator.data = {
        KEY_ACTIVE_POWER: 4_000_000,
        KEY_MAX_CHARGING_CURRENT: 6_000,
    }
    coordinator.hub = FakeHub(readbacks=[6_000, 7_000])
    writes = []
    updates = []
    sleeps = []

    async def async_write_register(address: int, value: int) -> None:
        writes.append((address, value))

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    def async_set_updated_data(data):
        coordinator.data = data
        updates.append(dict(data))

    coordinator.async_write_register = async_write_register
    coordinator.async_set_updated_data = async_set_updated_data
    monkeypatch.setattr(coordinator_module.asyncio, "sleep", fake_sleep)

    assert await coordinator.async_write_register_and_refresh(
        WRITE_REGISTER_CHARGING_CURRENT,
        7_000,
        assume_values={KEY_MAX_CHARGING_CURRENT: 7_000},
        refresh_keys=(KEY_MAX_CHARGING_CURRENT,),
    )

    assert writes == [(WRITE_REGISTER_CHARGING_CURRENT, 7_000)]
    assert coordinator.hub.reads == [
        ({KEY_MAX_CHARGING_CURRENT: 1100}, frozenset({KEY_MAX_CHARGING_CURRENT})),
        ({KEY_MAX_CHARGING_CURRENT: 1100}, frozenset({KEY_MAX_CHARGING_CURRENT})),
    ]
    assert sleeps == [WRITE_READBACK_RETRY_DELAY]
    assert all(update[KEY_MAX_CHARGING_CURRENT] == 7_000 for update in updates)


def test_pending_assumed_value_survives_normal_poll(monkeypatch) -> None:
    """A normal scan must not overwrite a recent write with stale readback data."""
    coordinator = KebaDataUpdateCoordinator.__new__(KebaDataUpdateCoordinator)
    coordinator._profile = P30_PROFILE
    coordinator.data = {KEY_MAX_CHARGING_CURRENT: 6_000}
    updates = []

    def async_set_updated_data(data):
        coordinator.data = data
        updates.append(dict(data))

    coordinator.async_set_updated_data = async_set_updated_data
    monkeypatch.setattr(coordinator_module, "monotonic", lambda: 100.0)

    coordinator.assume_register_values({KEY_MAX_CHARGING_CURRENT: 7_000})

    assert coordinator._apply_pending_assumed_values(
        {KEY_MAX_CHARGING_CURRENT: 6_000}
    ) == {KEY_MAX_CHARGING_CURRENT: 7_000}

    assert coordinator._apply_pending_assumed_values(
        {KEY_MAX_CHARGING_CURRENT: 7_000}
    ) == {KEY_MAX_CHARGING_CURRENT: 7_000}
    assert coordinator._pending_assumed_values == {}


def test_pending_assumed_value_expires(monkeypatch) -> None:
    """A rejected write eventually lets the real readback value through."""
    coordinator = KebaDataUpdateCoordinator.__new__(KebaDataUpdateCoordinator)
    coordinator._profile = P30_PROFILE
    coordinator.data = {KEY_MAX_CHARGING_CURRENT: 6_000}
    coordinator.async_set_updated_data = lambda data: None
    current_time = 100.0
    monkeypatch.setattr(coordinator_module, "monotonic", lambda: current_time)

    coordinator.assume_register_values({KEY_MAX_CHARGING_CURRENT: 7_000})

    current_time = 100.0 + WRITE_ASSUMPTION_TTL

    assert coordinator._apply_pending_assumed_values(
        {KEY_MAX_CHARGING_CURRENT: 6_000}
    ) == {KEY_MAX_CHARGING_CURRENT: 6_000}
    assert coordinator._pending_assumed_values == {}


def test_runtime_poll_includes_slow_registers_initially(monkeypatch) -> None:
    """The first runtime poll includes slow configuration and diagnostic values."""
    coordinator = KebaDataUpdateCoordinator.__new__(KebaDataUpdateCoordinator)
    coordinator._profile = P30_PROFILE
    coordinator._last_slow_runtime_poll_at = None
    monkeypatch.setattr(coordinator_module, "monotonic", lambda: 100.0)

    registers, slow_polled = coordinator._runtime_registers_for_poll({})

    assert slow_polled
    assert KEY_ACTIVE_POWER in registers
    assert KEY_TOTAL_ENERGY in registers
    assert KEY_MAX_SUPPORTED_CURRENT in registers
    assert KEY_PHASE_SWITCH_SOURCE in registers


def test_runtime_poll_skips_slow_registers_until_interval(monkeypatch) -> None:
    """Normal runtime polls only include fast-changing values."""
    coordinator = KebaDataUpdateCoordinator.__new__(KebaDataUpdateCoordinator)
    coordinator._profile = P30_PROFILE
    coordinator._last_slow_runtime_poll_at = 100.0
    monkeypatch.setattr(coordinator_module, "monotonic", lambda: 120.0)

    registers, slow_polled = coordinator._runtime_registers_for_poll(
        {key: 1 for key in P30_PROFILE.runtime_register_map}
    )

    assert not slow_polled
    assert KEY_ACTIVE_POWER in registers
    assert KEY_MAX_CHARGING_CURRENT in registers
    assert KEY_TOTAL_ENERGY not in registers
    assert KEY_MAX_SUPPORTED_CURRENT not in registers
    assert KEY_PHASE_SWITCH_SOURCE not in registers


def test_runtime_poll_rechecks_slow_registers_after_interval(monkeypatch) -> None:
    """Slow runtime registers are polled again after the slow interval elapsed."""
    coordinator = KebaDataUpdateCoordinator.__new__(KebaDataUpdateCoordinator)
    coordinator._profile = P30_PROFILE
    coordinator._last_slow_runtime_poll_at = 100.0
    monkeypatch.setattr(
        coordinator_module,
        "monotonic",
        lambda: 100.0 + SLOW_RUNTIME_POLL_INTERVAL,
    )

    registers, slow_polled = coordinator._runtime_registers_for_poll(
        {key: 1 for key in P30_PROFILE.runtime_register_map}
    )

    assert slow_polled
    assert KEY_TOTAL_ENERGY in registers
    assert KEY_MAX_SUPPORTED_CURRENT in registers


def test_runtime_poll_uses_configured_slow_interval(monkeypatch) -> None:
    """Slow runtime registers use the configured interval."""
    coordinator = KebaDataUpdateCoordinator.__new__(KebaDataUpdateCoordinator)
    coordinator._profile = P30_PROFILE
    coordinator._config = {CONF_SLOW_RUNTIME_POLL_INTERVAL: 30}
    coordinator._last_slow_runtime_poll_at = 100.0
    monkeypatch.setattr(coordinator_module, "monotonic", lambda: 130.0)

    registers, slow_polled = coordinator._runtime_registers_for_poll(
        {key: 1 for key in P30_PROFILE.runtime_register_map}
    )

    assert slow_polled
    assert KEY_TOTAL_ENERGY in registers


async def test_charging_power_target_write_skips_next_enabled_regulation() -> None:
    """Changing charging power writes once and avoids immediate stale regulation."""
    coordinator = KebaDataUpdateCoordinator.__new__(KebaDataUpdateCoordinator)
    coordinator.data = None
    coordinator._profile = P30_PROFILE
    coordinator._charging_power_target = 5.0
    coordinator._charging_current_regulation_enabled = True
    coordinator._charging_current_regulation_holdoff_cycles = 0
    writes = []

    async def async_write_register(address: int, value: int) -> None:
        writes.append((address, value))

    coordinator.async_write_register = async_write_register

    assert await coordinator.async_apply_charging_power_target(5.0) == 7_200
    assert writes == [(WRITE_REGISTER_CHARGING_CURRENT, 7_200)]

    data = {
        KEY_ACTIVE_POWER: 4_744_000,
        KEY_MAX_CHARGING_CURRENT: 7_200,
        KEY_MAX_SUPPORTED_CURRENT: 16_000,
        KEY_POWER_FACTOR: 998,
        KEY_VOLTAGE_L1: 226,
        KEY_VOLTAGE_L2: 225,
        KEY_VOLTAGE_L3: 225,
    }

    assert await coordinator.async_apply_charging_current_regulation(data) is None
    assert writes == [(WRITE_REGISTER_CHARGING_CURRENT, 7_200)]
    assert coordinator._charging_current_regulation_holdoff_cycles == 1

    assert await coordinator.async_apply_charging_current_regulation(data) is None
    assert writes == [(WRITE_REGISTER_CHARGING_CURRENT, 7_200)]
    assert coordinator._charging_current_regulation_holdoff_cycles == 0
