"""ZeroMQ bridge for the Leap Motion Controller LM-010 (Ultraleap Gemini / LeapC).

Sockets
  PUB  tcp://*:5555          (--bind)     hand tracking stream
       topics: leap.frame    full frame as compact JSON (~110 fps with hands)
               leap.palm     small JSON per hand (palm, pinch, grab) for fast consumers
               leap.status   connection / device / mode changes
  REP  tcp://127.0.0.1:5556  (--control)  control channel (JSON)
       {"command": "get_status"}
       {"command": "set_tracking_mode", "mode": "desktop" | "screentop" | "hmd"}

Every message is multipart [topic, json] and contains "t_pub_us"
(publisher wall clock in microseconds) so consumers can measure latency.

Threading model: LeapC delivers events in its own poll thread. The listener
only puts them into a bounded queue; the PUB socket is used exclusively by the
main thread (ZeroMQ sockets are not thread-safe).

--simulate generates synthetic hands with the same message schema, so every
consumer can be developed and tested without the device.
"""

import argparse
import json
import math
import os
import queue
import signal
import threading
import time

import zmq

EVENTS: "queue.Queue[tuple[str, dict]]" = queue.Queue(maxsize=512)
STATE = {"connected": False, "device": None, "mode": "desktop", "frames": 0, "simulated": False}


def now_us() -> int:
    return time.time_ns() // 1000


def emit(topic: str, payload: dict) -> None:
    """Thread-safe hand-over to the publishing thread; drops when overloaded."""
    try:
        EVENTS.put_nowait((topic, payload))
    except queue.Full:
        pass  # never block the tracking thread - newer frames are more valuable


# --------------------------------------------------------------------------
# Conversion helpers (LeapC objects -> plain dicts)
# --------------------------------------------------------------------------
def vec(v) -> list:
    return [round(float(v.x), 2), round(float(v.y), 2), round(float(v.z), 2)]


def quat(q) -> list:
    return [round(float(q.x), 4), round(float(q.y), 4), round(float(q.z), 4), round(float(q.w), 4)]


def hand_type(h) -> str:
    # LeapC enum prints as "HandType.Left" / "HandType.Right"
    return "left" if "left" in str(h.type).lower() else "right"


def hand_to_dict(h) -> dict:
    palm = h.palm
    return {
        "id": int(h.id),
        "type": hand_type(h),
        "confidence": round(float(h.confidence), 3),
        "pinch_strength": round(float(h.pinch_strength), 3),
        "pinch_distance": round(float(h.pinch_distance), 2),
        "grab_strength": round(float(h.grab_strength), 3),
        "grab_angle": round(float(h.grab_angle), 3),
        "palm": {
            "position": vec(palm.position),
            "velocity": vec(palm.velocity),
            "normal": vec(palm.normal),
            "direction": vec(palm.direction),
            "orientation": quat(palm.orientation),
            "width": round(float(palm.width), 2),
        },
        "fingers": [
            {
                "extended": bool(d.is_extended),
                "tip": vec(d.distal.next_joint),
                "bones": [[vec(b.prev_joint), vec(b.next_joint)] for b in d.bones],
            }
            for d in h.digits
        ],
    }


def palm_summary(hand: dict) -> dict:
    return {
        "type": hand["type"],
        "position": hand["palm"]["position"],
        "velocity": hand["palm"]["velocity"],
        "pinch": hand["pinch_strength"],
        "grab": hand["grab_strength"],
        "extended": sum(f["extended"] for f in hand["fingers"]),
    }


def publish_frame(frame_id: int, hands: list, fps: float) -> None:
    STATE["frames"] += 1
    emit("leap.frame", {"schema": "leap.frame.v2", "frame_id": frame_id, "fps": round(fps, 1), "hands": hands})
    for hand in hands:
        emit(f"leap.palm.{hand['type']}", {"frame_id": frame_id, **palm_summary(hand)})


# --------------------------------------------------------------------------
# Real device (LeapC Python bindings)
# --------------------------------------------------------------------------
class LeapSource:
    def __init__(self):
        import leap  # imported here so that --simulate works without the SDK

        self.leap = leap
        self.connection = leap.Connection()

        class Listener(leap.Listener):
            def on_connection_event(self, event):
                STATE["connected"] = True
                emit("leap.status", {"event": "connected"})

            def on_connection_lost_event(self, event):
                STATE["connected"] = False
                emit("leap.status", {"event": "connection_lost"})

            def on_device_event(self, event):
                # get_info() requires an OPEN device (otherwise DeviceNotOpenException)
                try:
                    with event.device.open():
                        info = event.device.get_info()
                except leap.LeapCannotOpenDeviceError:
                    info = event.device.get_info()  # already opened by the service
                STATE["device"] = info.serial
                emit("leap.status", {"event": "device", "serial": info.serial})

            def on_device_lost_event(self, event):
                STATE["device"] = None
                emit("leap.status", {"event": "device_lost"})

            def on_tracking_mode_event(self, event):
                emit("leap.status", {"event": "tracking_mode", "mode": STATE["mode"]})

            def on_tracking_event(self, event):
                hands = [hand_to_dict(h) for h in event.hands]
                publish_frame(int(event.tracking_frame_id), hands, float(event.framerate))

        self.listener = Listener()
        self.connection.add_listener(self.listener)
        self.modes = {
            "desktop": leap.TrackingMode.Desktop,
            "hmd": leap.TrackingMode.HMD,
            "screentop": leap.TrackingMode.ScreenTop,
        }

    def __enter__(self):
        self._ctx = self.connection.open()
        self._ctx.__enter__()
        self.set_mode("desktop")
        return self

    def __exit__(self, *exc):
        self.connection.remove_listener(self.listener)
        return self._ctx.__exit__(*exc)

    def set_mode(self, mode: str) -> None:
        self.connection.set_tracking_mode(self.modes[mode])
        STATE["mode"] = mode


# --------------------------------------------------------------------------
# Simulation (same schema, no hardware)
# --------------------------------------------------------------------------
class SimulatedSource:
    FPS = 110.0

    def __enter__(self):
        STATE.update(connected=True, device="SIMULATED", simulated=True)
        emit("leap.status", {"event": "device", "serial": "SIMULATED"})
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join()
        return False

    def set_mode(self, mode: str) -> None:
        STATE["mode"] = mode

    def _run(self) -> None:
        frame_id, start = 0, time.time()
        while not self._stop.wait(1 / self.FPS):
            t = time.time() - start
            phase = t % 8
            # right hand: circles, pinches every 2 s, grabs in 4..5 s, swipe in 6..7 s
            x = 120 * math.sin(t * 1.5) if phase < 6 else -200 + 400 * (phase - 6)
            pos = [x, 200 + 40 * math.cos(t * 1.5), 20 * math.sin(t)]
            vel = [180 * math.cos(t * 1.5) if phase < 6 else 400.0, -60 * math.sin(t * 1.5), 0.0]
            pinch = 1.0 if (t % 2) < 0.4 else 0.0
            grab = 1.0 if 4 <= phase < 5 else 0.0
            hand = {
                "id": 1, "type": "right", "confidence": 1.0,
                "pinch_strength": pinch, "pinch_distance": 10.0 if pinch else 60.0,
                "grab_strength": grab, "grab_angle": math.pi * grab,
                "palm": {"position": [round(v, 2) for v in pos], "velocity": [round(v, 2) for v in vel],
                         "normal": [0.0, -1.0, 0.0], "direction": [0.0, 0.0, -1.0],
                         "orientation": [0.0, 0.0, 0.0, 1.0], "width": 85.0},
                "fingers": [{"extended": not grab, "tip": pos, "bones": []} for _ in range(5)],
            }
            frame_id += 1
            publish_frame(frame_id, [hand] if phase < 7.5 else [], self.FPS)


# --------------------------------------------------------------------------
def handle_control(request: dict, source) -> dict:
    command = request.get("command")
    if command == "get_status":
        return {"ok": True, **STATE, "queue": EVENTS.qsize()}
    if command == "set_tracking_mode":
        mode = request.get("mode", "")
        if mode not in ("desktop", "hmd", "screentop"):
            return {"ok": False, "error": "mode must be desktop, hmd or screentop"}
        source.set_mode(mode)
        emit("leap.status", {"event": "tracking_mode", "mode": mode})
        return {"ok": True, "mode": mode}
    return {"ok": False, "error": f"unknown command {command!r}"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Leap Motion -> ZeroMQ bridge")
    parser.add_argument("--bind", default=os.getenv("ZMQ_PUB_ENDPOINT", "tcp://*:5555"))
    parser.add_argument("--control", default=os.getenv("ZMQ_CONTROL_ENDPOINT", "tcp://127.0.0.1:5556"))
    parser.add_argument("--simulate", action="store_true", help="synthetic hands, no device needed")
    args = parser.parse_args()

    running = threading.Event()
    running.set()
    signal.signal(signal.SIGINT, lambda *_: running.clear())
    signal.signal(signal.SIGTERM, lambda *_: running.clear())

    context = zmq.Context()
    pub = context.socket(zmq.PUB)
    pub.setsockopt(zmq.SNDHWM, 200)  # slow subscribers lose old frames instead of growing RAM
    pub.bind(args.bind)
    control = context.socket(zmq.REP)
    control.bind(args.control)
    poller = zmq.Poller()
    poller.register(control, zmq.POLLIN)

    source = SimulatedSource() if args.simulate else LeapSource()
    print(f"Leap bridge ({'simulated' if args.simulate else 'LeapC'}): PUB {args.bind}, control {args.control}")
    try:
        with source:
            while running.is_set():
                # 1) control requests (non-blocking)
                if dict(poller.poll(0)).get(control):
                    control.send_json(handle_control(control.recv_json(), source))
                # 2) forward queued tracking events
                try:
                    topic, payload = EVENTS.get(timeout=0.005)
                except queue.Empty:
                    continue
                payload["t_pub_us"] = now_us()
                pub.send_multipart([topic.encode(), json.dumps(payload, separators=(",", ":")).encode()])
    finally:
        pub.close(linger=0)
        control.close(linger=0)
        context.term()
        print("Leap bridge stopped")


if __name__ == "__main__":
    main()
