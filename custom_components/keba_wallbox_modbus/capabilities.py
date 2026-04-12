"""Capability helpers for KEBA wallboxes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .decoding import describe_product
from .profiles import KebaProfile


@dataclass(frozen=True)
class KebaCapabilities:
    """Describe product- and profile-derived wallbox capabilities."""

    connector: Optional[str]
    supports_unlock_plug: bool
    supports_failsafe_persist: bool
    supports_fast_charging: bool


def derive_capabilities(
    *,
    product_raw: Optional[int],
    model_key: Optional[str],
    profile: KebaProfile,
) -> KebaCapabilities:
    """Return derived capabilities for the current wallbox state."""
    connector = describe_product(product_raw, model_key).get("connector")

    return KebaCapabilities(
        connector=connector if isinstance(connector, str) else None,
        supports_unlock_plug=connector == "socket",
        supports_failsafe_persist=profile.supports_failsafe_persist,
        supports_fast_charging=profile.supports_fast_charging,
    )


__all__ = ["KebaCapabilities", "derive_capabilities"]
