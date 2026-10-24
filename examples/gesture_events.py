"""Second processing stage: turns the ~110 fps palm stream into a few
discrete gesture events and republishes them on its own PUB socket.

    leap_bridge --leap.palm.*--> gesture_events --gesture.*--> any consumer
                 (110 msg/s)                     (a few msg/min)

Detected events (with hysteresis so that one gesture = one event):
    gesture.pinch       pinch strength rises above 0.8
    gesture.grab        grab  strength rises above 0.8
    gesture.swipe       palm x velocity above 300 mm/s (left / right)

Ideas for consumers: switch lights via openHAB REST, control a robot, ...
"""

import argparse
import json
import time

import zmq


class GestureDetector:
    def __init__(self, publish):
        self.publish = publish
        self.pinching = self.grabbing = False
        self.last_swipe = 0.0

    def update(self, palm: dict) -> None:
        hand = palm["type"]
        if not self.pinching and palm["pinch"] > 0.8:
            self.pinching = True
            self.publish("gesture.pinch", {"hand": hand, "position": palm["position"]})
        elif self.pinching and palm["pinch"] < 0.3:
            self.pinching = False

        if not self.grabbing and palm["grab"] > 0.8:
            self.grabbing = True
            self.publish("gesture.grab", {"hand": hand, "position": palm["position"]})
        elif self.grabbing and palm["grab"] < 0.3:
            self.grabbing = False

        vx = palm["velocity"][0]
        if abs(vx) > 300 and time.time() - self.last_swipe > 1.0:
            self.last_swipe = time.time()
            self.publish("gesture.swipe", {"hand": hand, "direction": "right" if vx > 0 else "left"})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--connect", default="tcp://127.0.0.1:5555")
    parser.add_argument("--bind", default="tcp://*:5557")
    args = parser.parse_args()

    context = zmq.Context()
    sub = context.socket(zmq.SUB)
    sub.connect(args.connect)
    sub.setsockopt(zmq.SUBSCRIBE, b"leap.palm.")
    pub = context.socket(zmq.PUB)
    pub.bind(args.bind)

    def publish(topic: str, payload: dict) -> None:
        payload["t_pub_us"] = time.time_ns() // 1000
        pub.send_multipart([topic.encode(), json.dumps(payload).encode()])
        print(f"{topic:<14} {payload}")

    detector = GestureDetector(publish)
    print(f"Gesture stage: in {args.connect}, out {args.bind}")
    try:
        while True:
            _, raw = sub.recv_multipart()
            detector.update(json.loads(raw))
    except KeyboardInterrupt:
        pass
    finally:
        sub.close(linger=0)
        pub.close(linger=0)
        context.term()


if __name__ == "__main__":
    main()
