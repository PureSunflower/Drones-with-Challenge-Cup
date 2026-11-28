from unittest.mock import Mock

import pytest

from communication.message import Message, MessageType
from communication.protocol import decode, encode
from hardware.hardware_adapter import ConnectionStatus, HardwareAdapter
from hardware.serial_manager import SerialSettings
from hardware.serial_protocol import FrameRules, SerialProtocol


def extract_test_frames(buffer):
    *complete, tail = buffer.split(b"\n")
    return complete, tail


def test_fragmented_handshake_and_disconnect():
    message = Message(MessageType.LINK_STATUS, "001", "006", 1, 0, {})
    raw = encode(message).encode() + b"\n"
    port = Mock()
    port.read.side_effect = [raw[:7], raw[7:], OSError("lost")]
    adapter = HardwareAdapter(
        port, SerialProtocol(FrameRules(extract_test_frames,
                                       lambda raw: decode(raw.decode()),
                                       lambda msg: encode(msg).encode() + b"\n")),
        lambda msg: msg == message,
    )
    adapter.connect(SerialSettings("test", 1, 8, "N", 1, 0))
    assert adapter.get_connection_status() == ConnectionStatus.VERIFYING
    assert adapter.receive_message() == []
    assert adapter.get_connection_status() == ConnectionStatus.VERIFYING
    assert adapter.receive_message() == [message]
    assert adapter.get_connection_status() == ConnectionStatus.CONNECTED
    with pytest.raises(OSError, match="lost"):
        adapter.receive_message()
    assert adapter.get_connection_status() == ConnectionStatus.DISCONNECTED
