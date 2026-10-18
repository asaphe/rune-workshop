"""Chunked-world containers. Format reference: Shuiei/valheim-world-editor (MIT)."""
import copy, io, math, os, re, struct, zipfile
from pathlib import Path
from datetime import datetime
from platforms import flush_to_disk
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

def patch_settings(raw,settings):
    meta=metadata(raw);keys=meta['keys'][:]
    if not isinstance(settings,dict) or set(settings)-MODIFIERS:raise ValueError('Unsupported world setting.')
    for key,value in settings.items():
        if not isinstance(value,bool):raise ValueError('World settings must be on or off.')
        present=any(k.lower()==key for k in keys)
        if present==value:continue
        keys=[k for k in keys if k.lower()!=key]
        if value:keys.append(key)
    if keys==meta['keys']:return raw
    result=raw[4:meta['start']]+p('i',len(keys))+b''.join(string(k) for k in keys)+raw[meta['end']:]
    result=p('i',len(result))+result;metadata(result);return result

def parse_chunk(raw,texts=None,tombs=None):
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
                        except ValueError as e:entry['error']=str(e)
                        containers.append(entry)
            if bit==64:strings_end=r.pos
        if tombs is not None and prefab==hashcode('Player_tombstone') and owner and grave_items:
            tombs.append(dict(owner=str(owner),ownerName=strings.get(hashcode('ownerName'),{}).get('value',''),position=pos,items=grave_items))
        if texts is not None and creator and prefab in TEXT_PREFABS:
            kind,key=TEXT_PREFABS[prefab];field=strings.get(hashcode(key))
            texts.append(dict(object=obj,creator=str(creator),position=pos,prefab_hash=prefab,kind=kind,key=key,
              text=field['value'] if field else '',field=field,object_start=object_start,flags=flags,connection=connection,
              strings_start=strings_start,strings_end=strings_end,strings_data_start=strings_data_start,strings_count=strings_count))
    r.end();return count,containers

def generations(path):
    return sorted(int(m.group(1)) for f in path.glob('_main.*.ok') if (m:=re.fullmatch(r'_main\.(\d+)\.ok',f.name)))
def durable(path,data):
    with open(path,'xb') as f:f.write(data);flush_to_disk(f)
    if path.read_bytes()!=data:raise ValueError('Write verification failed.')
class World:
    def __init__(self,path):
        self.path=Path(str(path).strip().strip('"')).resolve()
        if self.path.is_file():self.path=self.path.parent
        nums=generations(self.path)
        if not nums:raise ValueError('Choose a Valheim 1.0 world folder containing _main.<number>.ok and .chunks files.')
        self.number=max(nums);self.files={};self.containers=[];self.texts=[];self.tombs=[];prefix=f'_main.{self.number}'
        for ext in ('.chunks','.fwl2','.db2','.ok'):self.files[prefix+ext]=(self.path/(prefix+ext)).read_bytes()
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
            texts=[];count,entries=parse_chunk(raw,texts,self.tombs);actual+=count
            for entry in texts:
                entry.update(id=str(len(self.texts)),chunk=name);self.texts.append(entry)
            if count!=c[3]:raise ValueError('Chunk count mismatch.')
            for entry in entries:
                entry.update(id=str(len(self.containers)),chunk=name);self.containers.append(entry)
        if actual!=total:raise ValueError('World object count mismatch.')
        self.verify_source()
    def verify_source(self):
        if max(generations(self.path),default=-1)!=self.number:raise ValueError('World changed since opening. Reopen it before saving.')
        for name,raw in self.files.items():
            if (self.path/name).read_bytes()!=raw:raise ValueError('World changed since opening. Reopen it before saving.')
    def public(self):
        parts=[x.lower() for x in self.path.parts];cloud='userdata' in parts and 'remote' in parts
        return dict(name=self.path.name,path=str(self.path),generation=self.number,canSave=not cloud,containers=self.containers,texts=self.texts,
          settings={key:any(k.lower()==key for k in self.meta['keys']) for key in sorted(MODIFIERS)} if self.meta else None,
          settingsError=self.settings_error,
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
        for entry in self.texts:
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
        if not patches and new_meta==meta_raw:return None
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
        result[prefix+'.db2']=self.files[f'_main.{self.number}.db2']
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
        marker=f'_main.{number}.ok'
        for name,data in files.items():
            if name!=marker:durable(self.path/name,data)
        self.verify_source();ensure_closed();durable(self.path/marker,files[marker])
        refreshed=World(self.path);self.__dict__.update(refreshed.__dict__)
        return dict(unchanged=False,backup=str(backup),generation=number)
