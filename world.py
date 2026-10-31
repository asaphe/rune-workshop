"""Chunked-world containers. Format reference: Shuiei/valheim-world-editor (MIT)."""
import copy, gzip, io, math, os, re, struct, zipfile
from pathlib import Path
from datetime import datetime
from platforms import flush_to_disk, publish_new, sync_directory
from subscripts.playerDataUtil import get_stable_hash_code as hashcode, ITEM_HASH_TO_PREFAB

def p(fmt,*values): return struct.pack('<'+fmt,*values)
class Reader:
    def __init__(self,data): self.data,self.pos=data,0
    def take(self,n):
        if n<0 or self.pos+n>len(self.data): raise ValueError('Truncated world data.')
        b=self.data[self.pos:self.pos+n];self.pos+=n;return b
    def read(self,fmt):return struct.unpack('<'+fmt,self.take(struct.calcsize('<'+fmt)))[0]
    def num(self):
        b=self.read('B');return ((b&127)<<8)|self.read('B') if b&128 else b
    def string(self):
        n=0
        for shift in range(0,35,7):
            b=self.read('B');n|=(b&127)<<shift
            if b<128:return self.take(n).decode('utf-8')
        raise ValueError('Invalid string.')
    def end(self):
        if self.pos!=len(self.data):raise ValueError('Unrecognized trailing data.')
def string(s):
    b=s.encode('utf-8');n=len(b);out=b''
    while n>=128:out+=bytes([(n&127)|128]);n>>=7
    return out+bytes([n])+b
def inventory(raw):
    r=Reader(raw);v=r.read('i')
    if v not in (109,110):raise ValueError(f'Unsupported inventory version {v}')
    items=[]
    for _ in range(r.read('H')):
        start=r.pos
        i=dict(durability=r.read('i')/100,grid_x=r.read('B'),grid_y=r.read('B'),world_level=r.read('B'))
        f=r.read('B')
        i.update(picked_up=bool(f&1),equipped=bool(f&2),quality=r.read('H') if f&4 else 1,stack=r.read('H') if f&8 else 1,variant=r.read('i') if f&16 else 0)
        i['crafter_id']=str(r.read('q')) if f&32 else '0';i['crafter_name']=r.string() if f&32 else ''
        i['prefab_hash']=r.read('i') if f&64 else 0;i['prefab']=ITEM_HASH_TO_PREFAB.get(i['prefab_hash'],'')
        i['custom_data']={r.string():r.string() for _ in range(r.num() if f&128 else 0)}
        i['_cheat_byte']=r.read('B');i['cheated']=bool(i['_cheat_byte']&1)
        i['_raw']=raw[start:r.pos].hex();items.append(i)
    r.end();return v,items
def encode_inventory(v,items,originals):
    if len(items)>65535:raise ValueError('Too many items.')
    out=p('iH',v,len(items));cells=set();lookup={i['_raw']:i for i in originals}
    for incoming in items:
        i=copy.deepcopy(incoming);old=lookup.get(i.get('_raw'))
        if old:
            i=copy.deepcopy(old)
            for k in ('prefab','prefab_hash','stack','quality','durability','grid_x','grid_y','cheated'):i[k]=incoming[k]
        for k,lo,hi in [('grid_x',0,255),('grid_y',0,255),('stack',1,65535),('quality',1,65535),('world_level',0,255),('variant',0,2147483647)]:
            val=i.get(k,0)
            if isinstance(val,bool) or not isinstance(val,int) or not lo<=val<=hi:raise ValueError(f'Invalid {k}.')
        cell=(i['grid_x'],i['grid_y'])
        if cell in cells:raise ValueError('Two items occupy the same slot.')
        cells.add(cell)
        if not math.isfinite(i['durability']) or not 0<=i['durability']<=21474836:raise ValueError('Invalid durability.')
        if old==i:out+=bytes.fromhex(i['_raw']);continue
        f=int(i.get('picked_up',False))|(int(i.get('equipped',False))<<1)
        for bit,key,default in [(4,'quality',1),(8,'stack',1),(16,'variant',0)]:
            if i[key]!=default:f|=bit
        if int(i.get('crafter_id',0)):f|=32
        h=hashcode(i['prefab']) if i.get('prefab') else i.get('prefab_hash',0)
        if h:f|=64
        custom=i.get('custom_data',{})
        if custom:f|=128
        out+=p('iBBBB',round(i['durability']*100),i['grid_x'],i['grid_y'],i['world_level'],f)
        if f&4:out+=p('H',i['quality'])
        if f&8:out+=p('H',i['stack'])
        if f&16:out+=p('i',i['variant'])
        if f&32:out+=p('q',int(i['crafter_id']))+string(i.get('crafter_name',''))
        if f&64:out+=p('i',h)
        if f&128:
            n=len(custom)
            if n>32767:raise ValueError('Too much custom data.')
            out+=bytes([n]) if n<128 else bytes([(n>>8)|128,n&255])
            for k,val in custom.items():out+=string(k)+string(val)
        out+=p('B',(i.get('_cheat_byte',0)&254)|int(i.get('cheated',False)))
    inventory(out);return out
def chunk_name(c):return f'{c[0]>>8:02x}_{c[0]&255:02x}__{c[1]}_{c[2]}.chunk'
TEXT_PREFABS={hashcode('portal_wood'):('portal','tag'),hashcode('portal_stone'):('portal','tag'),hashcode('sign'):('sign','text'),hashcode('sign_notext'):('sign','text')}
PORTAL_PREFABS={h for h,(kind,_) in TEXT_PREFABS.items() if kind=='portal'}
MODIFIERS={'nobuildcost','passivemobs','teleportall','playerevents','fire'}

def num(n):
    if not 0<=n<=32767:raise ValueError('Invalid entry count.')
    return bytes([n]) if n<128 else bytes([(n>>8)|128,n&255])

def metadata(raw):
    r=Reader(raw);length=r.read('i')
    if length!=len(raw)-4:raise ValueError('Invalid world metadata length.')
    version=r.read('i')
    if version not in (40,41,42):raise ValueError('Unsupported world metadata version.')
    name=r.string();r.string();r.take(4);uid=r.read('q');r.take(4+1)
    start=r.pos;count=r.read('i')
    if not 0<=count<=len(raw):raise ValueError('Invalid world modifier count.')
    keys=[r.string() for _ in range(count)]
    return dict(start=start,end=r.pos,keys=keys,name=name,uid=str(uid))

# Values from the installed game's ServerOptionsGUI modifier sliders.
SETTING_CHOICES={
    'combatDifficulty':{
        'veryeasy':['playerdamage 125','enemydamage 50','enemyspeedsize 90'],
        'easy':['playerdamage 110','enemydamage 75','enemyspeedsize 95'],
        'normal':[],
        'hard':['playerdamage 85','enemydamage 150','enemyspeedsize 110','enemyleveluprate 120'],
        'veryhard':['playerdamage 70','enemydamage 200','enemyspeedsize 120','enemyleveluprate 140']},
    'raidFrequency':{'none':['eventrate 0'],'muchless':['eventrate 200'],'less':['eventrate 150'],
                     'normal':[],'more':['eventrate 60'],'muchmore':['eventrate 30']}}

def setting_keys(key):
    return {entry.split()[0].lower() for entries in SETTING_CHOICES[key].values() for entry in entries}

def setting_choice(keys,key):
    actual=sorted(entry.lower() for entry in keys if entry.split() and entry.split()[0].lower() in setting_keys(key))
    return next((name for name,entries in SETTING_CHOICES[key].items() if sorted(entries)==actual),'custom')

def world_settings(keys):
    return {**{key:any(k.lower()==key for k in keys) for key in sorted(MODIFIERS)},
            **{key:setting_choice(keys,key) for key in SETTING_CHOICES}}

def patch_settings(raw,settings):
    meta=metadata(raw);keys=meta['keys'][:]
    if not isinstance(settings,dict) or set(settings)-(MODIFIERS|RAID_ACTIONS|set(SETTING_CHOICES)|{'progression'}):raise ValueError('Unsupported world setting.')
    for key,value in settings.items():
        if key in RAID_ACTIONS or key=='progression':continue
        if key in SETTING_CHOICES:
            if not isinstance(value,str) or value not in {*SETTING_CHOICES[key],'custom'}:raise ValueError('Unsupported modifier choice.')
            if value=='custom' or setting_choice(keys,key)==value:continue
            owned=setting_keys(key)
            keys=[entry for entry in keys if not entry.split() or entry.split()[0].lower() not in owned]
            keys.extend(SETTING_CHOICES[key][value])
            continue
        if not isinstance(value,bool):raise ValueError('World settings must be on or off.')
        present=any(k.lower()==key for k in keys)
        if present==value:continue
        keys=[k for k in keys if k.lower()!=key]
        if value:keys.append(key)
    if keys==meta['keys']:return raw
    result=raw[4:meta['start']]+p('i',len(keys))+b''.join(string(k) for k in keys)+raw[meta['end']:]
    result=p('i',len(result))+result;metadata(result);return result

RAID_ACTIONS={'endRaid','resetRaidTimer'}

PROGRESSION_FLAGS={
    'defeated_eikthyr':'Eikthyr defeated',
    'defeated_gdking':'The Elder defeated',
    'defeated_bonemass':'Bonemass defeated',
    'defeated_dragon':'Moder defeated',
    'defeated_goblinking':'Yagluth defeated',
    'defeated_queen':'The Queen defeated',
    'defeated_fader':'Fader defeated',
    'defeated_writhan':'Writhan defeated',
    'defeated_serpent':'A serpent has been defeated',
    'defeated_hive':'Hive defeated (game flag name)',
    'elakingmole_defeated':'Elaking mole defeated (game flag name)',
    'jotun_killed':'A jotun has been killed',
    'killed_frysling':'A frysling has been killed',
    'killedbat':'A bat has been killed',
    'bosshildir1':'Hildir miniboss 1 defeated',
    'bosshildir2':'Hildir miniboss 2 defeated',
    'bosshildir3':'Hildir miniboss 3 defeated',
    'killedtroll':'A troll has been killed',
    'killed_surtling':'A surtling has been killed'}

def progression_state(raw):
    r=Reader(raw)
    if r.read('i') not in (41,42):raise ValueError('Progression controls require world DB version 41 or 42.')
    r.take(8);compressed=r.take(r.read('i'));outer_end=r.pos
    # Limit decompression before parsing untrusted save files.
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:data=stream.read(64*1024*1024+1)
    if len(data)>64*1024*1024:raise ValueError('World progression data is too large.')
    z=Reader(data);zones=z.read('i')
    if zones<0:raise ValueError('Invalid generated-zone count.')
    z.take(zones*4);z.take(4) # Vector2s entries and location version.
    start=z.pos;count=z.read('i')
    if not 0<=count<=len(data):raise ValueError('Invalid progression key count.')
    keys=[z.string() for _ in range(count)]
    return dict(data=data,start=start,end=z.pos,outer_end=outer_end,keys=keys)

def patch_progression(raw,changes):
    if not isinstance(changes,dict) or set(changes)-set(PROGRESSION_FLAGS) or any(type(v) is not bool for v in changes.values()):
        raise ValueError('Unsupported progression flag change.')
    if not changes:return raw
    state=progression_state(raw);keys=state['keys'][:]
    for key,value in changes.items():
        if any(k.lower()==key for k in keys)==value:continue
        keys=[k for k in keys if k.lower()!=key]
        if value:keys.append(key)
    if keys==state['keys']:return raw
    data=state['data'][:state['start']]+p('i',len(keys))+b''.join(string(k) for k in keys)+state['data'][state['end']:]
    compressed=gzip.compress(data,mtime=0)
    return raw[:12]+p('i',len(compressed))+compressed+raw[state['outer_end']:]

def raid_state(raw):
    r=Reader(raw)
    if r.read('i') not in (41,42):raise ValueError('Raid controls require world DB version 41 or 42.')
    r.take(8)  # World clock; preserve it.
    r.take(r.read('i'))  # Compressed ZoneSystem data; preserve it byte for byte.
    start=r.pos;timer=r.read('f');name=r.string();elapsed=r.read('f')
    position=[r.read('f') for _ in range(3)]
    if any(not math.isfinite(v) for v in [timer,elapsed]+position) or timer<0 or elapsed<0:
        raise ValueError('Invalid saved raid timer or position.')
    return dict(start=start,end=r.pos,timer=timer,name=name,elapsed=elapsed,position=position)

def patch_raid(raw,settings):
    actions={key:settings.get(key,False) for key in RAID_ACTIONS}
    if any(not isinstance(v,bool) for v in actions.values()):raise ValueError('Raid actions must be on or off.')
    if not any(actions.values()):return raw
    raid=raid_state(raw)
    timer=0.0 if actions['resetRaidTimer'] else raid['timer']
    name,elapsed,position=('',0.0,[0.0]*3) if actions['endRaid'] else (raid['name'],raid['elapsed'],raid['position'])
    return raw[:raid['start']]+p('f',timer)+string(name)+p('ffff',elapsed,*position)+raw[raid['end']:]

def parse_chunk(raw,texts=None,tombs=None,links=None):
    r=Reader(raw);v=r.read('h');count=r.read('i')
    if v not in (40,41,42) or not 0<=count<=len(raw)//10:raise ValueError('Unsupported chunk format.')
    containers=[]
    for obj in range(count):
        object_start=r.pos;flags=r.read('H');creator=0;owner=0;grave_items=None;connection=None;strings={};strings_count=0
        pos=[r.read('h'),0,r.read('h')] if flags&0x2000 else [r.read('f') for _ in range(3)]
        prefab=r.read('i')
        if flags&0x1000:
            if not r.read('H')&0x8000:r.take(2)
        for bit,size in [(1,5),(2,4),(4,12),(8,16),(16,4),(32,8),(64,None),(128,None)]:
            if bit==64:strings_start=strings_end=r.pos;strings_data_start=r.pos
            if not flags&bit:continue
            if bit==1:
                connection=dict(start=r.pos,type=r.read('B'),hash=r.read('i'))
                continue
            entries=r.num()
            if bit==64:strings_count=entries;strings_data_start=r.pos
            for _ in range(entries):
                key=r.read('i')
                if bit==32:
                    value=r.read('q')
                    if key==hashcode('creator'):creator=value
                    if key==hashcode('owner'):owner=value
                elif size:r.take(size)
                elif bit==64:
                    start=r.pos;value=r.string();strings[key]=dict(start=start,end=r.pos,value=value)
                else:
                    start=r.pos;data=r.take(r.read('i'));end=r.pos
                    if key==hashcode('items') and prefab==hashcode('Player_tombstone'):
                        _,grave_items=inventory(data)
                    if key==hashcode('items') and creator!=0:
                        entry=dict(creator=str(creator),object=obj,position=pos,prefab_hash=prefab,start=start,end=end)
                        try:entry['version'],entry['items']=inventory(data)
                        except ValueError as e:entry['error']=str(e);entry['items']=[]
                        containers.append(entry)
            if bit==64:strings_end=r.pos
        if tombs is not None and prefab==hashcode('Player_tombstone') and owner and grave_items:
            tombs.append(dict(owner=str(owner),ownerName=strings.get(hashcode('ownerName'),{}).get('value',''),position=pos,items=grave_items))
        # Every linked portal, whoever built it, so retagging one side can unlink the other.
        if links is not None and connection and prefab in PORTAL_PREFABS:
            links.append(dict(object=obj,object_start=object_start,flags=flags,connection=connection))
        if texts is not None and creator and prefab in TEXT_PREFABS:
            kind,key=TEXT_PREFABS[prefab];field=strings.get(hashcode(key))
            texts.append(dict(object=obj,creator=str(creator),position=pos,prefab_hash=prefab,kind=kind,key=key,
              text=field['value'] if field else '',field=field,object_start=object_start,flags=flags,connection=connection,
              strings_start=strings_start,strings_end=strings_end,strings_data_start=strings_data_start,strings_count=strings_count))
    r.end();return count,containers

def generations(path):
    return sorted(int(m.group(1)) for f in path.glob('_main.*.ok') if (m:=re.fullmatch(r'_main\.(\d+)\.ok',f.name)))
def durable(path,data,created=None):
    with open(path,'xb') as f:
        if created is not None:created.append(path)
        f.write(data);flush_to_disk(f)
    if path.read_bytes()!=data:raise ValueError('Write verification failed.')
def torn_marker(path):
    # Only a short marker is an interrupted write; a full marker with an unknown version must fail closed, not be skipped.
    return len(path.read_bytes())<4
class World:
    def __init__(self,path):
        self.path=Path(str(path).strip().strip('"')).resolve()
        if self.path.is_file():self.path=self.path.parent
        nums=generations(self.path)
        if not nums:raise ValueError('Choose a Valheim 1.0 world folder containing _main.<number>.ok and .chunks files.')
        # A save interrupted while writing its marker leaves an empty or partial .ok; the previous generation is still the committed one.
        complete=[n for n in nums if not torn_marker(self.path/f'_main.{n}.ok')]
        if not complete:raise ValueError('No complete world generation: every _main.<number>.ok marker is empty or partial.')
        self.seen=nums;self.number=max(complete)
        self.markers={n:(self.path/f'_main.{n}.ok').read_bytes() for n in nums}
        self.warning=f'Generation {max(nums)} was never finished (its _main.{max(nums)}.ok marker is empty or partial), so generation {self.number} was opened. Saving writes a new, complete generation.' if self.number!=max(nums) else None
        self.files={};self.containers=[];self.texts=[];self.tombs=[];self.links=[];prefix=f'_main.{self.number}'
        for ext in ('.chunks','.fwl2','.db2','.ok'):self.files[prefix+ext]=(self.path/(prefix+ext)).read_bytes()
        self.raid=None;self.raid_error=None
        try:self.raid=raid_state(self.files[prefix+'.db2'])
        except (ValueError,UnicodeError,struct.error) as error:self.raid_error=str(error)
        self.progression=None;self.progression_error=None
        try:self.progression=progression_state(self.files[prefix+'.db2'])
        except (ValueError,UnicodeError,struct.error,OSError,EOFError) as error:self.progression_error=str(error)
        self.settings_error=None
        self.meta=metadata(self.files[prefix+'.fwl2'])
        r=Reader(self.files[prefix+'.chunks']);self.version=r.read('h');total=r.read('i');n=r.read('i')
        if self.files[prefix+'.ok']!=p('i',self.version):raise ValueError('Invalid world commit marker.')
        if self.version not in (40,41,42) or not 0<=n<=len(r.data)//11:raise ValueError('Unsupported world index.')
        self.chunks=[(r.read('H'),r.read('B'),r.read('I'),r.read('i')) for _ in range(n)];r.end()
        if len({chunk_name(c) for c in self.chunks})!=n:raise ValueError('Duplicate chunks.')
        actual=0
        for c in self.chunks:
            name=chunk_name(c);raw=(self.path/name).read_bytes();self.files[name]=raw
            texts=[];links=[];count,entries=parse_chunk(raw,texts,self.tombs,links);actual+=count
            for entry in texts:
                entry.update(id=str(len(self.texts)),chunk=name);self.texts.append(entry)
            for link in links:
                link.update(chunk=name);self.links.append(link)
            if count!=c[3]:raise ValueError('Chunk count mismatch.')
            for entry in entries:
                entry.update(id=str(len(self.containers)),chunk=name);self.containers.append(entry)
        if actual!=total:raise ValueError('World object count mismatch.')
        self.verify_source()
    def verify_source(self):
        if generations(self.path)!=self.seen:raise ValueError('World changed since opening. Reopen it before saving.')
        for n,raw in self.markers.items():
            if (self.path/f'_main.{n}.ok').read_bytes()!=raw:raise ValueError('World changed since opening. Reopen it before saving.')
        for name,raw in self.files.items():
            if (self.path/name).read_bytes()!=raw:raise ValueError('World changed since opening. Reopen it before saving.')
    def public(self):
        parts=[x.lower() for x in self.path.parts];cloud='userdata' in parts and 'remote' in parts
        return dict(name=self.path.name,path=str(self.path),generation=self.number,canSave=not cloud,containers=self.containers,texts=self.texts,warning=self.warning,
          settings={**world_settings(self.meta['keys']),**({'progression':{key:any(k.lower()==key for k in self.progression['keys']) for key in PROGRESSION_FLAGS}} if self.progression else {})} if self.meta else None,
          progressionFlags=PROGRESSION_FLAGS,progressionKeys=self.progression['keys'] if self.progression else None,progressionError=self.progression_error,
          settingsError=self.settings_error,raid=self.raid,raidError=self.raid_error,
          saveHelp='Steam Cloud world: move it to Local in Valheim Manage Saves, then quit Valheim and reopen it.' if cloud else 'Save creates a new world generation and a complete backup ZIP. Close Valheim first.')
    def build(self,changes,text_changes=None,settings=None):
        patches={};seen=set()
        for change in changes:
            key=change['id']
            if key in seen:raise ValueError('Duplicate container change.')
            seen.add(key);c=next((c for c in self.containers if c['id']==key),None)
            if not c or 'error' in c:raise ValueError('Unsupported container.')
            data=encode_inventory(c['version'],change['items'],c['items'])
            if data!=self.files[c['chunk']][c['start']+4:c['end']]:patches.setdefault(c['chunk'],[]).append((c['start'],c['end'],p('i',len(data))+data))
        meta_raw=self.files[f'_main.{self.number}.fwl2']
        new_meta=patch_settings(meta_raw,settings) if settings is not None else meta_raw
        db_raw=self.files[f'_main.{self.number}.db2']
        new_db=patch_raid(db_raw,settings) if settings is not None else db_raw
        if settings is not None and 'progression' in settings:new_db=patch_progression(new_db,settings['progression'])
        changed_texts={};disconnect=set()
        for change in text_changes or []:
            key=change['id']
            if key in changed_texts:raise ValueError('Duplicate text change.')
            entry=next((t for t in self.texts if t['id']==key),None)
            if entry is None:raise ValueError('Unknown player-created sign or portal.')
            value=change['text']
            if not isinstance(value,str) or len(value)>500 or '\x00' in value:raise ValueError('Text must be at most 500 characters, without nulls.')
            if value==entry['text']:continue
            changed_texts[key]=(entry,value)
            conn=entry['connection']
            if entry['kind']=='portal' and conn and conn['type'] in (1,17):disconnect.add(conn['hash'])
        text_objects={(t['chunk'],t['object_start']) for t in self.texts}
        peers=[dict(link,kind='portal',id=None) for link in self.links if (link['chunk'],link['object_start']) not in text_objects]
        for entry in self.texts+peers:
            change=changed_texts.get(entry['id']);conn=entry['connection'];flags=entry['flags']
            remove_conn=entry['kind']=='portal' and conn and conn['type'] in (1,17) and conn['hash'] in disconnect
            if not change and not remove_conn:continue
            dest=patches.setdefault(entry['chunk'],[])
            if change:
                value=string(change[1]);field=entry['field']
                if field:dest.append((field['start'],field['end'],value))
                else:
                    flags|=64
                    section=num(entry['strings_count']+1)+self.files[entry['chunk']][entry['strings_data_start']:entry['strings_end']]+p('i',hashcode(entry['key']))+value
                    dest.append((entry['strings_start'],entry['strings_end'],section))
            if remove_conn:
                flags&=~1;dest.append((conn['start'],conn['start']+5,b''))
            if flags!=entry['flags']:dest.append((entry['object_start'],entry['object_start']+2,p('H',flags)))
        if not patches and new_meta==meta_raw and new_db==db_raw:return None
        number=max([self.number]+[int(m.group(1)) for f in self.path.glob('_main.*.*') if (m:=re.match(r'_main\.(\d+)\.',f.name))])+1
        result={};chunks=[]
        for c in self.chunks:
            name=chunk_name(c)
            if name in patches:
                raw=self.files[name]
                for start,end,data in sorted(patches[name],reverse=True):raw=raw[:start]+data+raw[end:]
                parse_chunk(raw);v=c[2]+1
                while (self.path/chunk_name((c[0],c[1],v,c[3]))).exists():v+=1
                c=(c[0],c[1],v,c[3]);result[chunk_name(c)]=raw
            chunks.append(c)
        prefix=f'_main.{number}'
        result[prefix+'.chunks']=p('hii',self.version,sum(c[3] for c in chunks),len(chunks))+b''.join(p('HBIi',*c) for c in chunks)
        result[prefix+'.db2']=new_db
        result[prefix+'.fwl2']=new_meta
        result[prefix+'.ok']=p('i',self.version)
        return number,result
    def archive(self,files):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
            for name,data in files.items():z.writestr(self.path.name+'/'+name,data)
        result=buf.getvalue()
        with zipfile.ZipFile(io.BytesIO(result)) as z:
            if z.testzip():raise ValueError('Backup verification failed.')
            for name,data in files.items():
                if z.read(self.path.name+'/'+name)!=data:raise ValueError('Backup verification failed.')
        return result
    def export(self,changes,text_changes=None,settings=None):
        built=self.build(changes,text_changes,settings);files=dict(self.files)
        if built:files.update(built[1])
        return self.archive(files)
    def save(self,changes,ensure_closed,text_changes=None,settings=None):
        if not self.public()['canSave']:raise ValueError(self.public()['saveHelp'])
        ensure_closed();self.verify_source();built=self.build(changes,text_changes,settings)
        if not built:return dict(unchanged=True)
        number,files=built;folder=self.path/'.rune-backups';folder.mkdir(exist_ok=True)
        backup=folder/(datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.zip')
        durable(backup,self.archive(self.files));self.verify_source();ensure_closed()
        marker=f'_main.{number}.ok';staged=self.path/f'.{marker}.tmp';created=[];committed=False
        try:
            for name,data in files.items():
                if name!=marker:durable(self.path/name,data,created)
            staged.unlink(missing_ok=True);durable(staged,files[marker],created)
            self.verify_source();ensure_closed()
            # The marker appears complete or not at all, so a crash can never leave a torn commit.
            try:publish_new(staged,self.path/marker)
            except FileExistsError:raise ValueError('World changed since opening. Reopen it before saving.')
            committed=True;sync_directory(self.path)
        finally:
            staged_left=[staged] if committed else created
            for leftover in staged_left:
                try:leftover.unlink(missing_ok=True)
                except OSError:pass
        try:refreshed=World(self.path);self.__dict__.update(refreshed.__dict__)
        except (OSError,ValueError,struct.error) as e:
            return dict(unchanged=False,backup=str(backup),generation=number,reopen=True,warning=f'Saved generation {number}, but reading it back failed ({e}). Reopen the world before making more changes.')
        return dict(unchanged=False,backup=str(backup),generation=number,warning=None)
