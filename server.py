"""Local-only Valheim character editor with verified saves and retained backups."""
from pathlib import Path
import base64, copy, hashlib, io, json, math, os, re, secrets, sys, tempfile, threading, webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote
from contextlib import redirect_stdout
from datetime import datetime

BASE = Path(__file__).resolve().parent
EDITOR = BASE / 'backend' if (BASE / 'backend').exists() else BASE.parent / 'VikingEditor'
os.environ['VIKINGEDITOR_DATA_DIR'] = str(EDITOR / 'local-data')
sys.path.insert(0, str(EDITOR))
from subscripts.fchUtil import decompile_fch, compile_fch
from subscripts.playerDataUtil import unpack_player_data_hex, pack_player_data_hex
from world import World
WORLD_SESSIONS = {}
from data.skills import VALHEIM_SKILLS
from data.powers import GUARDIAN_POWERS
from data.hairs import VALHEIM_HAIRS
from data.beards import VALHEIM_BEARDS

RUNTIME = BASE / '.runtime'
RUNTIME.mkdir(exist_ok=True)
SESSIONS = {}
LOCK = threading.Lock()
SAVE_LOCK = threading.Lock()
SOURCES = {}
RECOVERY = {}
FIELDS = {'time_since_death','max_health','health','max_stamina','stamina','max_eitr','eitr','guardian_power','guardian_power_cooldown',
          'foods','skills','inventory','hair','beard','model_index','hair_color','skin_color','known_recipes',
          'known_stations','known_material','trophies','known_biomes','uniques','known_texts','shown_tutorials'}

ICONS = EDITOR / 'local-data/item_icons'

def catalogue():
    raw = json.loads((EDITOR/'local-data/valheim_items.json').read_text(encoding='utf-8'))['items']
    # Localized names prepared with MerpMB/Valhala's catalogue utility.
    try:labels=json.loads((EDITOR/'catalogue-labels.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):labels={}
    limits=json.loads((EDITOR/'stack-limits.json').read_text(encoding='utf-8'))
    durability=json.loads((EDITOR/'durability-stats.json').read_text(encoding='utf-8'))
    entries = []
    for key, item in raw.items():
        prefab = item['prefab']; label = labels.get(prefab,{})
        entries.append(dict(prefab=prefab, hash=int(key), name=label.get('name') or re.sub(r'(?<=[a-z])(?=[A-Z])',' ',prefab),
                            category=label.get('category','Other'), maxStack=limits.get(prefab), durability=durability.get(prefab), icons=[i for i in item.get('icons',[]) if (ICONS/i).is_file()]))
    return sorted(entries,key=lambda x:x['name'].lower())
CATALOG = catalogue()
FOOD_DATA=json.loads((EDITOR/'food-stats.json').read_text(encoding='utf-8'))

def decode(raw):
    with tempfile.TemporaryDirectory(dir=RUNTIME) as folder, redirect_stdout(io.StringIO()):
        p = Path(folder)/'input.fch';p.write_bytes(raw)
        root = decompile_fch(str(p))
        if not root.get('player_data_hex'): raise ValueError('This character has no saved player data yet.')
        player = unpack_player_data_hex(root['player_data_hex'])
        if (root['version'], player['version'], player['inventory_version']) not in ((46,33,109),(47,34,110)):
            raise ValueError('Unsupported save-format combination.')
        return root, player

def encode(root, player):
    root = copy.deepcopy(root)
    root['player_data_hex'] = pack_player_data_hex(player)
    with tempfile.TemporaryDirectory(dir=RUNTIME) as folder, redirect_stdout(io.StringIO()):
        j=Path(folder)/'wrapper.json';f=Path(folder)/'output.fch'
        j.write_text(json.dumps(root,ensure_ascii=False),encoding='utf-8');compile_fch(str(j),str(f))
        raw=f.read_bytes()
    checked_root, checked_player=decode(raw)
    if checked_root['version']!=root['version']: raise ValueError('Save verification failed.')
    if pack_player_data_hex(checked_player)!=root['player_data_hex']: raise ValueError('Player verification failed.')
    return raw

def public_player(player):
    out = {key:copy.deepcopy(value) for key,value in player.items() if key in FIELDS}
    # Browser numbers cannot represent every signed 64-bit identifier.
    for item in out['inventory']: item['crafter_id']=str(item.get('crafter_id',0))
    return out

def finite(value, low, high, label, integer=False):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError(f'{label} must be between {low} and {high}.')
    if integer and int(value)!=value: raise ValueError(f'{label} must be a whole number.')

def validate(player):
    for key in ('health','max_health','stamina','max_stamina','eitr','max_eitr','guardian_power_cooldown','time_since_death'):
        finite(player[key],0,1e7,key.replace('_',' '))
    if len(player['foods'])>3: raise ValueError('A character can have at most three active foods.')
    for food in player['foods']:
        if not isinstance(food['name'],str) or not food['name'].strip(): raise ValueError('Enter a food prefab.')
        finite(food['time'],0,1e7,'Food time')
    slots=set()
    for item in player['inventory']:
        for key,lo,hi in [('grid_x',0,7),('grid_y',0,255),('quality',1,65535),('stack',1,65535),('variant',0,2147483647),('world_level',0,255)]:
            finite(item.get(key,0),lo,hi,key,True)
        finite(item['durability'],0,21474836,'Durability')
        slot=(item['grid_x'],item['grid_y'])
        if slot in slots: raise ValueError('Two items occupy the same inventory slot.')
        slots.add(slot)
        item['crafter_id']=int(item.get('crafter_id',0))
        finite(item['crafter_id'],-2**63,2**63-1,'Crafter ID',True)
        if not item.get('prefab') and not item.get('prefab_hash'): raise ValueError('Item has no prefab or hash.')
    seen=set()
    for skill in player['skills']:
        finite(skill['level'],0,100,'Skill level');finite(skill['xp'],0,1e9,'Skill progress')
        if skill['id'] in seen: raise ValueError('Duplicate skill.')
        seen.add(skill['id'])
    for key in ('hair_color','skin_color'):
        if len(player[key])!=3:raise ValueError('Color must have three components.')
        for value in player[key]:finite(value,0,1,'Color')
    finite(player['model_index'],0,1,'Character model',True)
    for key in ('known_recipes','known_material','trophies','known_biomes','uniques','shown_tutorials'):
        if not isinstance(player[key],list) or any(not isinstance(v,str) for v in player[key]):raise ValueError(f'Invalid {key}.')
    for value in player['known_stations'].values():finite(value,0,1000,'Station level',True)

def open_save(raw,name,source=None):
    if len(raw)>32*1024*1024:raise ValueError('Character file is too large.')
    root,player=decode(raw)
    if encode(root,player)!=raw:raise ValueError('This save cannot yet be reproduced exactly. No changes were made.')
    sid=secrets.token_urlsafe(24)
    with LOCK:
        if len(SESSIONS)>=32:
            expired=next(iter(SESSIONS));SESSIONS.pop(expired);SOURCES.pop(expired,None);RECOVERY.pop(expired,None)
        SESSIONS[sid]=(root,player,raw)
        if source is not None:SOURCES[sid]=(Path(source).resolve(),raw)
    return dict(session=sid, filename=Path(name).name, canSave=source is not None and not is_cloud_cache(source), saveBlockedReason="Steam Cloud cache: move the character to Local in Valheim Manage Saves, quit Valheim, then reopen the local file." if source and is_cloud_cache(source) else None, sourcePath=str(Path(source).resolve()) if source else None, name=root['character_name'], usedCheats=root.get('used_cheats',False), player=public_player(player),
                playerId=str(root['player_id']), created=root.get('date_created_unix'), versions=[root['version'],player['version'],player['inventory_version']],
                worlds=len(root.get('worlds',[])))

def export_save(data):
    with LOCK:
        if data['session'] not in SESSIONS:raise ValueError('Session expired. Reopen your character.')
        root,original,raw=SESSIONS[data['session']]
    root=copy.deepcopy(root);player=copy.deepcopy(original)
    supplied=data['player']
    if set(supplied)-FIELDS:raise ValueError('Unsupported character field.')
    player.update(copy.deepcopy(supplied))
    if player['foods']!=original['foods']:
        names=[f['name'] for f in player['foods']]
        if len(names)!=len(set(names)):raise ValueError('Each active food must be different.')
        original_names={f['name'] for f in original['foods']}
        for food in player['foods']:
            stats=FOOD_DATA['foods'].get(food['name'])
            if stats:
                finite(food['time'],0,stats['duration'],'Food time')
            elif food['name'] not in original_names:raise ValueError('Choose an edible food from the food picker.')
    name=data.get('name',root['character_name']).strip()
    if not name or len(name)>64:raise ValueError('Character name must contain 1–64 characters.')
    root['character_name']=name
    if 'usedCheats' in data:
        if not isinstance(data['usedCheats'],bool):raise ValueError('Character cheat flag must be true or false.')
        root['used_cheats']=data['usedCheats']
    target=data.get('teleportTarget')
    if target:
        choices=RECOVERY.get(data['session'],{})
        if target not in choices:raise ValueError('Tombstone selection expired. Scan the world again.')
        world,grave=choices[target]
        world.verify_source()
        if grave['owner']!=str(root['player_id']):raise ValueError('This tombstone belongs to another character.')
        entry=next((w for w in root['worlds'] if str(w['world_id'])==world.meta['uid']),None)
        if entry is None:raise ValueError('This character has no saved position in that world.')
        pos=grave['position']
        if len(pos)!=3 or not all(math.isfinite(x) for x in pos):raise ValueError('Invalid tombstone position.')
        entry['logout_point']=list(pos);entry['have_logout_point']=True
    validate(player)
    result=encode(root,player)
    return result

def scan_tombstones(data):
    root,_,_=SESSIONS[data['session']]
    world=World(data['path'])
    if not any(str(w['world_id'])==world.meta['uid'] for w in root['worlds']):
        raise ValueError('This world is not in the character save. Choose the world where you died.')
    choices={};rows=[]
    for grave in world.tombs:
        if grave['owner']!=str(root['player_id']):continue
        token=secrets.token_hex(16);choices[token]=(world,grave)
        rows.append(dict(id=token,position=grave['position'],items=[dict(prefab=i['prefab'] or str(i['prefab_hash']),stack=i['stack']) for i in grave['items']]))
    RECOVERY.setdefault(data['session'],{}).update(choices)
    return dict(world=world.meta['name'],tombstones=rows)

def is_cloud_cache(path):
    parts=[part.lower() for part in Path(path).resolve().parts]
    return 'userdata' in parts and '892970' in parts and 'remote' in parts

def ensure_game_closed():
    if os.name!='nt':raise ValueError('Direct saves are only enabled on Windows with process checks.')
    import ctypes
    from ctypes import wintypes
    class Entry(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('usage',wintypes.DWORD),('pid',wintypes.DWORD),
                  ('heap',ctypes.c_size_t),('module',wintypes.DWORD),('threads',wintypes.DWORD),
                  ('parent',wintypes.DWORD),('priority',wintypes.LONG),('flags',wintypes.DWORD),
                  ('name',wintypes.WCHAR*260)]
    dll=ctypes.WinDLL('kernel32',use_last_error=True)
    dll.CreateToolhelp32Snapshot.argtypes=[wintypes.DWORD,wintypes.DWORD]
    dll.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    dll.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
    dll.Process32NextW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
    dll.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=dll.CreateToolhelp32Snapshot(2,0)
    if handle==ctypes.c_void_p(-1).value:raise ValueError('Cannot check whether Valheim is running. Save cancelled.')
    try:
        entry=Entry();entry.size=ctypes.sizeof(entry)
        if not dll.Process32FirstW(handle,ctypes.byref(entry)):raise ValueError('Cannot inspect running processes. Save cancelled.')
        while True:
            if entry.name.lower() in ('valheim.exe','valheim_server.exe'):
                raise ValueError('Close Valheim completely, including the main menu, before saving.')
            if not dll.Process32NextW(handle,ctypes.byref(entry)):
                if ctypes.get_last_error()!=18:raise ValueError('Process inspection failed. Save cancelled.')
                break
    finally:dll.CloseHandle(handle)

def install_staged(staged,path):
    os.replace(staged,path)

def save_character(data):
    with LOCK:source=SOURCES.get(data['session'])
    if source is None:raise ValueError('Reopen with Open character to save to its original location, or use Export copy.')
    if is_cloud_cache(source[0]):
        raise ValueError('Direct Steam Cloud cache writes are disabled: they can truncate saves. In Valheim Manage Saves, move this character to Local, quit Valheim completely, then reopen the local character here.')
    ensure_game_closed()
    result=export_save(data)
    with SAVE_LOCK:
        with LOCK:path,expected=SOURCES[data['session']]
        if path.read_bytes()!=expected:raise ValueError('This file changed outside the editor. Reopen it before saving.')
        if result==expected:return dict(saved=True,backup=None,path=str(path),unchanged=True)
        stamp=datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        backups=path.parent/'.rune-backups';backups.mkdir(exist_ok=True)
        backup=backups/f'{path.stem}_backup_editor-{stamp}.fch.old'
        fd,temp=tempfile.mkstemp(prefix=f'.{path.stem}-',suffix='.tmp',dir=path.parent)
        staged=Path(temp)
        try:
            with os.fdopen(fd,'wb') as stream:
                stream.write(result);stream.flush();os.fsync(stream.fileno())
            if staged.read_bytes()!=result:raise ValueError('Staged save verification failed.')
            with backup.open('xb') as stream:
                stream.write(expected);stream.flush();os.fsync(stream.fileno())
            if backup.read_bytes()!=expected:raise ValueError('Backup verification failed. Original file was not changed.')
            ensure_game_closed()
            if path.read_bytes()!=expected:raise ValueError('This file changed outside the editor. Reopen it before saving.')
            install_staged(staged,path)
            if path.read_bytes()!=result:raise ValueError(f'The file changed during save. The verified previous file is retained at {backup}.')
            with LOCK:SOURCES[data['session']]=(path,result)
            return dict(saved=True,backup=str(backup),path=str(path),unchanged=False)
        finally:staged.unlink(missing_ok=True)

def browse_character():
    import tkinter as tk
    from tkinter import filedialog
    window=tk.Tk();window.withdraw();window.attributes('-topmost',True)
    try:path=filedialog.askopenfilename(parent=window,title='Open Valheim character',filetypes=[('Valheim character','*.fch')])
    finally:window.destroy()
    if not path:return dict(cancelled=True)
    source=Path(path)
    return open_save(source.read_bytes(),source.name,source)

def open_character_path(value):
    if not isinstance(value,str) or not value.strip():raise ValueError('Paste a character file or folder path.')
    value=value.strip().strip('"')
    path=Path(os.path.expandvars(value)).expanduser()
    if not path.is_absolute():raise ValueError('Use the full path, including the drive letter.')
    path=path.resolve()
    if path.is_dir():
        files=sorted((p for p in path.iterdir() if p.is_file() and p.suffix.lower()=='.fch'),key=lambda p:p.name.lower())
        return dict(directory=str(path),files=[dict(name=p.name,path=str(p)) for p in files])
    if not path.is_file():raise ValueError('That path does not exist or is not accessible.')
    if path.suffix.lower()!='.fch':raise ValueError('Choose a .fch character file. Use Backups to download an .old backup as a restore copy.')
    return open_save(path.read_bytes(),path.name,path)

def backup_paths(session):
    with LOCK:source=SOURCES.get(session)
    if source is None:return []
    path=source[0]
    candidates=list((path.parent/'.rune-backups').glob(path.stem+'_backup_editor-*.fch.old'))
    candidates+=list(path.parent.glob(path.stem+'_backup_editor-*.fch.old'))
    return sorted(candidates,key=lambda p:p.stat().st_mtime,reverse=True)

def list_backups(session):
    entries=[]
    for path in backup_paths(session):
        try:
            raw=path.read_bytes();root,player=decode(raw)
            valid=encode(root,player)==raw
        except Exception:valid=False
        entries.append(dict(id=hashlib.sha256(str(path).encode()).hexdigest(),name=path.name,
                            path=str(path),modified=path.stat().st_mtime,valid=valid))
    return entries

def world_public(world, sid):
    result=world.public();result['session']=sid
    labels=json.loads((EDITOR/'container-labels.json').read_text(encoding='utf-8'))
    sizes=json.loads((EDITOR/'container-sizes.json').read_text(encoding='utf-8'))
    names={}
    for path in character_paths():
        try:
            root,_=decode(path.read_bytes())
            names.setdefault(str(root['player_id']),root['character_name'])
        except Exception:
            pass
    for c in result['containers']+result.get('texts',[]):
        c['name']=labels.get(str(c['prefab_hash']),f"Container {c['prefab_hash']}")
        c['creatorName']=names.get(c['creator'])
        c['size']=sizes.get(c['name'])
    return result

def character_paths():
    dirs=[*Path('D:/Steam/userdata').glob('*/892970/remote/characters'),Path.home()/'AppData/LocalLow/IronGate/Valheim/characters_local']
    return sorted([p for d in dirs if d.exists() for p in d.glob('*.fch') if '_backup_' not in p.name],key=lambda p:p.stat().st_mtime,reverse=True)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,status,body,ctype='application/json',extra=None):
        if isinstance(body,(dict,list)):body=json.dumps(body,ensure_ascii=False,allow_nan=False).encode()
        elif isinstance(body,str):body=body.encode()
        self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
        for k,v in (extra or {}).items():self.send_header(k,v)
        self.end_headers();self.wfile.write(body)
    def allowed(self):
        expected=f'127.0.0.1:{self.server.server_port}'
        return self.headers.get('Host')==expected and self.headers.get('Origin',f'http://{expected}')==f'http://{expected}'
    def do_GET(self):
        if not self.allowed():return self.send(403,{'error':'Local access only.'})
        path=urlparse(self.path).path
        try:
            if path=='/api/worlds':
                roots=[Path.home()/'AppData/LocalLow/IronGate/Valheim/worlds_local',*Path('D:/Steam/userdata').glob('*/892970/remote/worlds')]
                return self.send(200,[dict(name=p.name,path=str(p),cloud=is_cloud_cache(p)) for root in roots if root.exists() for p in root.iterdir() if p.is_dir() and '_backup' not in p.name and any(p.glob('_main.*.ok'))])
            if path=='/api/catalog':return self.send(200,dict(items=CATALOG,foods=FOOD_DATA['foods'],foodBase=FOOD_DATA['base'],skills=VALHEIM_SKILLS,powers=GUARDIAN_POWERS,hairs=VALHEIM_HAIRS,beards=VALHEIM_BEARDS))
            if path=='/api/characters':return self.send(200,[dict(id=hashlib.sha256(str(p).encode()).hexdigest(),name=p.stem,location='Steam Cloud' if is_cloud_cache(p) else 'Local',modified=p.stat().st_mtime,size=p.stat().st_size) for p in character_paths()])
            if path.startswith('/icons/'):
                name=path.split('/')[-1]
                if not re.fullmatch(r'[a-f0-9]{64}\.png',name):raise ValueError('Invalid icon.')
                return self.send(200,(ICONS/name).read_bytes(),'image/png')
            files={'/':'index.html','/world.js':'world.js','/app.js':'app.js','/style.css':'style.css'}
            if path not in files:return self.send(404,{'error':'Not found.'})
            ctype={'/':'text/html; charset=utf-8','/world.js':'text/javascript; charset=utf-8','/app.js':'text/javascript; charset=utf-8','/style.css':'text/css; charset=utf-8'}[path]
            self.send(200,(BASE/'web'/files[path]).read_bytes(),ctype)
        except Exception as exc:self.send(400,{'error':str(exc)})
    def do_POST(self):
        if not self.allowed():return self.send(403,{'error':'Local access only.'})
        try:
            size=int(self.headers.get('Content-Length',0))
            if not 0<size<=40*1024*1024:raise ValueError('Invalid request size.')
            body=self.rfile.read(size)
            if self.path=='/api/open':return self.send(200,open_save(body,unquote(self.headers.get('X-Filename','character.fch'))))
            if self.headers.get('Content-Type')!='application/json':raise ValueError('Expected JSON request.')
            data=json.loads(body)
            if self.path=='/api/tombstones':
                with SAVE_LOCK:result=scan_tombstones(data)
                return self.send(200,result)
            if self.path=='/api/world/open':
                with SAVE_LOCK:
                    world=World(data['path']);sid=secrets.token_hex(16)
                    WORLD_SESSIONS[sid]=world
                    result=world_public(world,sid)
                return self.send(200,result)
            if self.path in ('/api/world/save','/api/world/export'):
                with SAVE_LOCK:
                    world=WORLD_SESSIONS[data['session']]
                    if self.path.endswith('/export'):return self.send(200,world.export(data.get('changes',[]),data.get('texts'),data.get('settings')),'application/zip')
                    result=world.save(data.get('changes',[]),ensure_game_closed,data.get('texts'),data.get('settings'))
                    result['world']=world_public(world,data['session'])
                return self.send(200,result)
            if self.path=='/api/backups':return self.send(200,list_backups(data['session']))
            if self.path=='/api/backup-copy':
                path=next((p for p in backup_paths(data['session']) if hashlib.sha256(str(p).encode()).hexdigest()==data['id']),None)
                if not path:raise ValueError('Backup not found.')
                raw=path.read_bytes();root,player=decode(raw)
                if encode(root,player)!=raw:raise ValueError('Backup verification failed.')
                return self.send(200,raw,'application/octet-stream')
            if self.path=='/api/browse':return self.send(200,browse_character())
            if self.path=='/api/open-path':return self.send(200,open_character_path(data.get('path')))
            if self.path=='/api/load':
                match=next((p for p in character_paths() if hashlib.sha256(str(p).encode()).hexdigest()==data['id']),None)
                if not match:raise ValueError('Character not found.')
                return self.send(200,open_save(match.read_bytes(),match.name,match))
            if self.path=='/api/save':return self.send(200,save_character(data))
            if self.path=='/api/export':return self.send(200,export_save(data),'application/octet-stream')
            if self.path=='/api/original':
                with LOCK:raw=SESSIONS[data['session']][2]
                return self.send(200,raw,'application/octet-stream')
            self.send(404,{'error':'Not found.'})
        except Exception as exc:self.send(400,{'error':str(exc)})

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=0);parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    url=f'http://127.0.0.1:{server.server_port}'
    (RUNTIME/'url.txt').write_text(url)
    print(url,flush=True)
    if not args.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
