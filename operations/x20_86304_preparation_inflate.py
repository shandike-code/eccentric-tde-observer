"""Bounded NPZ payload decoder; no ZipExtFile and no production entry.

Ledger entries cover explicit byte payload capacities, not allocator overhead or
zlib's private native workspace. Linux RLIMIT_AS is a separate process ceiling.
"""
import hashlib
import io
import stat
import struct
import sys
import zlib
from operations.x20_86304_preparation_inputs import Budget, npy_header

CHUNK = 65536
STAGE_LIMIT = 512*1024**2


class PayloadLedger:
    def __init__(self, limit=STAGE_LIMIT):
        if type(limit) is not int or not 0 < limit <= STAGE_LIMIT:
            raise ValueError('reservation ceiling')
        self.budget=Budget(limit)
        self.entries=[]

    def reserve(self,label,size):
        self.budget.charge(size)
        self.entries.append((label,size))


def members(raw,check):
    """Strict single-disk ZIP subset produced by seekable NumPy NPZ writers.

    No comments, descriptors, central ZIP64, encryption, path names or trailers.
    Local ZIP64 sizes are accepted only as the two explicit 64-bit sizes.
    """
    if type(raw) is not bytes or not 22 <= len(raw) < 32*1024**2:
        raise ValueError('compressed source size')
    end=struct.unpack_from('<4s4H2IH',raw,len(raw)-22)
    sig,disk,cd_disk,on_disk,count,cd_size,cd_offset,comment=end
    if sig!=b'PK\x05\x06' or disk or cd_disk or on_disk!=count or not 0<count<=128 or comment or cd_offset+cd_size!=len(raw)-22:
        raise ValueError('central directory')
    rows=[];pos=cd_offset;next_local=0;names=set();total=0
    for _ in range(count):
        check()
        if pos+46>len(raw)-22:raise ValueError('central truncation')
        h=struct.unpack_from('<4s6H3I5H2I',raw,pos)
        sig,made,version,flags,method,tm,dt,crc,compressed,size,nlen,xlen,clen,disk,internal,external,offset=h
        if (sig!=b'PK\x01\x02' or version not in (20,45) or flags not in (0,2048) or method not in (0,8) or
                xlen or clen or disk or offset!=next_local or
                stat.S_IFMT(external>>16) not in (0,stat.S_IFREG) or pos+46+nlen>len(raw)-22):
            raise ValueError('unsupported central member')
        name=raw[pos+46:pos+46+nlen]
        try:key=name.decode('ascii')
        except UnicodeDecodeError:raise ValueError('ASCII member name') from None
        if not key.endswith('.npy') or key=='.npy' or any(c in key for c in '/\\\0') or key in names:
            raise ValueError('member name')
        names.add(key);pos+=46+nlen
        if offset+30>cd_offset:raise ValueError('local truncation')
        local=struct.unpack_from('<4s5H3I2H',raw,offset)
        ls,lv,lf,lm,lt,ld,lc,lcs,lus,ln,lx=local
        start=offset+30+ln+lx
        if (ls!=b'PK\x03\x04' or (lv,lf,lm,lt,ld,lc,ln)!=(version,flags,method,tm,dt,crc,nlen) or
                start+compressed>cd_offset or raw[offset+30:offset+30+ln]!=name):
            raise ValueError('local identity')
        if (lcs,lus)==(0xffffffff,0xffffffff):
            if lx!=20 or struct.unpack_from('<HHQQ',raw,offset+30+ln)!=(1,16,size,compressed):
                raise ValueError('local ZIP64 sizes')
        elif lx or (lcs,lus)!=(compressed,size):raise ValueError('local sizes')
        if method==0 and compressed!=size:raise ValueError('stored size')
        total+=size
        if total>=128*1024**2:raise ValueError('decompressed source limit')
        rows.append((key[:-4],start,compressed,size,method,crc));next_local=start+compressed
    if pos!=len(raw)-22 or next_local!=cd_offset:raise ValueError('ZIP gaps or trailing data')
    return rows


def decode_member(raw,row,ledger,check):
    name,start,compressed,size,method,crc=row
    ledger.reserve(name+':output-bytearray',size)
    output=bytearray(size);written=0;position=0;pending=b''
    decoder=zlib.decompressobj(-15) if method==8 else None
    calls=0;max_input=0;max_output=0
    while position<compressed or pending:
        check()
        if not pending:
            n=min(CHUNK,compressed-position)
            ledger.reserve(name+':input-slice',n)
            pending=raw[start+position:start+position+n];position+=n
        allowance=min(CHUNK,size-written+1)
        # Reserve before zlib creates return bytes and its exposed tail bytes.
        ledger.reserve(name+':returned-and-tail-capacity',allowance+2*len(pending))
        before=len(pending);max_input=max(max_input,before)
        if method==8:
            chunk=decoder.decompress(pending,allowance)
            pending=decoder.unconsumed_tail
            if decoder.unused_data:raise ValueError('trailing deflate stream')
        else:chunk=pending;pending=b''
        calls+=1;max_output=max(max_output,len(chunk))
        if len(chunk)>allowance or written+len(chunk)>size:raise ValueError('decompression overrun')
        output[written:written+len(chunk)]=chunk;written+=len(chunk)
        if method==8 and not chunk and len(pending)==before:raise ValueError('deflate stalled')
    check()
    if written!=size or (decoder is not None and not decoder.eof):raise ValueError('truncated deflate output')
    if zlib.crc32(output)!=crc:raise ValueError('member CRC')
    ledger.reserve(name+':immutable-output',size)
    return bytes(output),dict(calls=calls,max_input_bytes=max_input,max_output_bytes=max_output,
                              compressed_payload_bytes=compressed,decompressed_payload_bytes=written)


class BoundedArrayLoader:
    def __init__(self,stage_limit=STAGE_LIMIT):
        self.ledger=PayloadLedger(stage_limit);self.loaded=set();self.events=[]

    def npz(self,raw,sha,label,check):
        if type(raw) is not bytes or hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('source SHA')
        if label in self.loaded:raise ValueError('duplicate load')
        self.loaded.add(label)
        rows=members(raw,check);decoded={}
        for row in rows:
            value,event=decode_member(raw,row,self.ledger,check)
            header=npy_header(io.BytesIO(value),len(value))
            if header['fortran_order']:raise ValueError('Fortran order')
            decoded[row[0]]=(value,header);self.events.append(dict(label=label,member=row[0],**event))
        import numpy as np
        arrays={}
        for name,(value,h) in decoded.items():
            check();a=np.frombuffer(value,dtype=h['dtype'],offset=h['offset']).reshape(h['shape'])
            self.ledger.reserve(name+':finite-mask',a.size)
            if a.dtype.kind in 'fc' and not np.all(np.isfinite(a)):raise ValueError('nonfinite array')
            if a.dtype.kind=='b' and any(x not in (0,1) for x in memoryview(value)[h['offset']:]):raise ValueError('boolean storage')
            arrays[name]=a
        return arrays

    def facts(self):
        return dict(explicit_payload_capacity_reserved_bytes=self.ledger.budget.used,
            events=self.events,private_zlib_workspace_metered=False,all_scientific_temporaries_metered=False,
            total_rss_bound_claimed=False,production_authorized=False)


def install_address_space_limit(limit=1024**3):
    """Linux-only irreversible ceiling, to install in a disposable trusted child.

    Covers future virtual memory growth including C/NumPy/zlib allocations, not
    resident-memory accounting. Does not prevent filesystem access or authenticate
    the interpreter. Call before exec for startup coverage; no such wiring here.
    """
    if sys.platform!='linux':raise RuntimeError('Linux-only address-space ceiling')
    if type(limit) is not int or not 0<limit<=1024**3:raise ValueError('address-space ceiling')
    import resource
    soft,hard=resource.getrlimit(resource.RLIMIT_AS)
    if soft!=resource.RLIM_INFINITY:limit=min(limit,soft)
    if hard!=resource.RLIM_INFINITY:limit=min(limit,hard)
    resource.setrlimit(resource.RLIMIT_AS,(limit,limit))
    if resource.getrlimit(resource.RLIMIT_AS)!=(limit,limit):raise RuntimeError('limit not installed')
    return dict(virtual_address_space_limit_bytes=limit,rss_limit=False,filesystem_guard=False)


def native_configuration(*args,**kwargs):
    raise RuntimeError('DO NOT RUN: decoder and address ceiling not integrated into production')
