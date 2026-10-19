"""Local-only Valheim character editor with verified saves and retained backups."""
from pathlib import Path
import copy, hashlib, hmac, json, math, os, re, secrets, sys, tempfile, threading, webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote, parse_qs
from datetime import datetime

BASE = Path(__file__).resolve().parent
EDITOR = BASE / 'backend' if (BASE / 'backend').exists() else BASE.parent / 'VikingEditor'
os.environ['VIKINGEDITOR_DATA_DIR'] = str(EDITOR / 'local-data')
sys.path.insert(0, str(EDITOR))
from subscripts.fchUtil import decompile_fch, compile_fch
from subscripts.playerDataUtil import unpack_player_data_hex, pack_player_data_hex
from world import World
from platforms import ensure_game_closed, flush_to_disk, local_dirs, pick_character_file, steam_remote_dirs
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
SAVING = set()
MAX_SESSIONS = 32
MAX_WORLDS = 4
# Every /api and /icons request must carry this; the launch URL hands it to the browser as a cookie.
TOKEN = secrets.token_urlsafe(32)

def character_session(sid):
    with LOCK:
        if sid not in SESSIONS:raise ValueError('Session expired. Reopen your character.')
        SESSIONS[sid]=SESSIONS.pop(sid)
        return SESSIONS[sid]

def world_session(sid):
    with LOCK:
        if sid not in WORLD_SESSIONS:raise ValueError('World session expired. Reopen the world.')
        WORLD_SESSIONS[sid]=WORLD_SESSIONS.pop(sid)
        return WORLD_SESSIONS[sid]

def add_world_session(world):
    sid=secrets.token_hex(16)
    with LOCK:
        for old in [k for k,w in WORLD_SESSIONS.items() if w.path==world.path]:WORLD_SESSIONS.pop(old)
        while len(WORLD_SESSIONS)>=MAX_WORLDS:WORLD_SESSIONS.pop(next(iter(WORLD_SESSIONS)))
        WORLD_SESSIONS[sid]=world
    return sid
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
                            category=label.get('category','Other'), maxStack=limits.get(prefab), durability=durability.get(prefab), icons=[i if (ICONS/i).is_file() else None for i in item.get('icons',[])]))
    return sorted(entries,key=lambda x:x['name'].lower())
CATALOG = catalogue()
FOOD_DATA=json.loads((EDITOR/'food-stats.json').read_text(encoding='utf-8'))

def decode(raw):
    with tempfile.TemporaryDirectory(dir=RUNTIME) as folder:
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
    with tempfile.TemporaryDirectory(dir=RUNTIME) as folder:
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

# PlayerStatType IDs verified against Valheim 1.0: independent of the death timer.
SURVIVAL_CURRENT, SURVIVAL_BEST = 128, 129

def survival_profiles(root):
    profiles=root.get('profiles',[])
    if len(profiles)!=10 or any(len(p.get('stats',[]))<=SURVIVAL_BEST for p in profiles):return None
    return [dict(current=p['stats'][SURVIVAL_CURRENT],best=p['stats'][SURVIVAL_BEST]) for p in profiles]

def apply_survival(root, supplied):
    original=survival_profiles(root)
    if supplied==original:return
    if original is None or not isinstance(supplied,list) or len(supplied)!=10:
        raise ValueError('Survival statistics are unavailable for this save layout.')
    for index,row in enumerate(supplied):
        if row==original[index]:continue
        if not isinstance(row,dict) or set(row)!={'current','best'}:raise ValueError('Invalid survival statistics.')
        for key in ('current','best'):finite(row[key],0,1000000,'Survival days',True)
        if row['best']<row['current']:raise ValueError('Best survival streak cannot be below the current streak.')
        root['profiles'][index]['stats'][SURVIVAL_CURRENT]=row['current']
        root['profiles'][index]['stats'][SURVIVAL_BEST]=row['best']

def open_save(raw,name,source=None):
    if len(raw)>32*1024*1024:raise ValueError('Character file is too large.')
    root,player=decode(raw)
    if encode(root,player)!=raw:raise ValueError('This save cannot yet be reproduced exactly. No changes were made.')
    sid=secrets.token_urlsafe(24)
    with LOCK:
        idle=[k for k in SESSIONS if k not in SAVING]
        while len(SESSIONS)>=MAX_SESSIONS and idle:
            expired=idle.pop(0);SESSIONS.pop(expired);SOURCES.pop(expired,None);RECOVERY.pop(expired,None)
        SESSIONS[sid]=(root,player,raw)
        if source is not None:SOURCES[sid]=(Path(source).resolve(),raw)
    return dict(survival=survival_profiles(root), session=sid, filename=Path(name).name, canSave=source is not None and not is_cloud_cache(source), saveBlockedReason="Steam Cloud cache: move the character to Local in Valheim Manage Saves, quit Valheim, then reopen the local file." if source and is_cloud_cache(source) else None, sourcePath=str(Path(source).resolve()) if source else None, name=root['character_name'], usedCheats=root.get('used_cheats',False), player=public_player(player),
                playerId=str(root['player_id']), created=root.get('date_created_unix'), versions=[root['version'],player['version'],player['inventory_version']],
                worlds=len(root.get('worlds',[])))

def export_save(data):
    root,original,raw=character_session(data['session'])
    root=copy.deepcopy(root);player=copy.deepcopy(original)
    if 'survival' in data:apply_survival(root,data['survival'])
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
        with LOCK:choices=RECOVERY.get(data['session'],{})
        if target not in choices:raise ValueError('Tombstone selection expired. Scan the world again.')
        choice=choices[target];grave=choice['grave']
        current=World(choice['path'])
        if (current.seen,current.number)!=(choice['seen'],choice['number']):raise ValueError('The world changed since the scan. Scan the world again.')
        if grave['owner']!=str(root['player_id']):raise ValueError('This tombstone belongs to another character.')
        entry=next((w for w in root['worlds'] if str(w['world_id'])==choice['uid']),None)
        if entry is None:raise ValueError('This character has no saved position in that world.')
        pos=grave['position']
        if len(pos)!=3 or not all(math.isfinite(x) for x in pos):raise ValueError('Invalid tombstone position.')
        entry['logout_point']=list(pos);entry['have_logout_point']=True
    validate(player)
    result=encode(root,player)
    return result

def scan_tombstones(data):
    root,_,_=character_session(data['session'])
    world=World(data['path'])
    if not any(str(w['world_id'])==world.meta['uid'] for w in root['worlds']):
        raise ValueError('This world is not in the character save. Choose the world where you died.')
    choices={};rows=[]
    for grave in world.tombs:
        if grave['owner']!=str(root['player_id']):continue
        token=secrets.token_hex(16);choices[token]=dict(path=world.path,seen=world.seen,number=world.number,uid=world.meta['uid'],grave=grave)
        rows.append(dict(id=token,position=grave['position'],items=[dict(prefab=i['prefab'] or str(i['prefab_hash']),stack=i['stack']) for i in grave['items']]))
    with LOCK:
        if data['session'] not in SESSIONS:raise ValueError('Session expired. Reopen your character.')
        RECOVERY[data['session']]=choices
    return dict(world=world.meta['name'],tombstones=rows,warning=getattr(world,'warning',None))

def is_cloud_cache(path):
    parts=[part.lower() for part in Path(path).resolve().parts]
    return 'userdata' in parts and '892970' in parts and 'remote' in parts

def install_staged(staged,path):
    os.replace(staged,path)

def save_character(data):
    sid=data['session']
    with LOCK:
        if sid in SAVING:raise ValueError('A save of this character is already running.')
        SAVING.add(sid)
    try:return _save_character(data)
    finally:
        with LOCK:SAVING.discard(sid)

def _save_character(data):
    character_session(data['session'])
    with LOCK:source=SOURCES.get(data['session'])
    if source is None:raise ValueError('Reopen with Open character to save to its original location, or use Export copy.')
    if is_cloud_cache(source[0]):
        raise ValueError('Direct Steam Cloud cache writes are disabled: they can truncate saves. In Valheim Manage Saves, move this character to Local, quit Valheim completely, then reopen the local character here.')
    ensure_game_closed()
    result=export_save(data)
    with SAVE_LOCK:
        with LOCK:path,expected=SOURCES.get(data['session'],source)
        if path.read_bytes()!=expected:raise ValueError('This file changed outside the editor. Reopen it before saving.')
        if result==expected:return dict(saved=True,backup=None,path=str(path),unchanged=True)
        stamp=datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        backups=path.parent/'.rune-backups';backups.mkdir(exist_ok=True)
        backup=backups/f'{path.stem}_backup_editor-{stamp}.fch.old'
        fd,temp=tempfile.mkstemp(prefix=f'.{path.stem}-',suffix='.tmp',dir=path.parent)
        staged=Path(temp)
        try:
            with os.fdopen(fd,'wb') as stream:
                stream.write(result);flush_to_disk(stream)
            if staged.read_bytes()!=result:raise ValueError('Staged save verification failed.')
            with backup.open('xb') as stream:
                stream.write(expected);flush_to_disk(stream)
            if backup.read_bytes()!=expected:raise ValueError('Backup verification failed. Original file was not changed.')
            ensure_game_closed()
            if path.read_bytes()!=expected:raise ValueError('This file changed outside the editor. Reopen it before saving.')
            install_staged(staged,path)
            if path.read_bytes()!=result:raise ValueError(f'The file changed during save. The verified previous file is retained at {backup}.')
            with LOCK:SOURCES[data['session']]=(path,result)
            return dict(saved=True,backup=str(backup),path=str(path),unchanged=False)
        finally:staged.unlink(missing_ok=True)

def browse_character():
    path=pick_character_file()
    if not path:return dict(cancelled=True)
    return open_local_path(Path(path))

def open_character_path(value):
    if not isinstance(value,str) or not value.strip():raise ValueError('Paste a character file or folder path.')
    value=value.strip().strip('"')
    path=Path(os.path.expandvars(value)).expanduser()
    if not path.is_absolute():raise ValueError('Use the full path to the file or folder.')
    return open_local_path(path)

def open_local_path(path):
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
    dirs=steam_remote_dirs('characters')+local_dirs('characters')
    return sorted([p for d in dirs if d.exists() for p in d.glob('*.fch') if '_backup_' not in p.name],key=lambda p:p.stat().st_mtime,reverse=True)

class RuneServer(ThreadingHTTPServer):
    # Drain accepted requests (including saves) before the process exits.
    daemon_threads = False
    block_on_close = True

    def __init__(self, *args, **kwargs):
        self.stopping = threading.Event()
        super().__init__(*args, **kwargs)

class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self,*args):pass
    def send(self,status,body,ctype='application/json',extra=None):
        if isinstance(body,(dict,list)):body=json.dumps(body,ensure_ascii=False,allow_nan=False).encode()
        elif isinstance(body,str):body=body.encode()
        self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        for k,v in (extra or {}).items():self.send_header(k,v)
        self.end_headers();self.wfile.write(body)
    def allowed(self):
        expected=f'127.0.0.1:{self.server.server_port}'
        return self.headers.get('Host')==expected and self.headers.get('Origin',f'http://{expected}')==f'http://{expected}'
    def cookie_name(self):
        return f'rune{self.server.server_port}'
    def authorized(self):
        # Parsed by hand: SimpleCookie drops every cookie after a malformed one, and 127.0.0.1 cookies are shared by all local ports.
        for part in self.headers.get('Cookie','').split(';'):
            name,_,value=part.strip().partition('=')
            if name==self.cookie_name() and hmac.compare_digest(value.encode(),TOKEN.encode()):return True
        return False
    def do_GET(self):
        if not self.allowed():return self.send(403,{'error':'Local access only.'})
        url=urlparse(self.path);path=url.path
        if path=='/' and parse_qs(url.query).get('t'):
            if not hmac.compare_digest(parse_qs(url.query)['t'][0].encode(),TOKEN.encode()):return self.send(403,{'error':'This Rune link is from an earlier launch. Use the link Rune printed when it started.'})
            return self.send(303,b'','text/plain',{'Location':'/','Set-Cookie':f'{self.cookie_name()}={TOKEN}; Path=/; HttpOnly; SameSite=Strict'})
        if (path.startswith('/api/') or path.startswith('/icons/')) and not self.authorized():
            return self.send(403,{'error':'Open Rune with its launcher, or the link saved in the .runtime/url.txt file next to server.py.'})
        try:
            if path=='/api/worlds':
                roots=local_dirs('worlds')+steam_remote_dirs('worlds')
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
        if not self.authorized():return self.send(403,{'error':'Open Rune with its launcher, or the link saved in the .runtime/url.txt file next to server.py.'})
        if getattr(self.server,'stopping',None) and self.server.stopping.is_set():return self.send(503,{'error':'Rune is shutting down.'})
        try:
            size=int(self.headers.get('Content-Length',0))
            if not 0<size<=40*1024*1024:raise ValueError('Invalid request size.')
            body=self.rfile.read(size)
            if self.path=='/api/open':return self.send(200,open_save(body,unquote(self.headers.get('X-Filename','character.fch'))))
            if self.headers.get('Content-Type')!='application/json':raise ValueError('Expected JSON request.')
            data=json.loads(body)
            if self.path=='/api/quit':
                self.server.stopping.set()
                try:self.send(200,{'stopping':True})
                finally:threading.Thread(target=self.server.shutdown,daemon=True).start()
                return
            if self.path=='/api/tombstones':
                with SAVE_LOCK:result=scan_tombstones(data)
                return self.send(200,result)
            if self.path=='/api/world/open':
                with SAVE_LOCK:
                    world=World(data['path']);sid=add_world_session(world)
                    result=world_public(world,sid)
                return self.send(200,result)
            if self.path in ('/api/world/save','/api/world/export'):
                with SAVE_LOCK:
                    world=world_session(data['session'])
                    if self.path.endswith('/export'):return self.send(200,world.export(data.get('changes',[]),data.get('texts'),data.get('settings')),'application/zip')
                    result=world.save(data.get('changes',[]),ensure_game_closed,data.get('texts'),data.get('settings'))
                    if not result.get('unchanged') and not result.get('reopen'):
                        try:result['world']=world_public(world,data['session'])
                        except Exception as exc:result.update(reopen=True,warning=f'Saved generation {result["generation"]}, but preparing the updated view failed ({exc}). Reopen the world before making more changes.')
                    elif result.get('unchanged'):result['world']=world_public(world,data['session'])
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
                raw=character_session(data['session'])[2]
                return self.send(200,raw,'application/octet-stream')
            self.send(404,{'error':'Not found.'})
        except Exception as exc:self.send(400,{'error':str(exc)})

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=0);parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
    server=RuneServer(('127.0.0.1',args.port),Handler)
    url=f'http://127.0.0.1:{server.server_port}/?t={TOKEN}'
    url_file=RUNTIME/'url.txt'
    with os.fdopen(os.open(url_file,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600),'w') as stream:stream.write(url)
    os.chmod(url_file,0o600)
    print(url,flush=True)
    if not args.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        server.server_close()
        # Another launch may now own this file; never remove its link.
        try:
            if url_file.read_text()==url:url_file.unlink()
        except OSError:pass
