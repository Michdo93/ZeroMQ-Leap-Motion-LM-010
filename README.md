# ZeroMQ Leap Motion LM-010 Bridge

For the original Leap Motion Controller LM-010. The bridge forwards the tracking service's JSON frames (hands, fingers, bones, frame data) and reported gestures over ZeroMQ PUB/SUB. It sends interpreted tracking output, not raw infrared pixels. Hardware: LM-010 over USB, Windows, and a Leap Motion Orion tracking service exposing its legacy local WebSocket API. This proprietary runtime/SDK is not bundled.

## Install

Install and start the Leap tracking service separately; check that it recognizes the device. Install Python 3.10+, then in PowerShell at repo root:

    py -3 -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt

The bridge defaults to ws://127.0.0.1:6437/v6.json and PUB tcp://*:5555. Legacy WebSocket availability depends on the Leap service version/configuration. Current Ultraleap documentation favors LeapC; if the local service lacks this legacy endpoint, replace the input adapter with LeapC and retain the ZeroMQ output contract.

## Run and test

Terminal A: .venv\Scripts\python.exe src\leap_bridge.py
Terminal B: .venv\Scripts\python.exe examples\monitor.py

Move hands above the device; monitor should display leap.frame and available leap.gesture events. Ctrl+C stops processes. Start subscriber first.

Each PUB message contains multipart frames: topic UTF-8 then JSON UTF-8. Topics are leap.frame, leap.gesture, leap.status. The bridge adds schema and receive time while retaining service fields. Frames are not durable; PUB/SUB may lose data on connect or overload.

## Configure and personalize

Set PowerShell variables before start: LEAP_WS_URL overrides WebSocket address; ZMQ_PUB_ENDPOINT changes the bridge bind. If changing the port, edit examples/monitor.py endpoint to match. Edit the message callback to filter fields or emit custom events. The bridge requests gesture reporting. No LM-010 brightness adjustment is exposed in this API. Remote data should use CURVE and authorized peers rather than an open TCP endpoint.

Troubleshooting: no WebSocket means check Leap service and local port 6437; no hands means check device recognized, hand visibility and foreground/background policy; address-in-use means choose a free port on both peers. References: https://docs.ultraleap.com/hand-tracking/index.html ; https://docs.ultraleap.com/api-reference/tracking-api/leapc-guide/leap-concepts.html ; https://developer.leapmotiontechnology.com/developer-sub/documentation
