import socket
import struct
import time
from telemetry import packets

PACKET_ID_MOTION = 0
PACKET_ID_SESSION = 1
PACKET_ID_LAP_DATA = 2
PACKET_ID_EVENT = 3
PACKET_ID_PARTICIPANTS = 4
PACKET_ID_CAR_STATUS = 7
PACKET_ID_CAR_DAMAGE = 10


class TelemetryListener:
    def __init__(self, state_tracker, ip="0.0.0.0", port=20777, capture_writer=None):
        self.state_tracker = state_tracker
        self.ip = ip
        self.port = port
        self.capture_writer = capture_writer
        self._sock = None
        self._running = False

    def start(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind((self.ip, self.port))
        self._sock.settimeout(1.0)
        self._running = True
        last_packet_time = time.time()
        warned = False
        while self._running:
            try:
                data, _ = self._sock.recvfrom(2048)
                last_packet_time = time.time()
                warned = False
            except socket.timeout:
                if not warned and time.time() - last_packet_time > 5:
                    print("[telemetry] no packets received in 5s - check game UDP settings")
                    warned = True
                continue
            if self.capture_writer:
                self.capture_writer(data)
            self._dispatch(data)

    def stop(self):
        self._running = False
        if self._sock:
            self._sock.close()

    def _dispatch(self, data):
        try:
            header = packets.parse_header(data)
            player_car_index = header["player_car_index"]
            packet_id = header["packet_id"]
            self.state_tracker.update_player_car_index(player_car_index)
            if packet_id == PACKET_ID_MOTION:
                motion_cars = packets.parse_motion_packet(data)
                self.state_tracker.update_motion(player_car_index, motion_cars)
            elif packet_id == PACKET_ID_LAP_DATA:
                my_lap, gap_ahead_ms, gap_behind_ms, all_cars = packets.parse_lap_data_packet(data, player_car_index)
                self.state_tracker.update_lap_data(my_lap, gap_ahead_ms, gap_behind_ms, all_cars)
            elif packet_id == PACKET_ID_CAR_STATUS:
                car_status = packets.parse_car_status_packet(data, player_car_index)
                self.state_tracker.update_car_status(car_status)
            elif packet_id == PACKET_ID_CAR_DAMAGE:
                tyres_wear, damage_components = packets.parse_car_damage_packet(data, player_car_index)
                self.state_tracker.update_car_damage(tyres_wear, damage_components)
            elif packet_id == PACKET_ID_SESSION:
                session = packets.parse_session_packet(data)
                self.state_tracker.update_session(session)
            elif packet_id == PACKET_ID_EVENT:
                event_code, details = packets.parse_event_packet(data)
                self.state_tracker.update_event(event_code, details)
            elif packet_id == PACKET_ID_PARTICIPANTS:
                num_active_cars, participants = packets.parse_participants_packet(data)
                self.state_tracker.update_participants(num_active_cars, participants)
        except (struct.error, IndexError, UnicodeDecodeError) as e:
            print(f"[telemetry] malformed packet ignored: {e}")
