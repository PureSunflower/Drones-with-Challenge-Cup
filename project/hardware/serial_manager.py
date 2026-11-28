from dataclasses import dataclass

from serial import SerialException
from serial.tools.list_ports import comports

from communication.serial_transport import open_serial


@dataclass(frozen=True)
class SerialSettings:
    port: str
    baudrate: int
    bytesize: int
    parity: str
    stopbits: float
    timeout: float


class SerialManager:
    def __init__(self) -> None:
        self.connection = None

    @staticmethod
    def scan() -> list[str]:
        return [f"{port.device} · {port.description}" for port in comports()]

    def open(self, settings: SerialSettings) -> None:
        self.close()
        self.connection = open_serial(settings.port, baudrate=settings.baudrate,
                                      bytesize=settings.bytesize, parity=settings.parity,
                                      stopbits=settings.stopbits, timeout=settings.timeout,
                                      write_timeout=settings.timeout)

    def close(self) -> None:
        connection, self.connection = self.connection, None
        if connection is not None:
            connection.close()

    def read(self) -> bytes:
        if self.connection is None or not self.connection.is_open:
            raise SerialException("串口未打开")
        return self.connection.read(min(self.connection.in_waiting, 65536))

    def write(self, data: bytes) -> None:
        if self.connection is None or not self.connection.is_open:
            raise SerialException("串口未打开")
        if self.connection.write(data) != len(data):
            raise SerialException("串口写入不完整")
