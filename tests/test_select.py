"""Tests for KEBA select entities."""

from __future__ import annotations

from custom_components.keba_wallbox_modbus.profiles import P30_PROFILE
from custom_components.keba_wallbox_modbus.registers import (
    KEY_PHASE_SWITCH_STATE,
    WRITE_REGISTER_PHASE_SWITCH_STATE,
)
from custom_components.keba_wallbox_modbus.select import KebaSelectEntity
from custom_components.keba_wallbox_modbus.write_descriptions import SELECT_DESCRIPTIONS


class FakeCoordinator:
    """Minimal coordinator for select entity write tests."""

    def __init__(self) -> None:
        self.profile = P30_PROFILE
        self.data = {KEY_PHASE_SWITCH_STATE: 1}
        self.writes = []

    async def async_write_register_and_refresh(
        self,
        address,
        value,
        *,
        refresh_keys=None,
    ):
        """Record a register write with its requested refresh keys."""
        self.writes.append((address, value, tuple(refresh_keys or ())))


def _select_description(key: str):
    return next(
        description for description in SELECT_DESCRIPTIONS if description.key == key
    )


async def test_select_write_refreshes_only_readback_key() -> None:
    """Select writes request a targeted refresh for their readback register."""
    coordinator = FakeCoordinator()
    entity = KebaSelectEntity.__new__(KebaSelectEntity)
    entity.coordinator = coordinator
    entity.entity_description = _select_description("phase_switch_state")

    await entity.async_select_option("3 phases")

    assert coordinator.writes == [
        (WRITE_REGISTER_PHASE_SWITCH_STATE, 1, (KEY_PHASE_SWITCH_STATE,))
    ]
