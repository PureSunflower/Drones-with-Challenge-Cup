"""Future hardware framing interface. The simulation bus does not use it."""

from collections.abc import Iterable
from typing import Protocol


class SerialFraming(Protocol):
    def encode_frame(self, payload: bytes) -> bytes: ...
    def feed_bytes(self, chunk: bytes) -> Iterable[bytes]: ...


def open_serial(port: str, *, baudrate: int, bytesize: int, parity: str,
                stopbits: float, timeout: float, **options):
    from serial import Serial

    return Serial(port=port, baudrate=baudrate, bytesize=bytesize,
                  parity=parity, stopbits=stopbits, timeout=timeout, **options)
