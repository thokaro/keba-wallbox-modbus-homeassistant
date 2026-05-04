"""Typed helpers for KEBA Wallbox Modbus."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import KebaDataUpdateCoordinator

    KebaConfigEntry: TypeAlias = ConfigEntry[KebaDataUpdateCoordinator]
else:
    KebaConfigEntry = ConfigEntry
