"""Model profiles for KEBA wallboxes."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Mapping, Optional

from .const import (
    MODEL,
    MODEL_KEY_P30,
    MODEL_KEY_P40,
    MODEL_NAME_P30,
    MODEL_NAME_P40,
)
from .registers import (
    P30_RUNTIME_REGISTER_MAP,
    P30_STATIC_REGISTER_MAP,
    P40_RUNTIME_REGISTER_MAP,
    P40_STATIC_REGISTER_MAP,
    PHASE_SWITCH_SOURCE_MAP_P30,
    PHASE_SWITCH_SOURCE_MAP_P40,
    SLOW_RUNTIME_REGISTER_KEYS,
)


@dataclass(frozen=True)
class KebaProfile:
    """Describe model-specific Modbus behavior."""

    model_key: str
    model_name: str
    static_register_map: Mapping[str, int]
    runtime_register_map: Mapping[str, int]
    optional_runtime_keys: frozenset[str]
    phase_switch_source_map: Mapping[int, str]
    supports_failsafe_persist: bool
    supports_fast_charging: bool
    charging_current_min_amps: int

    @property
    def phase_switch_source_write_map(self) -> Mapping[str, int]:
        """Return write values keyed by option label."""
        return {option: raw for raw, option in self.phase_switch_source_map.items()}

    @cached_property
    def slow_runtime_register_map(self) -> Mapping[str, int]:
        """Return runtime registers that should be polled less frequently."""
        return {
            key: address
            for key, address in self.runtime_register_map.items()
            if key in SLOW_RUNTIME_REGISTER_KEYS
        }

    @cached_property
    def fast_runtime_register_map(self) -> Mapping[str, int]:
        """Return runtime registers that should be polled every update interval."""
        return {
            key: address
            for key, address in self.runtime_register_map.items()
            if key not in self.slow_runtime_register_map
        }

    def supports_key(self, key: str) -> bool:
        """Return whether the profile exposes the given read key."""
        return key in self.static_register_map or key in self.runtime_register_map


P30_PROFILE = KebaProfile(
    model_key=MODEL_KEY_P30,
    model_name=MODEL_NAME_P30,
    static_register_map=P30_STATIC_REGISTER_MAP,
    runtime_register_map=P30_RUNTIME_REGISTER_MAP,
    optional_runtime_keys=frozenset(P30_RUNTIME_REGISTER_MAP),
    phase_switch_source_map=PHASE_SWITCH_SOURCE_MAP_P30,
    supports_failsafe_persist=True,
    supports_fast_charging=False,
    charging_current_min_amps=0,
)

P40_PROFILE = KebaProfile(
    model_key=MODEL_KEY_P40,
    model_name=MODEL_NAME_P40,
    static_register_map=P40_STATIC_REGISTER_MAP,
    runtime_register_map=P40_RUNTIME_REGISTER_MAP,
    optional_runtime_keys=frozenset(P40_RUNTIME_REGISTER_MAP),
    phase_switch_source_map=PHASE_SWITCH_SOURCE_MAP_P40,
    supports_failsafe_persist=False,
    supports_fast_charging=True,
    charging_current_min_amps=0,
)

PROFILE_BY_MODEL = {
    MODEL_KEY_P30: P30_PROFILE,
    MODEL_KEY_P40: P40_PROFILE,
}


def detect_wallbox_model(raw_product: Optional[int]) -> Optional[str]:
    """Detect the wallbox model family from register 1016."""
    if raw_product is None:
        return None

    normalized = str(abs(raw_product))
    if not normalized:
        return None

    if normalized[0] == "3":
        return MODEL_KEY_P30

    if normalized[0] == "4":
        return MODEL_KEY_P40

    return None


def get_wallbox_profile(model_key: Optional[str]) -> KebaProfile:
    """Return the model-specific profile."""
    return PROFILE_BY_MODEL.get(model_key, P30_PROFILE)


def model_name_for_key(model_key: Optional[str]) -> str:
    """Return the display name for a detected model."""
    profile = PROFILE_BY_MODEL.get(model_key)
    return profile.model_name if profile is not None else MODEL


__all__ = [
    "KebaProfile",
    "P30_PROFILE",
    "P40_PROFILE",
    "PROFILE_BY_MODEL",
    "detect_wallbox_model",
    "get_wallbox_profile",
    "model_name_for_key",
]
