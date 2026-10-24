"""Shows the incoming Leap stream: rate, hands and end-to-end latency.

    python examples/monitor.py                 # everything
    python examples/monitor.py --topic leap.palm.right
"""

import argparse
import json
import time

import zmq


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--connect", default="tcp://127.0.0.1:5555")
    parser.add_argument("--topic", default="leap.")
    args = parser.parse_args()

    context = zmq.Context()
    sub = context.socket(zmq.SUB)
    sub.connect(args.connect)
    sub.setsockopt_string(zmq.SUBSCRIBE, args.topic)
    print(f"Listening on {args.connect} for '{args.topic}*' (Ctrl+C to stop)")

    count, latencies, window_start = 0, [], time.time()
    try:
        while True:
            topic, raw = sub.recv_multipart()
            msg = json.loads(raw)
            latencies.append(time.time_ns() // 1000 - msg["t_pub_us"])
            count += 1
            if topic == b"leap.status":
                print("STATUS", msg)
            if time.time() - window_start >= 1.0:
                latencies.sort()
                summary = ""
                if topic.startswith(b"leap.palm"):
                    summary = f" | {msg['type']} palm {msg['position']} pinch {msg['pinch']:.1f} grab {msg['grab']:.1f}"
                elif topic == b"leap.frame":
                    summary = f" | {len(msg['hands'])} hand(s)"
                print(f"{count:4d} msg/s  latency median {latencies[len(latencies)//2]:5d} us"
                      f"  max {latencies[-1]:6d} us{summary}")
                count, latencies, window_start = 0, [], time.time()
    except KeyboardInterrupt:
        pass
    finally:
        sub.close(linger=0)
        context.term()


if __name__ == "__main__":
    main()
