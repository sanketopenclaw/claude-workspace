from telemetry.capture import write_packet, replay_session


def test_replay_session_calls_callback_with_original_bytes(tmp_path):
    file_path = tmp_path / "session.bin"
    packet1 = b"\x01\x02\x03"
    packet2 = b"\xaa\xbb"
    with open(file_path, "wb") as f:
        write_packet(f, packet1)
        write_packet(f, packet2)

    received = []
    replay_session(str(file_path), on_packet=received.append)

    assert received == [packet1, packet2]
