import json,zmq
c=zmq.Context();s=c.socket(zmq.SUB);s.setsockopt(zmq.SUBSCRIBE,b'leap.');s.connect('tcp://127.0.0.1:5555');print('Listening; Ctrl-C to stop')
try:
 while True:
  t,b=s.recv_multipart();print(t.decode(),json.dumps(json.loads(b),ensure_ascii=False)[:1200])
except KeyboardInterrupt:pass
finally:s.close(0);c.term()
