# F1 25 AI Race Engineer — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Live AI race engineer for F1 25 — listens to real UDP telemetry from the game PC, speaks 3 proactive callouts (lap delta, tyre/fuel, gap to rivals), and answers spoken questions on demand.

**Architecture:** UDP listener parses F1 25 telemetry packets into a shared `State` object; a deterministic `RuleEngine` watches `State` for threshold crossings and emits `Event`s; Claude phrases each `Event` into one spoken line (with a canned-template fallback if the API call fails); a wake-word thread listens for a spoken question and routes it through STT → Claude → TTS. Runs entirely on the laptop (this machine), receiving telemetry cross-network from the separate game PC.

**Tech Stack:** Python 3, `anthropic` (Claude API), `edge-tts` + `pygame` (voice out), `openwakeword` + `sounddevice` (wake word), `faster-whisper` (speech-to-text), `tkinter` (text overlay), `pytest`.

## Global Constraints

- Game UDP settings (already configured, see design spec): IP `192.168.0.115`, port `20777`, format `2025`, send rate `20Hz`, "Your Telemetry" = Public.
- Packet struct layouts below are copied verbatim from the official F1 25 UDP telemetry structs (verified against `MacManley/f1-25-udp` on GitHub, a released F1 25 telemetry parser) — do not "simplify" these byte layouts, they must match exactly or every field after the first mismatch decodes garbage.
- Tyre wear array order (`m_tyresWear[4]`) is not verified against index meaning (front/rear/left/right) — Phase 1 only uses `max()` of the 4 values, so exact index-to-wheel mapping doesn't matter yet. Do not assume index 0 = front-left without checking the official spec first if a later phase needs per-wheel detail.
- Phase 1 lap/sector delta trigger is **lap-level only** (fires on full-lap purple, i.e., beats session best lap time). Live per-sector purple/green/yellow mid-lap is deferred — it needs a sector-completion edge detector that's meaningfully more state to track correctly, and is not needed for a first working version. Note this scope cut, don't silently expand it mid-implementation.
- Claude model: `claude-haiku-4-5-20251001` for both phrasing and Q&A — callouts need to be fast and are simple templated asks, not deep reasoning.
- Wake phrase for Phase 1 is the pretrained `hey_jarvis` openWakeWord model (confirmed working via its GitHub README), not a custom "hey engineer" phrase — training a custom model is separate future work.
- `ANTHROPIC_API_KEY` must be set as an environment variable — never hardcode it.

---

## File Structure

```
C:\Claude\f1-race-engineer\
├── requirements.txt
├── config.py
├── main.py
├── overlay.py
├── telemetry\
│   ├── __init__.py
│   ├── packets.py       # struct formats + parse functions
│   ├── listener.py       # UDP socket loop, dispatches by packet_id
│   ├── state.py           # State dataclass + thread-safe StateTracker
│   └── capture.py         # record/replay raw UDP packets to/from file
├── rules\
│   ├── __init__.py
│   └── engine.py          # Event dataclass + RuleEngine
├── voice\
│   ├── __init__.py
│   ├── phrasing.py        # Claude calls: event_to_line(), answer_question()
│   ├── tts.py              # speak(text) via edge-tts + pygame
│   ├── wakeword.py         # WakeWordListener thread (openwakeword)
│   └── stt.py               # record_question() + transcribe() (faster-whisper)
└── tests\
    ├── test_packets.py
    ├── test_capture.py
    ├── test_state.py
    └── test_engine.py
```

---

### Task 1: Project scaffold + dependencies

**Files:**
- Create: `C:\Claude\f1-race-engineer\requirements.txt`
- Create: `C:\Claude\f1-race-engineer\config.py`
- Create: `C:\Claude\f1-race-engineer\telemetry\__init__.py` (empty)
- Create: `C:\Claude\f1-race-engineer\rules\__init__.py` (empty)
- Create: `C:\Claude\f1-race-engineer\voice\__init__.py` (empty)

**Interfaces:**
- Produces: `config.ANTHROPIC_MODEL`, `config.UDP_LISTEN_IP`, `config.UDP_LISTEN_PORT`, `config.TTS_VOICE`, `config.WAKE_WORD_NAME`, `config.WHISPER_MODEL_SIZE`, `config.get_anthropic_api_key()`

- [ ] **Step 1: Create the project folders and empty `__init__.py` files**

```bash
mkdir -p C:/Claude/f1-race-engineer/telemetry C:/Claude/f1-race-engineer/rules C:/Claude/f1-race-engineer/voice C:/Claude/f1-race-engineer/tests
touch C:/Claude/f1-race-engineer/telemetry/__init__.py C:/Claude/f1-race-engineer/rules/__init__.py C:/Claude/f1-race-engineer/voice/__init__.py C:/Claude/f1-race-engineer/tests/__init__.py
```

- [ ] **Step 2: Write `requirements.txt`**

```
anthropic
edge-tts
pygame
openwakeword
faster-whisper
sounddevice
numpy
pytest
```

- [ ] **Step 3: Install dependencies**

Run: `pip install -r C:/Claude/f1-race-engineer/requirements.txt`
Expected: all packages install without error.

- [ ] **Step 4: Write `config.py`**

```python
import os

ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
UDP_LISTEN_IP = "0.0.0.0"
UDP_LISTEN_PORT = 20777
TTS_VOICE = "en-GB-RyanNeural"
WAKE_WORD_NAME = "hey_jarvis"
WHISPER_MODEL_SIZE = "base.en"


def get_anthropic_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")
    return key
```

- [ ] **Step 5: Set the API key env var for this session and verify**

Run: `$env:ANTHROPIC_API_KEY = "<your key>"; python -c "import config; print(config.get_anthropic_api_key()[:8])"`
Expected: prints the first 8 characters of your key, no error.

- [ ] **Step 6: Commit**

```bash
git init
git add requirements.txt config.py telemetry rules voice tests
git commit -m "Scaffold f1-race-engineer project"
```

---

### Task 2: Packet header parser

**Files:**
- Create: `C:\Claude\f1-race-engineer\telemetry\packets.py`
- Test: `C:\Claude\f1-race-engineer\tests\test_packets.py`

**Interfaces:**
- Produces: `packets.HEADER_FORMAT`, `packets.HEADER_SIZE`, `packets.parse_header(data) -> dict` with keys `packet_format`, `packet_id`, `player_car_index`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_packets.py
import struct
from telemetry import packets


def _build_header(packet_id, player_car_index=0):
    return struct.pack(
        packets.HEADER_FORMAT,
        2025, 25, 1, 5, 1, packet_id,
        123456789, 12.5, 1000, 1000,
        player_car_index, 255,
    )


def test_parse_header_extracts_packet_id_and_player_index():
    data = _build_header(packet_id=2, player_car_index=3) + b"\x00" * 100
    header = packets.parse_header(data)
    assert header["packet_id"] == 2
    assert header["player_car_index"] == 3
    assert header["packet_format"] == 2025
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Claude/f1-race-engineer && pytest tests/test_packets.py -v`
Expected: FAIL — `telemetry.packets` has no attribute `HEADER_FORMAT`

- [ ] **Step 3: Write `telemetry/packets.py` header section**

```python
import struct

# F1 25 UDP telemetry — struct formats verified against MacManley/f1-25-udp
# (github.com/MacManley/f1-25-udp), matching the official F1 25 spec.

HEADER_FORMAT = "<HBBBBBQfIIBB"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 29 bytes


def parse_header(data):
    fields = struct.unpack_from(HEADER_FORMAT, data, 0)
    (packet_format, game_year, game_major, game_minor, packet_version, packet_id,
     session_uid, session_time, frame_id, overall_frame_id,
     player_car_index, secondary_player_car_index) = fields
    return {
        "packet_format": packet_format,
        "packet_id": packet_id,
        "player_car_index": player_car_index,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_packets.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add telemetry/packets.py tests/test_packets.py
git commit -m "Add F1 25 UDP header parser"
```

---

### Task 3: LapData packet parser + gap-ahead/gap-behind

**Files:**
- Modify: `C:\Claude\f1-race-engineer\telemetry\packets.py`
- Modify: `C:\Claude\f1-race-engineer\tests\test_packets.py`

**Interfaces:**
- Consumes: `packets.HEADER_SIZE` (Task 2)
- Produces: `packets.LAP_DATA_FORMAT`, `packets.LAP_DATA_SIZE`, `packets.NUM_CARS` (=22), `packets.parse_lap_data_packet(data, player_car_index) -> (my_lap: dict, gap_ahead_ms: int, gap_behind_ms: int|None)`. `my_lap` has keys `last_lap_time_ms`, `current_lap_time_ms`, `sector1_time_ms`, `sector2_time_ms`, `car_position`, `current_lap_num`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_packets.py

def _build_lap_data_car(last_lap_ms=90000, current_lap_ms=45000, sector1_ms=30000, sector2_ms=30000,
                         delta_front_ms=800, delta_leader_ms=5000, car_position=5, current_lap_num=3):
    return struct.pack(
        packets.LAP_DATA_FORMAT,
        last_lap_ms, current_lap_ms,
        sector1_ms % 60000, sector1_ms // 60000,
        sector2_ms % 60000, sector2_ms // 60000,
        delta_front_ms % 60000, delta_front_ms // 60000,
        delta_leader_ms % 60000, delta_leader_ms // 60000,
        100.0, 200.0, 0.0,
        car_position, current_lap_num,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0,
        250.0, 255,
    )


def test_parse_lap_data_packet_extracts_player_car_and_gaps():
    header = _build_header(packet_id=2, player_car_index=1)
    car_p2_behind_player = _build_lap_data_car(car_position=2, delta_front_ms=750)
    car_player = _build_lap_data_car(car_position=1, delta_front_ms=0)
    filler_cars = [_build_lap_data_car(car_position=p) for p in range(3, 23)]
    cars = [car_p2_behind_player, car_player] + filler_cars
    data = header + b"".join(cars) + b"\xff\xff"

    my_lap, gap_ahead_ms, gap_behind_ms = packets.parse_lap_data_packet(data, player_car_index=1)

    assert my_lap["car_position"] == 1
    assert my_lap["current_lap_num"] == 3
    assert gap_ahead_ms == 0
    assert gap_behind_ms == 750
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_packets.py -v`
Expected: FAIL — no attribute `LAP_DATA_FORMAT`

- [ ] **Step 3: Add LapData parsing to `telemetry/packets.py`**

```python
# append to telemetry/packets.py

LAP_DATA_FORMAT = "<IIHBHBHBHBfffBBBBBBBBBBBBBBBHHBfB"
LAP_DATA_SIZE = struct.calcsize(LAP_DATA_FORMAT)  # 57 bytes
NUM_CARS = 22


def _combine_delta(ms_part, minutes_part):
    return minutes_part * 60000 + ms_part


def parse_lap_data_packet(data, player_car_index):
    cars = []
    offset = HEADER_SIZE
    for _ in range(NUM_CARS):
        f = struct.unpack_from(LAP_DATA_FORMAT, data, offset)
        cars.append({
            "last_lap_time_ms": f[0],
            "current_lap_time_ms": f[1],
            "sector1_time_ms": _combine_delta(f[2], f[3]),
            "sector2_time_ms": _combine_delta(f[4], f[5]),
            "delta_to_car_in_front_ms": _combine_delta(f[6], f[7]),
            "delta_to_race_leader_ms": _combine_delta(f[8], f[9]),
            "car_position": f[13],
            "current_lap_num": f[14],
        })
        offset += LAP_DATA_SIZE

    my_lap = cars[player_car_index]
    gap_ahead_ms = my_lap["delta_to_car_in_front_ms"]

    gap_behind_ms = None
    my_position = my_lap["car_position"]
    for car in cars:
        if car["car_position"] == my_position + 1:
            gap_behind_ms = car["delta_to_car_in_front_ms"]
            break

    return my_lap, gap_ahead_ms, gap_behind_ms
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_packets.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add telemetry/packets.py tests/test_packets.py
git commit -m "Add LapData parser with gap-ahead/gap-behind computation"
```

---

### Task 4: CarStatus packet parser (fuel)

**Files:**
- Modify: `C:\Claude\f1-race-engineer\telemetry\packets.py`
- Modify: `C:\Claude\f1-race-engineer\tests\test_packets.py`

**Interfaces:**
- Consumes: `packets.HEADER_SIZE`, `packets.NUM_CARS` (Tasks 2-3)
- Produces: `packets.CAR_STATUS_FORMAT`, `packets.CAR_STATUS_SIZE`, `packets.parse_car_status_packet(data, player_car_index) -> (fuel_in_tank: float, fuel_remaining_laps: float)`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_packets.py

def _build_car_status_car(fuel_in_tank=45.5, fuel_remaining_laps=12.3):
    return struct.pack(
        packets.CAR_STATUS_FORMAT,
        0, 0, 1, 50, 0,
        fuel_in_tank, 110.0, fuel_remaining_laps,
        15000, 4000,
        8, 1, 1500,
        16, 16, 5,
        0,
        500.0, 300.0, 4000000.0,
        0,
        100.0, 50.0, 150.0,
        0,
    )


def test_parse_car_status_packet_extracts_fuel_for_player_car():
    header = _build_header(packet_id=7, player_car_index=2)
    cars = [_build_car_status_car() for _ in range(22)]
    cars[2] = _build_car_status_car(fuel_in_tank=30.0, fuel_remaining_laps=3.0)
    data = header + b"".join(cars)

    fuel_in_tank, fuel_remaining_laps = packets.parse_car_status_packet(data, player_car_index=2)

    assert fuel_in_tank == 30.0
    assert fuel_remaining_laps == 3.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_packets.py -v`
Expected: FAIL — no attribute `CAR_STATUS_FORMAT`

- [ ] **Step 3: Add CarStatus parsing to `telemetry/packets.py`**

```python
# append to telemetry/packets.py

CAR_STATUS_FORMAT = "<BBBBBfffHHBBHBBBbfffBfffB"
CAR_STATUS_SIZE = struct.calcsize(CAR_STATUS_FORMAT)  # 55 bytes


def parse_car_status_packet(data, player_car_index):
    offset = HEADER_SIZE + player_car_index * CAR_STATUS_SIZE
    f = struct.unpack_from(CAR_STATUS_FORMAT, data, offset)
    fuel_in_tank = f[5]
    fuel_remaining_laps = f[7]
    return fuel_in_tank, fuel_remaining_laps
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_packets.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add telemetry/packets.py tests/test_packets.py
git commit -m "Add CarStatus parser for fuel fields"
```

---

### Task 5: CarDamage packet parser (tyre wear)

**Files:**
- Modify: `C:\Claude\f1-race-engineer\telemetry\packets.py`
- Modify: `C:\Claude\f1-race-engineer\tests\test_packets.py`

**Interfaces:**
- Consumes: `packets.HEADER_SIZE`, `packets.NUM_CARS`
- Produces: `packets.CAR_DAMAGE_FORMAT`, `packets.CAR_DAMAGE_SIZE`, `packets.parse_car_damage_packet(data, player_car_index) -> list[float]` (4 tyre wear percentages)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_packets.py

def _build_car_damage_car(tyres_wear=(10.0, 12.0, 8.0, 9.0)):
    zeros_30 = (0,) * 30
    return struct.pack(packets.CAR_DAMAGE_FORMAT, *tyres_wear, *zeros_30)


def test_parse_car_damage_packet_extracts_tyre_wear_for_player_car():
    header = _build_header(packet_id=10, player_car_index=5)
    cars = [_build_car_damage_car() for _ in range(22)]
    cars[5] = _build_car_damage_car(tyres_wear=(40.0, 42.0, 38.0, 39.0))
    data = header + b"".join(cars)

    tyres_wear = packets.parse_car_damage_packet(data, player_car_index=5)

    assert tyres_wear == [40.0, 42.0, 38.0, 39.0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_packets.py -v`
Expected: FAIL — no attribute `CAR_DAMAGE_FORMAT`

- [ ] **Step 3: Add CarDamage parsing to `telemetry/packets.py`**

```python
# append to telemetry/packets.py

CAR_DAMAGE_FORMAT = "<4f4B4B4B18B"
CAR_DAMAGE_SIZE = struct.calcsize(CAR_DAMAGE_FORMAT)  # 46 bytes


def parse_car_damage_packet(data, player_car_index):
    offset = HEADER_SIZE + player_car_index * CAR_DAMAGE_SIZE
    f = struct.unpack_from(CAR_DAMAGE_FORMAT, data, offset)
    return list(f[0:4])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_packets.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add telemetry/packets.py tests/test_packets.py
git commit -m "Add CarDamage parser for tyre wear"
```

---

### Task 6: UDP capture/replay tool

**Files:**
- Create: `C:\Claude\f1-race-engineer\telemetry\capture.py`
- Create: `C:\Claude\f1-race-engineer\tests\test_capture.py`

**Interfaces:**
- Produces: `capture.write_packet(f, data: bytes)`, `capture.record_session(output_path, ip, port, duration_seconds)`, `capture.replay_session(input_path, on_packet: callable, delay_seconds=0.0)`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_capture.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_capture.py -v`
Expected: FAIL — `telemetry.capture` module not found

- [ ] **Step 3: Write `telemetry/capture.py`**

```python
import socket
import struct
import time


def write_packet(f, data):
    f.write(struct.pack("<I", len(data)))
    f.write(data)


def record_session(output_path, ip="0.0.0.0", port=20777, duration_seconds=60):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((ip, port))
    sock.settimeout(1.0)
    end_time = time.time() + duration_seconds
    with open(output_path, "wb") as f:
        while time.time() < end_time:
            try:
                data, _ = sock.recvfrom(2048)
            except socket.timeout:
                continue
            write_packet(f, data)
    sock.close()


def replay_session(input_path, on_packet, delay_seconds=0.0):
    with open(input_path, "rb") as f:
        while True:
            size_bytes = f.read(4)
            if len(size_bytes) < 4:
                break
            (size,) = struct.unpack("<I", size_bytes)
            data = f.read(size)
            on_packet(data)
            if delay_seconds:
                time.sleep(delay_seconds)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_capture.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add telemetry/capture.py tests/test_capture.py
git commit -m "Add UDP session capture/replay tool for offline dev"
```

---

### Task 7: State tracker

**Files:**
- Create: `C:\Claude\f1-race-engineer\telemetry\state.py`
- Create: `C:\Claude\f1-race-engineer\tests\test_state.py`

**Interfaces:**
- Produces: `state.State` dataclass with fields `last_lap_time_ms`, `current_lap_time_ms`, `sector1_time_ms`, `sector2_time_ms`, `best_lap_time_ms`, `car_position`, `current_lap_num`, `gap_ahead_ms`, `gap_behind_ms`, `fuel_in_tank`, `fuel_remaining_laps`, `tyres_wear` (list of 4 floats); `state.StateTracker` with methods `update_lap_data(my_lap: dict, gap_ahead_ms, gap_behind_ms)`, `update_car_status(fuel_in_tank, fuel_remaining_laps)`, `update_car_damage(tyres_wear)`, `snapshot() -> State`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_state.py
from telemetry.state import StateTracker


def test_update_lap_data_tracks_best_lap_time():
    tracker = StateTracker()
    tracker.update_lap_data(
        {"last_lap_time_ms": 0, "current_lap_time_ms": 20000, "sector1_time_ms": 0,
         "sector2_time_ms": 0, "car_position": 3, "current_lap_num": 1},
        gap_ahead_ms=1000, gap_behind_ms=2000,
    )
    tracker.update_lap_data(
        {"last_lap_time_ms": 92000, "current_lap_time_ms": 5000, "sector1_time_ms": 0,
         "sector2_time_ms": 0, "car_position": 3, "current_lap_num": 2},
        gap_ahead_ms=900, gap_behind_ms=2100,
    )

    snapshot = tracker.snapshot()

    assert snapshot.last_lap_time_ms == 92000
    assert snapshot.best_lap_time_ms == 92000
    assert snapshot.current_lap_num == 2
    assert snapshot.gap_ahead_ms == 900
    assert snapshot.gap_behind_ms == 2100


def test_update_car_status_and_damage_populate_snapshot():
    tracker = StateTracker()
    tracker.update_car_status(fuel_in_tank=25.0, fuel_remaining_laps=4.0)
    tracker.update_car_damage(tyres_wear=[10.0, 11.0, 9.0, 12.0])

    snapshot = tracker.snapshot()

    assert snapshot.fuel_in_tank == 25.0
    assert snapshot.fuel_remaining_laps == 4.0
    assert snapshot.tyres_wear == [10.0, 11.0, 9.0, 12.0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_state.py -v`
Expected: FAIL — `telemetry.state` module not found

- [ ] **Step 3: Write `telemetry/state.py`**

```python
import dataclasses
import threading


@dataclasses.dataclass
class State:
    last_lap_time_ms: int = 0
    current_lap_time_ms: int = 0
    sector1_time_ms: int = 0
    sector2_time_ms: int = 0
    best_lap_time_ms: int = None
    car_position: int = 0
    current_lap_num: int = 0
    gap_ahead_ms: int = None
    gap_behind_ms: int = None
    fuel_in_tank: float = 0.0
    fuel_remaining_laps: float = 0.0
    tyres_wear: list = dataclasses.field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])


class StateTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = State()

    def update_lap_data(self, my_lap, gap_ahead_ms, gap_behind_ms):
        with self._lock:
            s = self._state
            s.last_lap_time_ms = my_lap["last_lap_time_ms"]
            s.current_lap_time_ms = my_lap["current_lap_time_ms"]
            s.sector1_time_ms = my_lap["sector1_time_ms"]
            s.sector2_time_ms = my_lap["sector2_time_ms"]
            s.car_position = my_lap["car_position"]
            s.current_lap_num = my_lap["current_lap_num"]
            s.gap_ahead_ms = gap_ahead_ms
            s.gap_behind_ms = gap_behind_ms
            if s.last_lap_time_ms and (s.best_lap_time_ms is None or s.last_lap_time_ms < s.best_lap_time_ms):
                s.best_lap_time_ms = s.last_lap_time_ms

    def update_car_status(self, fuel_in_tank, fuel_remaining_laps):
        with self._lock:
            self._state.fuel_in_tank = fuel_in_tank
            self._state.fuel_remaining_laps = fuel_remaining_laps

    def update_car_damage(self, tyres_wear):
        with self._lock:
            self._state.tyres_wear = tyres_wear

    def snapshot(self):
        with self._lock:
            return dataclasses.replace(self._state)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_state.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add telemetry/state.py tests/test_state.py
git commit -m "Add thread-safe State tracker"
```

---

### Task 8: UDP listener

**Files:**
- Create: `C:\Claude\f1-race-engineer\telemetry\listener.py`

**Interfaces:**
- Consumes: `packets.parse_header`, `packets.parse_lap_data_packet`, `packets.parse_car_status_packet`, `packets.parse_car_damage_packet` (Tasks 2-5); `state.StateTracker` (Task 7)
- Produces: `listener.TelemetryListener(state_tracker, ip, port, capture_writer=None)` with `.start()` (blocking loop) and `.stop()`

No test for this task — it needs a live socket/game to exercise meaningfully; correctness of the parsing it calls is already covered by Task 2-5 unit tests. Verified end-to-end in Task 15.

- [ ] **Step 1: Write `telemetry/listener.py`**

```python
import socket
import time
from telemetry import packets

PACKET_ID_LAP_DATA = 2
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
        header = packets.parse_header(data)
        player_car_index = header["player_car_index"]
        packet_id = header["packet_id"]
        if packet_id == PACKET_ID_LAP_DATA:
            my_lap, gap_ahead_ms, gap_behind_ms = packets.parse_lap_data_packet(data, player_car_index)
            self.state_tracker.update_lap_data(my_lap, gap_ahead_ms, gap_behind_ms)
        elif packet_id == PACKET_ID_CAR_STATUS:
            fuel_in_tank, fuel_remaining_laps = packets.parse_car_status_packet(data, player_car_index)
            self.state_tracker.update_car_status(fuel_in_tank, fuel_remaining_laps)
        elif packet_id == PACKET_ID_CAR_DAMAGE:
            tyres_wear = packets.parse_car_damage_packet(data, player_car_index)
            self.state_tracker.update_car_damage(tyres_wear)
```

- [ ] **Step 2: Commit**

```bash
git add telemetry/listener.py
git commit -m "Add UDP telemetry listener with packet dispatch"
```

---

### Task 9: Rule engine — lap completion (purple lap)

**Files:**
- Create: `C:\Claude\f1-race-engineer\rules\engine.py`
- Create: `C:\Claude\f1-race-engineer\tests\test_engine.py`

**Interfaces:**
- Consumes: `state.State` (Task 7)
- Produces: `engine.Event` dataclass (`kind: str`, `data: dict`); `engine.RuleEngine` with `.check_lap_completion(state) -> list[Event]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_engine.py
from telemetry.state import State
from rules.engine import RuleEngine


def test_lap_completion_fires_purple_event_on_new_best():
    engine = RuleEngine()
    lap1 = State(current_lap_num=1, last_lap_time_ms=0)
    lap2 = State(current_lap_num=2, last_lap_time_ms=92000, best_lap_time_ms=92000)
    lap3 = State(current_lap_num=3, last_lap_time_ms=90500, best_lap_time_ms=90500)
    lap4 = State(current_lap_num=4, last_lap_time_ms=91000, best_lap_time_ms=90500)

    events1 = engine.check_lap_completion(lap1)
    events2 = engine.check_lap_completion(lap2)
    events3 = engine.check_lap_completion(lap3)
    events4 = engine.check_lap_completion(lap4)

    assert events1 == []
    assert events2 == []  # first completed lap, nothing to beat yet
    assert len(events3) == 1
    assert events3[0].kind == "lap_purple"
    assert events3[0].data["lap_time_ms"] == 90500
    assert events4 == []  # slower lap, no event
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_engine.py -v`
Expected: FAIL — `rules.engine` module not found

- [ ] **Step 3: Write `rules/engine.py` (lap completion section)**

```python
import dataclasses


@dataclasses.dataclass
class Event:
    kind: str
    data: dict


class RuleEngine:
    def __init__(self):
        self._last_lap_num_seen = None
        self._prev_best_lap_time_ms = None
        self._fired_tyre_thresholds = set()
        self._fired_fuel_warning = False
        self._last_gap_ahead_alert_lap = None
        self._last_gap_behind_alert_lap = None

    def check_lap_completion(self, state):
        events = []
        lap_just_completed = (
            self._last_lap_num_seen is not None
            and state.current_lap_num != self._last_lap_num_seen
        )
        if lap_just_completed:
            if (
                state.last_lap_time_ms
                and self._prev_best_lap_time_ms is not None
                and state.last_lap_time_ms < self._prev_best_lap_time_ms
            ):
                events.append(Event("lap_purple", {"lap_time_ms": state.last_lap_time_ms}))
            self._fired_tyre_thresholds = set()
        self._last_lap_num_seen = state.current_lap_num
        self._prev_best_lap_time_ms = state.best_lap_time_ms
        return events
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rules/engine.py tests/test_engine.py
git commit -m "Add rule engine: purple lap detection"
```

---

### Task 10: Rule engine — tyre wear + fuel

**Files:**
- Modify: `C:\Claude\f1-race-engineer\rules\engine.py`
- Modify: `C:\Claude\f1-race-engineer\tests\test_engine.py`

**Interfaces:**
- Produces: `RuleEngine.check_tyre_and_fuel(state) -> list[Event]` — emits `Event("tyre_wear", {"threshold": int, "remaining_pct": float})` once per threshold per lap (30/15/5 remaining %), and `Event("fuel_critical", {"fuel_remaining_laps": float})` once when fuel drops under 2 laps remaining.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_engine.py
from telemetry.state import State
from rules.engine import RuleEngine


def test_tyre_wear_fires_once_per_threshold():
    engine = RuleEngine()
    state = State(tyres_wear=[65.0, 60.0, 55.0, 50.0])  # worst = 65% worn -> 35% remaining

    events_first = engine.check_tyre_and_fuel(state)
    events_second = engine.check_tyre_and_fuel(state)  # same state, should not refire

    assert events_first == []  # 35% remaining hasn't crossed 30 yet
    assert events_second == []

    worn_more = State(tyres_wear=[72.0, 60.0, 55.0, 50.0])  # 28% remaining -> crosses 30
    events_third = engine.check_tyre_and_fuel(worn_more)
    events_fourth = engine.check_tyre_and_fuel(worn_more)

    assert len(events_third) == 1
    assert events_third[0].kind == "tyre_wear"
    assert events_third[0].data["threshold"] == 30
    assert events_fourth == []  # already fired for this threshold


def test_fuel_critical_fires_once_when_below_two_laps():
    engine = RuleEngine()
    plenty_fuel = State(fuel_remaining_laps=5.0)
    low_fuel = State(fuel_remaining_laps=1.5)

    events_ok = engine.check_tyre_and_fuel(plenty_fuel)
    events_low_first = engine.check_tyre_and_fuel(low_fuel)
    events_low_second = engine.check_tyre_and_fuel(low_fuel)

    assert events_ok == []
    assert len(events_low_first) == 1
    assert events_low_first[0].kind == "fuel_critical"
    assert events_low_second == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_engine.py -v`
Expected: FAIL — `RuleEngine` has no attribute `check_tyre_and_fuel`

- [ ] **Step 3: Add to `rules/engine.py`**

```python
# append inside RuleEngine class in rules/engine.py

    def check_tyre_and_fuel(self, state):
        events = []
        worst_tyre_wear = max(state.tyres_wear)
        remaining_pct = 100 - worst_tyre_wear
        for threshold in (30, 15, 5):
            if remaining_pct <= threshold and threshold not in self._fired_tyre_thresholds:
                events.append(Event("tyre_wear", {"threshold": threshold, "remaining_pct": remaining_pct}))
                self._fired_tyre_thresholds.add(threshold)

        if state.fuel_remaining_laps < 2 and not self._fired_fuel_warning:
            events.append(Event("fuel_critical", {"fuel_remaining_laps": state.fuel_remaining_laps}))
            self._fired_fuel_warning = True
        elif state.fuel_remaining_laps >= 2:
            self._fired_fuel_warning = False

        return events
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_engine.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add rules/engine.py tests/test_engine.py
git commit -m "Add rule engine: tyre wear and fuel thresholds"
```

---

### Task 11: Rule engine — gap closing

**Files:**
- Modify: `C:\Claude\f1-race-engineer\rules\engine.py`
- Modify: `C:\Claude\f1-race-engineer\tests\test_engine.py`

**Interfaces:**
- Produces: `RuleEngine.check_gaps(state) -> list[Event]` — emits `Event("gap_closing_ahead", {"gap_ms": int})` or `Event("gap_closing_behind", {"gap_ms": int})` when the respective gap drops under 1000ms, at most once per lap per direction.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_engine.py

def test_gap_closing_fires_once_per_lap_per_direction():
    engine = RuleEngine()
    close_ahead = State(current_lap_num=1, gap_ahead_ms=800, gap_behind_ms=5000)

    events_first = engine.check_gaps(close_ahead)
    events_second = engine.check_gaps(close_ahead)  # same lap, no refire

    assert len(events_first) == 1
    assert events_first[0].kind == "gap_closing_ahead"
    assert events_first[0].data["gap_ms"] == 800
    assert events_second == []

    next_lap_still_close = State(current_lap_num=2, gap_ahead_ms=700, gap_behind_ms=5000)
    events_next_lap = engine.check_gaps(next_lap_still_close)

    assert len(events_next_lap) == 1  # new lap, allowed to fire again
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_engine.py -v`
Expected: FAIL — `RuleEngine` has no attribute `check_gaps`

- [ ] **Step 3: Add to `rules/engine.py`**

```python
# append inside RuleEngine class in rules/engine.py

    def check_gaps(self, state):
        events = []
        if state.gap_ahead_ms is not None and state.gap_ahead_ms < 1000:
            if self._last_gap_ahead_alert_lap != state.current_lap_num:
                events.append(Event("gap_closing_ahead", {"gap_ms": state.gap_ahead_ms}))
                self._last_gap_ahead_alert_lap = state.current_lap_num
        if state.gap_behind_ms is not None and state.gap_behind_ms < 1000:
            if self._last_gap_behind_alert_lap != state.current_lap_num:
                events.append(Event("gap_closing_behind", {"gap_ms": state.gap_behind_ms}))
                self._last_gap_behind_alert_lap = state.current_lap_num
        return events
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_engine.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add rules/engine.py tests/test_engine.py
git commit -m "Add rule engine: gap-closing detection"
```

---

### Task 12: Claude phrasing module

**Files:**
- Create: `C:\Claude\f1-race-engineer\voice\phrasing.py`

**Interfaces:**
- Consumes: `config.ANTHROPIC_MODEL`, `config.get_anthropic_api_key()` (Task 1); `rules.engine.Event` (Task 9); `telemetry.state.State` (Task 7)
- Produces: `phrasing.event_to_line(event: Event) -> str`, `phrasing.answer_question(question: str, state: State) -> str`

No automated test — this task calls the live Claude API, so it's manually verified in Task 17's end-to-end check. The canned-fallback path (`_canned_line`) is deterministic and testable.

- [ ] **Step 1: Write `voice/phrasing.py`**

```python
import anthropic
import config

_client = anthropic.Anthropic(api_key=config.get_anthropic_api_key())

CANNED_LINES = {
    "lap_purple": "Purple lap! New session best, {lap_time_ms} milliseconds.",
    "tyre_wear": "Tyres at {remaining_pct:.0f} percent, box window opening.",
    "fuel_critical": "Fuel critical, {fuel_remaining_laps:.1f} laps left, look after it.",
    "gap_closing_ahead": "Car ahead, gap closing, {gap_ms} milliseconds.",
    "gap_closing_behind": "Car behind closing, {gap_ms} milliseconds.",
}


def _canned_line(event):
    template = CANNED_LINES.get(event.kind, "Note: {kind}")
    try:
        return template.format(kind=event.kind, **event.data)
    except (KeyError, ValueError):
        return "Note: {}".format(event.kind)


def event_to_line(event):
    prompt = (
        "You are a terse F1 race engineer speaking on team radio. "
        f"React to this event in ONE short sentence, no filler: {event.kind} with data {event.data}."
    )
    try:
        resp = _client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=60,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception:
        return _canned_line(event)


def answer_question(question, state):
    context = (
        f"Current state: lap {state.current_lap_num}, position {state.car_position}, "
        f"fuel {state.fuel_in_tank:.1f}kg ({state.fuel_remaining_laps:.1f} laps left), "
        f"worst tyre wear {max(state.tyres_wear):.0f}%, "
        f"gap ahead {state.gap_ahead_ms}ms, gap behind {state.gap_behind_ms}ms."
    )
    prompt = (
        f"You are a terse F1 race engineer on team radio. {context}\n"
        f'Driver asks: "{question}"\nAnswer in one or two short sentences.'
    )
    try:
        resp = _client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception:
        return "Radio's breaking up, say again."
```

- [ ] **Step 2: Manually verify the canned fallback**

Run: `cd C:/Claude/f1-race-engineer && python -c "from rules.engine import Event; from voice.phrasing import _canned_line; print(_canned_line(Event('tyre_wear', {'threshold': 30, 'remaining_pct': 28.0})))"`
Expected: prints `Tyres at 28 percent, box window opening.`

- [ ] **Step 3: Commit**

```bash
git add voice/phrasing.py
git commit -m "Add Claude phrasing module with canned-line fallback"
```

---

### Task 13: TTS playback

**Files:**
- Create: `C:\Claude\f1-race-engineer\voice\tts.py`

**Interfaces:**
- Consumes: `config.TTS_VOICE`
- Produces: `tts.speak(text: str)` — blocks until playback finishes

- [ ] **Step 1: Write `voice/tts.py`**

```python
import asyncio
import os
import tempfile
import edge_tts
import pygame
import config

pygame.mixer.init()


async def _synthesize(text, mp3_path):
    communicate = edge_tts.Communicate(text, config.TTS_VOICE)
    await communicate.save(mp3_path)


def speak(text):
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        mp3_path = f.name
    try:
        asyncio.run(_synthesize(text, mp3_path))
        pygame.mixer.music.load(mp3_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.wait(100)
    finally:
        os.remove(mp3_path)
```

- [ ] **Step 2: Manually verify audio plays**

Run: `cd C:/Claude/f1-race-engineer && python -c "from voice.tts import speak; speak('Box box box, this lap.')"`
Expected: hear the line spoken through the laptop speakers/headphones.

- [ ] **Step 3: Commit**

```bash
git add voice/tts.py
git commit -m "Add edge-tts + pygame voice playback"
```

---

### Task 14: Wake-word listener

**Files:**
- Create: `C:\Claude\f1-race-engineer\voice\wakeword.py`

**Interfaces:**
- Consumes: `config.WAKE_WORD_NAME`
- Produces: `wakeword.WakeWordListener(on_wake: callable)` — a `threading.Thread` subclass; `.start()` begins listening, `.stop()` ends it, `on_wake()` is called (with no args) each time the wake phrase is detected.

- [ ] **Step 1: Write `voice/wakeword.py`**

```python
import threading
import openwakeword
from openwakeword.model import Model
import sounddevice as sd
import config

SAMPLE_RATE = 16000
CHUNK_SIZE = 1280  # 80ms, openWakeWord's recommended frame size


class WakeWordListener(threading.Thread):
    def __init__(self, on_wake):
        super().__init__(daemon=True)
        self.on_wake = on_wake
        self._stop = threading.Event()
        openwakeword.utils.download_models()
        self._model = Model(
            wakeword_models=[f"{config.WAKE_WORD_NAME}.onnx"],
            inference_framework="onnx",
        )

    def run(self):
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=CHUNK_SIZE) as stream:
            while not self._stop.is_set():
                audio_chunk, _ = stream.read(CHUNK_SIZE)
                prediction = self._model.predict(audio_chunk[:, 0])
                score = prediction.get(config.WAKE_WORD_NAME, 0.0)
                if score > 0.5:
                    self.on_wake()

    def stop(self):
        self._stop.set()
```

- [ ] **Step 2: Manually verify wake detection**

Run: `cd C:/Claude/f1-race-engineer && python -c "from voice.wakeword import WakeWordListener; import time; w = WakeWordListener(on_wake=lambda: print('WAKE DETECTED')); w.start(); time.sleep(15)"`
Expected: say "hey jarvis" within 15 seconds, see `WAKE DETECTED` printed.

- [ ] **Step 3: Commit**

```bash
git add voice/wakeword.py
git commit -m "Add openWakeWord listener thread"
```

---

### Task 15: STT + Q&A recording pipeline

**Files:**
- Create: `C:\Claude\f1-race-engineer\voice\stt.py`

**Interfaces:**
- Consumes: `config.WHISPER_MODEL_SIZE`
- Produces: `stt.record_question() -> str` (path to a temp WAV file, records until ~2s of silence or 6s max), `stt.transcribe(wav_path: str) -> str`

- [ ] **Step 1: Write `voice/stt.py`**

```python
import tempfile
import wave
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
import config

_model = WhisperModel(config.WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")

SAMPLE_RATE = 16000
CHUNK_FRAMES = 1024
SILENCE_AMPLITUDE_THRESHOLD = 500
SILENCE_CHUNKS_TO_STOP = 20  # ~1.3s of quiet
MAX_RECORD_SECONDS = 6


def record_question():
    frames = []
    silence_chunks = 0
    max_chunks = int(MAX_RECORD_SECONDS * SAMPLE_RATE / CHUNK_FRAMES)
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16") as stream:
        for _ in range(max_chunks):
            chunk, _ = stream.read(CHUNK_FRAMES)
            frames.append(chunk.copy())
            if np.abs(chunk).mean() < SILENCE_AMPLITUDE_THRESHOLD:
                silence_chunks += 1
                if silence_chunks > SILENCE_CHUNKS_TO_STOP:
                    break
            else:
                silence_chunks = 0

    audio = np.concatenate(frames)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())
    return wav_path


def transcribe(wav_path):
    segments, _ = _model.transcribe(wav_path)
    return " ".join(seg.text for seg in segments).strip()
```

- [ ] **Step 2: Manually verify recording + transcription**

Run: `cd C:/Claude/f1-race-engineer && python -c "from voice.stt import record_question, transcribe; path = record_question(); print(transcribe(path))"`
Expected: say "how many laps of fuel do I have" after running, see the transcribed text printed reasonably accurately.

- [ ] **Step 3: Commit**

```bash
git add voice/stt.py
git commit -m "Add speech-to-text recording and transcription"
```

---

### Task 16: Overlay window

**Files:**
- Create: `C:\Claude\f1-race-engineer\overlay.py`

**Interfaces:**
- Produces: `overlay.OverlayWindow` with `.show_message(text: str)` (thread-safe, callable from any thread) and `.run()` (blocking, must be called from the main thread)

- [ ] **Step 1: Write `overlay.py`**

```python
import queue
import tkinter as tk


class OverlayWindow:
    def __init__(self):
        self._queue = queue.Queue()
        self._root = tk.Tk()
        self._root.title("Race Engineer")
        self._root.attributes("-topmost", True)
        self._root.geometry("500x100+50+50")
        self._label = tk.Label(self._root, text="", font=("Consolas", 14), wraplength=480, justify="left")
        self._label.pack(padx=10, pady=10)
        self._poll()

    def show_message(self, text):
        self._queue.put(text)

    def _poll(self):
        try:
            while True:
                text = self._queue.get_nowait()
                self._label.config(text=text)
        except queue.Empty:
            pass
        self._root.after(200, self._poll)

    def run(self):
        self._root.mainloop()
```

- [ ] **Step 2: Manually verify the window updates from a background thread**

Run: `cd C:/Claude/f1-race-engineer && python -c "
import threading, time
from overlay import OverlayWindow
o = OverlayWindow()
def updater():
    time.sleep(2)
    o.show_message('Box this lap, box box box.')
threading.Thread(target=updater, daemon=True).start()
o.run()
"`
Expected: window appears, shows the message 2 seconds later. Close the window to exit.

- [ ] **Step 3: Commit**

```bash
git add overlay.py
git commit -m "Add always-on-top text overlay window"
```

---

### Task 17: Main orchestrator

**Files:**
- Create: `C:\Claude\f1-race-engineer\main.py`

**Interfaces:**
- Consumes: everything from Tasks 1-16

- [ ] **Step 1: Write `main.py`**

```python
import threading
import time
from telemetry.state import StateTracker
from telemetry.listener import TelemetryListener
from rules.engine import RuleEngine
from voice.phrasing import event_to_line, answer_question
from voice.tts import speak
from voice.wakeword import WakeWordListener
from voice.stt import record_question, transcribe
from overlay import OverlayWindow
import config


def run_telemetry_loop(state_tracker, rule_engine, overlay):
    listener = TelemetryListener(state_tracker, ip=config.UDP_LISTEN_IP, port=config.UDP_LISTEN_PORT)
    threading.Thread(target=listener.start, daemon=True).start()

    while True:
        state = state_tracker.snapshot()
        events = []
        events += rule_engine.check_lap_completion(state)
        events += rule_engine.check_tyre_and_fuel(state)
        events += rule_engine.check_gaps(state)
        for event in events:
            line = event_to_line(event)
            overlay.show_message(line)
            speak(line)
        time.sleep(0.5)


def on_wake_word(state_tracker, overlay):
    wav_path = record_question()
    question = transcribe(wav_path)
    if not question:
        return
    state = state_tracker.snapshot()
    answer = answer_question(question, state)
    overlay.show_message(answer)
    speak(answer)


def main():
    state_tracker = StateTracker()
    rule_engine = RuleEngine()
    overlay = OverlayWindow()

    threading.Thread(
        target=run_telemetry_loop, args=(state_tracker, rule_engine, overlay), daemon=True
    ).start()

    wake_listener = WakeWordListener(on_wake=lambda: on_wake_word(state_tracker, overlay))
    wake_listener.start()

    overlay.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add main.py
git commit -m "Add main orchestrator wiring telemetry, rules, and voice"
```

---

### Task 18: End-to-end manual verification (live game)

No new files — this is a manual test pass with the real game before calling Phase 1 done.

- [ ] **Step 1: Confirm game-side settings**

On the game PC: F1 25 → Telemetry Settings → UDP Telemetry On, IP `192.168.0.115`, Port `20777`, Send Rate 20Hz, Format 2025, Your Telemetry = Public.

- [ ] **Step 2: Start the app on the laptop**

Run: `cd C:/Claude/f1-race-engineer && $env:ANTHROPIC_API_KEY = "<your key>"; python main.py`
Expected: overlay window appears, console shows no `[telemetry] no packets received` warning once you're in a session on track.

- [ ] **Step 3: Drive a few laps in Time Trial, verify each Phase 1 trigger fires**

- Beat your best lap time → hear + see a purple-lap callout.
- Run tyres down (long run or high wear setting) → hear a tyre-wear callout as remaining % crosses 30/15/5.
- Let fuel run low (or check in a race with limited fuel) → hear a fuel-critical callout under 2 laps remaining.
- In a race with AI cars, close to within ~1 second of the car ahead/behind → hear a gap-closing callout.

- [ ] **Step 4: Verify wake-word Q&A**

Say "hey jarvis" while driving, then ask a question ("how much fuel do I have left?"). Expected: overlay shows the transcribed answer, hear it spoken back.

- [ ] **Step 5: Verify fallback behavior**

Temporarily set an invalid `ANTHROPIC_API_KEY` and trigger an event — expected: still hear/see the canned-template line, app doesn't crash. Restore the correct key afterward.

- [ ] **Step 6: Commit any fixes found during manual testing, then tag Phase 1 done**

```bash
git add -A
git commit -m "Phase 1 manual verification pass"
```

---

## Self-Review Notes

- **Spec coverage:** all 3 Phase 1 triggers (lap delta, tyre/fuel, gap) implemented (Tasks 9-11); wake-word Q&A implemented (Tasks 14-15, 17); voice output implemented (Task 13); overlay implemented (Task 16); error handling — no-telemetry warning (Task 8), Claude API fallback (Task 12), mic/STT failure is naturally a no-op in `on_wake_word` if `transcribe` returns empty text.
- **Known scope cut carried from Global Constraints:** lap/sector trigger is lap-level only, not live per-sector purple/green — flagged, not silently dropped.
- **Struct byte layouts:** verified against a real, maintained F1 25 telemetry parser repository rather than assumed from memory — reduces (but doesn't eliminate) risk of a field mismatch; Task 18 catches any remaining mismatch against the live game.
