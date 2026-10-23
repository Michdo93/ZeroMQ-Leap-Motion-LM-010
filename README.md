# ZeroMQ Leap Motion LM-010 for Ubuntu (Python)

Streams hand-tracking frames from the original Leap Motion Controller LM-010 using Ultraleap's LeapC Python bindings and ZeroMQ PUB/SUB. Frames include hand/palm position and orientation, velocity, pinch/grab measures, fingers and bones. These are tracking-service outputs, not raw infrared images. The bindings require the separately installed Ultraleap tracking service and SDK.

## Install device service and Python bindings

Install the Ubuntu-compatible Ultraleap Gemini Hand Tracking Service/SDK from Ultraleap's official download portal. Verify the service is running and that the LM-010 is detected. The SDK is not redistributed here. LeapC Python bindings are official open-source bindings but currently provide prebuilt Linux x64 extension for Python 3.8; on other Ubuntu Python versions build the CFFI component locally against the installed Leap SDK.

Example source build (Ubuntu x64):

    sudo apt update
    sudo apt install -y git build-essential python3-dev python3-venv
    git clone https://github.com/ultraleap/leapc-python-bindings.git
    cd leapc-python-bindings
    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install --upgrade pip build cffi
    python -m pip install -r requirements.txt
    export LEAPSDK_INSTALL_LOCATION=/usr/lib/ultraleap-hand-tracking-service
    python -m build leapc-cffi
    python -m pip install leapc-cffi/dist/leapc_cffi-0.0.1.tar.gz
    python -m pip install -e leapc-python-api
    cd /path/to/ZeroMQ-Leap-Motion-LM-010
    python -m venv --system-site-packages .venv
    source .venv/bin/activate
    python -m pip install -r requirements.txt

If using Ultraleap's supported Python 3.8 prebuilt extension, install the binding packages as instructed by their README; otherwise compile as above. For a non-default SDK location export LEAPSDK_INSTALL_LOCATION to that SDK folder. Linux x64 default is /usr/lib/ultraleap-hand-tracking-service.

## Run and test

Terminal A:

    source .venv/bin/activate
    python src/leap_bridge.py

Terminal B:

    source .venv/bin/activate
    python examples/monitor.py

Move hands over the controller. The monitor should show leap.frame records; startup/device changes use leap.status. Stop with Ctrl+C. Start the subscriber first.

## Message format and configuration

Messages are multipart: UTF-8 topic then compact UTF-8 JSON. Default topic output binds tcp://*:5555; subscriber connects to tcp://127.0.0.1:5555. Change publisher address with ZMQ_PUB_ENDPOINT and update examples/monitor.py to match. Frame includes ids, hand type, palm vectors/quaternion, finger extension and four bone segments. Coordinates are Leap-space units (millimeters); time values are service units. PUB/SUB is lossy during startup or overload.

To customize, edit hand_json() to select/extend fields or Listener.on_tracking_event() to derive new events. Pinch/grab strengths are included for custom gesture classification. The bridge intentionally avoids raw camera image transfer; LeapC has separate image-event capabilities that can be added if needed. For remote transfer, bind only on trusted interfaces and add CURVE authentication/encryption.

## Troubleshooting

Import error for leapc_cffi: ensure service SDK installed, LEAPSDK_INSTALL_LOCATION correct, and compile CFFI for active Python ABI. No connection/device: check the service and USB permissions; reconnect after adding required udev rules. No frames: verify device orientation and hand visibility. Port conflict: choose a free PUB bind and matching subscriber connect.

Upstream binding installation and supported Python ABIs: https://github.com/ultraleap/leapc-python-bindings . LeapC provides access to tracking, image and status events: https://docs.ultraleap.com/api-reference/tracking-api/leapc-guide.html .
