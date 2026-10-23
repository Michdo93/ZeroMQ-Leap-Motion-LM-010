import json,os,time,threading,websocket,zmq
def main():
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--ws',default=os.getenv('LEAP_WS_URL','ws://127.0.0.1:6437/v6.json'));p.add_argument('--bind',default=os.getenv('ZMQ_PUB_ENDPOINT','tcp://*:5555'));a=p.parse_args()
 ctx=zmq.Context();pub=ctx.socket(zmq.PUB);pub.setsockopt(zmq.SNDHWM,100);pub.bind(a.bind)
 def send(topic,obj):pub.send_multipart([topic.encode(),json.dumps(obj,separators=(',',':')).encode()])
 def opened(ws):ws.send(json.dumps({'enableGestures':True,'background':True}));print('Leap service connected')
 def message(ws,raw):
  try:f=json.loads(raw)
  except ValueError:return
  if 'hands' not in f:send('leap.status',f);return
  f.setdefault('schema','leap.frame.v1');f.setdefault('received_unix_ms',int(time.time()*1000));send('leap.frame',f)
  for g in f.get('gestures',[]):send('leap.gesture',{'schema':'leap.gesture.v1','frame_id':f.get('id'),'gesture':g})
 ws=websocket.WebSocketApp(a.ws,on_open=opened,on_message=message,on_error=lambda w,e:print('Leap WebSocket error:',e),on_close=lambda *x:print('Leap service closed'))
 t=threading.Thread(target=ws.run_forever,kwargs={'ping_interval':20},daemon=True);t.start()
 try:
  while t.is_alive():time.sleep(.1)
 except KeyboardInterrupt:pass
 finally:ws.close();pub.close(0);ctx.term()
if __name__=='__main__':main()
