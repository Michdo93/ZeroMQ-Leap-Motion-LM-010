"""Control client for the bridge (REQ -> REP on tcp://127.0.0.1:5556).

    python examples/control.py status
    python examples/control.py mode desktop|screentop|hmd
"""

import argparse

import zmq


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["status", "mode"])
    parser.add_argument("value", nargs="?")
    parser.add_argument("--connect", default="tcp://127.0.0.1:5556")
    args = parser.parse_args()

    request = {"command": "get_status"} if args.command == "status" else \
        {"command": "set_tracking_mode", "mode": args.value}

    context = zmq.Context()
    req = context.socket(zmq.REQ)
    req.setsockopt(zmq.RCVTIMEO, 2000)
    req.setsockopt(zmq.LINGER, 0)
    req.connect(args.connect)
    try:
        req.send_json(request)
        print(req.recv_json())
    except zmq.Again:
        print("No answer - is leap_bridge.py running?")
    finally:
        req.close()
        context.term()


if __name__ == "__main__":
    main()
