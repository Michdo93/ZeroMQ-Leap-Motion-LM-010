# ZeroMQ Leap Motion LM-010 (Python)

Streams hand tracking data of the original **Leap Motion Controller (LM-010)** with **ZeroMQ** – ~110 frames per second, sub-millisecond latency, any number of consumers, plus a control channel. Uses Ultraleap's official LeapC Python bindings (Gemini tracking service).

Companion example of the book *From Zero to Hero – ZeroMQ in Python meistern* (chapter "Two things MQTT cannot do (well)").

```
                       PUB tcp://*:5555                       PUB tcp://*:5557
 LM-010 ─ LeapC ─ leap_bridge.py ──leap.frame / leap.palm.*──► gesture_events.py ──gesture.*──► openHAB, robot, ...
                       │                      └──────────────► monitor.py (rate + latency)
                       └── REP tcp://127.0.0.1:5556 ◄── control.py (status, tracking mode)
```

Works **without hardware** as well: `--simulate` produces synthetic hands with the same message schema.

## 1. Install the Ultraleap tracking service

Download and install the *Ultraleap Hand Tracking* software (Gemini) for Linux from Ultraleap's developer site and check that the service runs and sees the device:

```bash
systemctl status ultraleap-hand-tracking-service   # name may differ by version
```

SDK locations used by the bindings: Linux x64 `/usr/lib/ultraleap-hand-tracking-service`, Linux ARM64 (e.g. Raspberry Pi) `/opt/ultraleap/LeapSDK`. Check Ultraleap's release notes for the devices and distributions supported by your version.

## 2. Install the LeapC Python bindings

Pre-compiled modules exist only for some Python versions (see the bindings README). For any other version build the CFFI module yourself:

```bash
sudo apt install -y git build-essential python3-dev python3-venv
git clone https://github.com/Michdo93/ZeroMQ-Leap-Motion-LM-010.git
cd ZeroMQ-Leap-Motion-LM-010
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

git clone https://github.com/ultraleap/leapc-python-bindings.git
cd leapc-python-bindings
pip install -r requirements.txt build
export LEAPSDK_INSTALL_LOCATION=/usr/lib/ultraleap-hand-tracking-service   # ARM: /opt/ultraleap/LeapSDK
python -m build leapc-cffi
pip install leapc-cffi/dist/leapc_cffi-0.0.1.tar.gz
pip install -e leapc-python-api
python examples/tracking_event_example.py     # prints frames -> bindings work
cd ..
```

## 3. Run

```bash
python src/leap_bridge.py              # real device
python src/leap_bridge.py --simulate   # no device needed
```

In further terminals:

```bash
python examples/monitor.py --topic leap.palm.right     # ~110 msg/s, latency median ~0.3 ms
python examples/gesture_events.py                      # pinch / grab / swipe events on :5557
python examples/control.py status
python examples/control.py mode screentop              # desktop | screentop | hmd
```

## Message format

Multipart `[topic, UTF-8 JSON]`, every payload contains `t_pub_us` (publisher clock, µs).

| Topic | Rate | Content |
|-------|------|---------|
| `leap.frame` | every tracking frame | `frame_id`, `fps`, `hands[]` with palm (position, velocity, normal, direction, orientation), pinch/grab, 5 fingers with tip and 4 bones |
| `leap.palm.left` / `leap.palm.right` | every frame per hand | compact: position, velocity, pinch, grab, number of extended fingers |
| `leap.status` | on change | `connected`, `device` (serial), `device_lost`, `tracking_mode` |
| `gesture.pinch` / `gesture.grab` / `gesture.swipe` | on event | produced by `gesture_events.py` |

Coordinates in millimetres relative to the device. Subscribe only to what you need: a consumer of `leap.palm.right` never receives the larger `leap.frame` messages (filtering happens on the publisher side for TCP).

## Design notes

* LeapC calls the listener in its own thread → events go into a bounded `queue.Queue`; only the main thread touches the PUB socket (sockets are not thread-safe).
* `SNDHWM=200`: a slow subscriber loses old frames instead of filling RAM – for live tracking the newest frame is what matters.
* `leap.status` is sent once per change. A subscriber that connects later does not see older status messages (PUB/SUB *slow joiner*) – use `control.py status` to query the current state.
* The control channel binds to `127.0.0.1` only. For remote access add CURVE (see ZeroMQ-Advanced-Examples).

## Troubleshooting

* `ModuleNotFoundError: leapc_cffi._leapc_cffi` – build the CFFI module for your Python version (step 2) and check `LEAPSDK_INSTALL_LOCATION`.
* No `device` in `control.py status` – tracking service not running, USB/permissions, or device not supported by the installed service version.
* `Address already in use` – another bridge is running; use `--bind`/`--control` with other ports.
