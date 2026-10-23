import json,queue,time,os
import leap,zmq
EVENTS=queue.Queue(maxsize=256)
def vec(v):return {'x':float(v.x),'y':float(v.y),'z':float(v.z)}
def quat(q):return {'x':float(q.x),'y':float(q.y),'z':float(q.z),'w':float(q.w)}
def bone(b):return {'prev_joint':vec(b.prev_joint),'next_joint':vec(b.next_joint),'width':float(b.width),'rotation':quat(b.rotation)}
def hand_json(h):
 palm=h.palm
 return {'id':int(h.id),'type':str(h.type),'confidence':float(h.confidence),'visible_time':float(h.visible_time),'pinch_distance':float(h.pinch_distance),'pinch_strength':float(h.pinch_strength),'grab_angle':float(h.grab_angle),'grab_strength':float(h.grab_strength),'palm':{'position':vec(palm.position),'stabilized_position':vec(palm.stabilized_position),'velocity':vec(palm.velocity),'normal':vec(palm.normal),'direction':vec(palm.direction),'width':float(palm.width),'orientation':quat(palm.orientation)},'digits':[{'is_extended':bool(d.is_extended),'bones':[bone(b) for b in d.bones]} for d in h.digits]}
class Listener(leap.Listener):
 def on_connection_event(self,e):EVENTS.put_nowait(('leap.status',{'schema':'leap.status.v1','status':'connected'}))
 def on_device_event(self,e):
  try: info=e.device.get_info();EVENTS.put_nowait(('leap.status',{'schema':'leap.status.v1','device':str(info.serial)}))
  except Exception:pass
 def on_tracking_event(self,e):
  frame={'schema':'leap.frame.v1','frame_id':int(e.tracking_frame_id),'received_unix_ms':int(time.time()*1000),'hands':[hand_json(h) for h in e.hands]}
  try:EVENTS.put_nowait(('leap.frame',frame))
  except queue.Full:pass
def main():
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--bind',default=os.getenv('ZMQ_PUB_ENDPOINT','tcp://*:5555'));a=p.parse_args()
 ctx=zmq.Context();pub=ctx.socket(zmq.PUB);pub.setsockopt(zmq.SNDHWM,100);pub.bind(a.bind);listener=Listener();conn=leap.Connection();conn.add_listener(listener)
 try:
  with conn.open():
   conn.set_tracking_mode(leap.TrackingMode.Desktop);print('LeapC connected. Publishing on',a.bind,'Ctrl-C to stop')
   while True:
    try:t,obj=EVENTS.get(timeout=.05);pub.send_multipart([t.encode(),json.dumps(obj,separators=(',',':')).encode()])
    except queue.Empty:pass
 except KeyboardInterrupt:pass
 finally:conn.remove_listener(listener);pub.close(0);ctx.term()
if __name__=='__main__':main()
