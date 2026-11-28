from collections.abc import Callable
from enum import StrEnum

from communication.message import Message
from hardware.serial_manager import SerialManager, SerialSettings
from hardware.serial_protocol import SerialProtocol


class ConnectionStatus(StrEnum):
    DISCONNECTED = "DISCONNECTED"
    VERIFYING = "VERIFYING"
    CONNECTED = "CONNECTED"


class HardwareAdapter:
    def __init__(self, serial: SerialManager, protocol: SerialProtocol,
                 verify: Callable[[Message], bool]) -> None:
        self.serial = serial
        self.protocol = protocol
        self.verify = verify
        self.status = ConnectionStatus.DISCONNECTED

    def connect(self, settings: SerialSettings) -> None:
        self.disconnect()
        self.serial.open(settings)
        self.status = ConnectionStatus.VERIFYING

    def disconnect(self) -> None:
        self.status = ConnectionStatus.DISCONNECTED
        self.protocol.reset()
        self.serial.close()

    def get_connection_status(self) -> ConnectionStatus:
        return self.status

    def send_message(self, message: Message) -> None:
        # A verification request can be sent while the port is open.
        try:
            self.serial.write(self.protocol.rules.encode(message))
        except OSError:
            self.disconnect()
            raise

    def receive_message(self) -> list[Message]:
        try:
            messages = self.protocol.feed(self.serial.read())
        except OSError:
            self.disconnect()
            raise
        if self.status == ConnectionStatus.VERIFYING:
            for index, message in enumerate(messages):
                if self.verify(message):
                    self.status = ConnectionStatus.CONNECTED
                    return messages[index:]
            return []
        return messages
