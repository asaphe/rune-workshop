import http.client,json,threading,time,unittest
from unittest.mock import patch
import server

class ShutdownTests(unittest.TestCase):
 def setUp(self):
  self.started=threading.Event();self.release=threading.Event();self.closed=threading.Event()
  parent=self
  class Handler(server.Handler):
   def do_GET(self):
    if self.path=='/test-operation':
     parent.started.set();parent.release.wait(5);self.send(200,{'done':True})
    else:super().do_GET()
  self.http=server.RuneServer(('127.0.0.1',0),Handler)
  def run():
   try:self.http.serve_forever(poll_interval=.02)
   finally:self.http.server_close();self.closed.set()
  self.thread=threading.Thread(target=run);self.thread.start()
  self.addCleanup(self.cleanup)
 def cleanup(self):
  self.release.set()
  if not self.closed.is_set():self.http.shutdown()
  self.thread.join(5)
 def post(self,auth=True,origin=None):
  c=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=3)
  headers={'Content-Type':'application/json'}
  if auth:headers['Cookie']=f'rune{self.http.server_port}={server.TOKEN}'
  if origin:headers['Origin']=origin
  c.request('POST','/api/quit','{}',headers);r=c.getresponse();status=r.status;r.read();c.close();return status
 def test_unauthorized_and_cross_origin_cannot_stop_server(self):
  self.assertEqual(self.post(False),403)
  self.assertEqual(self.post(origin='https://example.com'),403)
  self.assertFalse(self.http.stopping.is_set())
  self.assertEqual(self.post(),200);self.assertTrue(self.closed.wait(3))
 def test_shutdown_drains_an_active_operation(self):
  def operation():
   c=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=5)
   c.request('GET','/test-operation');r=c.getresponse();r.read();c.close()
  worker=threading.Thread(target=operation);worker.start()
  self.assertTrue(self.started.wait(3));self.assertEqual(self.post(),200)
  self.assertFalse(self.closed.wait(.1))
  self.release.set();worker.join(3);self.assertTrue(self.closed.wait(3))
  self.assertFalse(self.thread.is_alive());self.assertEqual(self.http.socket.fileno(),-1)
