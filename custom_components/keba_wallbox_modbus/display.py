"""UDP display helpers for KEBA wallboxes."""

from __future__ import annotations

import json
import socket
from typing import Any

from .const import UDP_DISPLAY_MAX_DURATION, UDP_DISPLAY_MAX_LENGTH, UDP_DISPLAY_PORT
from .modbus import KebaModbusError


class KebaDisplayClient:
    """Send display commands and probe display support via UDP."""

    def __init__(self, *, host: str, timeout: int) -> None:
        self._host = host
        self._timeout = timeout

    def send_text(self, text: str, *, min_time: float, max_time: float) -> None:
        """Show a transient text on the KEBA display via UDP."""
        if not isinstance(min_time, (int, float)) or not isinstance(
            max_time, (int, float)
        ):
            raise KebaModbusError("Display times must be numeric")

        if (
            min_time < 0
            or min_time > UDP_DISPLAY_MAX_DURATION
            or max_time < 0
            or max_time > UDP_DISPLAY_MAX_DURATION
        ):
            raise KebaModbusError(
                f"Display times must be between 0 and {UDP_DISPLAY_MAX_DURATION} seconds"
            )

        if min_time > max_time:
            raise KebaModbusError(
                "Display minimum time must not be greater than maximum time"
            )

        normalized_text = text.replace(" ", "$")[:UDP_DISPLAY_MAX_LENGTH]
        command = (
            f"display 1 {int(round(min_time))} {int(round(max_time))} 0 {normalized_text}"
        )
        self._send_command(command)

    def probe_display_support(self) -> bool:
        """Probe report 1 via UDP and derive display support from the product string."""
        payload, response_ip = self._send_command("report 1", expect_response=True)

        if not _udp_response_matches_host(response_ip, self._host):
            return False

        try:
            report_1 = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False

        return _report_1_has_display(report_1)

    def _send_command(
        self,
        command: str,
        *,
        expect_response: bool = False,
    ) -> tuple[bytes, str] | tuple[None, None]:
        """Send a UDP command and optionally wait for a response."""
        try:
            payload = command.encode("ascii")
        except UnicodeEncodeError as err:
            raise KebaModbusError(
                "Display text must contain ASCII characters only"
            ) from err

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
                udp_socket.settimeout(self._timeout)
                udp_socket.bind(("0.0.0.0", UDP_DISPLAY_PORT))
                udp_socket.sendto(payload, (self._host, UDP_DISPLAY_PORT))
                if not expect_response:
                    return None, None

                response_payload, address = udp_socket.recvfrom(4096)
        except OSError as err:
            raise KebaModbusError(
                f"Failed to send UDP display command to {self._host}:{UDP_DISPLAY_PORT}: {err}"
            ) from err

        return response_payload, address[0]


def _report_1_has_display(report_1: dict[str, Any]) -> bool:
    """Determine display support like keba_kecontact.ChargingStationInfo."""
    if not isinstance(report_1, dict):
        return False

    if report_1.get("ID") != "1":
        return False

    product = report_1.get("Product")
    if not isinstance(product, str):
        return False

    p_split = product.split("-")
    if len(p_split) < 4:
        return False

    manufacturer = p_split[0]
    model = p_split[1]

    if manufacturer != "KC":
        return False

    if model != "P30":
        return False

    return "KC-P30-EC220112-000-DE" not in product


def _udp_response_matches_host(response_ip: str, expected_host: str) -> bool:
    """Return whether the UDP response IP belongs to the expected host."""
    if response_ip == expected_host:
        return True

    try:
        resolved = {
            addr_info[4][0]
            for addr_info in socket.getaddrinfo(expected_host, None, socket.AF_INET)
        }
    except OSError:
        return False

    return response_ip in resolved


__all__ = ["KebaDisplayClient"]
