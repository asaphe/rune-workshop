"""Server behaviour: durability round-trip, session lifetime, world-session cap and the per-launch token."""
import http.client,sys,tempfile,threading,unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import server
from subscripts.playerDataUtil import pack_player_data_hex,unpack_player_data_hex
from test_synthetic_saves import synthetic_fch

class DurabilityTests(unittest.TestCase):
    def test_every_hundredth_round_trips(self):
        item=dict(prefab='Wood',prefab_hash=0,stack=1,quality=1,grid_x=0,grid_y=0,world_level=0,variant=0,equipped=False,picked_up=True,crafter_id=0,crafter_name='',custom_data={},cheated=False)
        bad=[]
        for raw in range(0,20001):
            item['durability']=raw*0.01
            got=unpack_player_data_hex(pack_player_data_hex(dict(version=33,inventory=[item],foods=[])))['inventory'][0]['durability']
            if round(got*100)!=raw:bad.append(raw)
        self.assertEqual(bad,[])

class SessionTests(unittest.TestCase):
    def setUp(self):
        for store in (server.SESSIONS,server.SOURCES,server.RECOVERY,server.WORLD_SESSIONS):
            saved=dict(store);store.clear();self.addCleanup(store.update,saved);self.addCleanup(store.clear)
        self.raw=synthetic_fch(34)

    def test_unknown_session_reports_expiry(self):
        for call in (lambda:server.export_save(dict(session='gone',player={})),lambda:server.scan_tombstones(dict(session='gone',path='x')),lambda:server.world_session('gone')):
            with self.subTest(call=call),self.assertRaisesRegex(ValueError,'expired'):call()

    def test_eviction_is_least_recently_used_and_skips_saving_sessions(self):
        with patch.object(server,'MAX_SESSIONS',3):
            a,b,c=(server.open_save(self.raw,'x.fch')['session'] for _ in range(3))
            server.character_session(a)
            with server.LOCK:server.SAVING.add(b)
            try:d=server.open_save(self.raw,'x.fch')['session']
            finally:
                with server.LOCK:server.SAVING.discard(b)
        self.assertEqual(set(server.SESSIONS),{a,b,d})

    def test_rescan_replaces_recovery_choices(self):
        sid=server.open_save(self.raw,'x.fch')['session']
        server.RECOVERY[sid]={'old':object()}
        root,_,_=server.SESSIONS[sid]
        fake=type('W',(),{'meta':dict(uid='1',name='W'),'tombs':[]})()
        root['worlds']=[dict(world_id=1)]
        with patch.object(server,'World',return_value=fake):server.scan_tombstones(dict(session=sid,path='p'))
        self.assertEqual(server.RECOVERY[sid],{})

    def test_world_sessions_are_capped_and_replaced_per_path(self):
        worlds=[type('W',(),{'path':Path(f'/w{i}')})() for i in range(6)]
        with patch.object(server,'MAX_WORLDS',3):
            ids=[server.add_world_session(w) for w in worlds]
            again=server.add_world_session(worlds[5])
        self.assertEqual(list(server.WORLD_SESSIONS),[ids[3],ids[4],again])

class TokenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);cls.port=cls.httpd.server_port
        threading.Thread(target=cls.httpd.serve_forever,daemon=True).start()
    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown();cls.httpd.server_close()

    def request(self,path,headers=None,method='GET',body=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=10)
        conn.request(method,path,body=body,headers={'Host':f'127.0.0.1:{self.port}',**(headers or {})})
        response=conn.getresponse();data=response.read();conn.close()
        return response,data

    def test_api_requires_launch_token(self):
        self.assertEqual(self.request('/api/characters')[0].status,403)
        self.assertEqual(self.request('/api/open',{'Content-Type':'application/octet-stream'},'POST',b'x')[0].status,403)
        self.assertEqual(self.request('/?t=wrong')[0].status,403)
        response,_=self.request('/?t='+server.TOKEN)
        self.assertEqual(response.status,303)
        cookie=response.getheader('Set-Cookie').split(';')[0]
        self.assertIn('HttpOnly',response.getheader('Set-Cookie'))
        self.assertEqual(self.request('/api/characters',{'Cookie':cookie})[0].status,200)

    def test_static_page_and_csp(self):
        response,_=self.request('/')
        self.assertEqual(response.status,200)
        for directive in ("base-uri 'none'","form-action 'self'","frame-ancestors 'none'"):
            self.assertIn(directive,response.getheader('Content-Security-Policy'))

    def test_foreign_host_rejected_even_with_token(self):
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=10)
        conn.request('GET','/api/characters',headers={'Host':'evil.example','Cookie':f'rune{self.port}={server.TOKEN}'})
        self.assertEqual(conn.getresponse().status,403);conn.close()

if __name__=='__main__':unittest.main()
