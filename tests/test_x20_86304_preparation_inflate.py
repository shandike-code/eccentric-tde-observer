"""New synthetic decoder tests; does not rerun native configuration."""
import hashlib
import io
import struct
import unittest
import zipfile
import zlib
import numpy as np
from operations import x20_86304_preparation_inflate as core


def archive(array, compressed=True):
    out=io.BytesIO()
    (np.savez_compressed if compressed else np.savez)(out,value=array)
    return out.getvalue()


def load(raw, **kwargs):
    loader=core.BoundedArrayLoader(**kwargs)
    arrays=loader.npz(raw,hashlib.sha256(raw).hexdigest(),'fixture',lambda:None)
    return arrays,loader


class DecoderTests(unittest.TestCase):
    def test_stored_and_deflated(self):
        for compressed in (False,True):
            a=np.arange(20000,dtype='<f8').reshape(100,200)
            raw=archive(a,compressed)
            arrays,loader=load(raw)
            self.assertEqual(arrays['value'].tobytes(),a.tobytes())
            self.assertFalse(arrays['value'].flags.writeable)
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                oracle=z.read('value.npy')
            row=core.members(raw,lambda:None)[0]
            decoded,event=core.decode_member(raw,row,core.PayloadLedger(),lambda:None)
            self.assertEqual(decoded,oracle)
            self.assertLessEqual(event['max_input_bytes'],65536)
            self.assertLessEqual(event['max_output_bytes'],65536)
            self.assertFalse(loader.facts()['all_scientific_temporaries_metered'])

    def test_high_compression_multiple_outputs(self):
        arrays,loader=load(archive(np.zeros(40000)))
        self.assertEqual(arrays['value'].tobytes(),bytes(320000))
        self.assertGreater(loader.events[0]['calls'],4)

    def test_crc(self):
        raw=archive(np.arange(10.))
        row=list(core.members(raw,lambda:None)[0]);row[-1]^=1
        with self.assertRaisesRegex(ValueError,'CRC'):
            core.decode_member(raw,row,core.PayloadLedger(),lambda:None)

    def test_output_overrun(self):
        raw=archive(np.zeros(1000))
        row=list(core.members(raw,lambda:None)[0]);row[3]=4
        with self.assertRaisesRegex(ValueError,'overrun'):
            core.decode_member(raw,row,core.PayloadLedger(),lambda:None)

    def test_truncated_stream(self):
        raw=archive(np.arange(1000.))
        row=list(core.members(raw,lambda:None)[0]);row[2]-=1
        with self.assertRaisesRegex(ValueError,'truncated'):
            core.decode_member(raw,row,core.PayloadLedger(),lambda:None)

    def test_trailing_stream(self):
        compressor=zlib.compressobj(wbits=-15)
        encoded=compressor.compress(b'abc')+compressor.flush()+b'junk'
        with self.assertRaisesRegex(ValueError,'trailing'):
            core.decode_member(encoded,('a',0,len(encoded),3,8,zlib.crc32(b'abc')),core.PayloadLedger(),lambda:None)

    def test_budget_before_output(self):
        raw=archive(np.zeros(1000))
        ledger=core.PayloadLedger(10)
        with self.assertRaises(Exception):core.decode_member(raw,core.members(raw,lambda:None)[0],ledger,lambda:None)
        self.assertEqual(ledger.entries,[])

    def test_stop(self):
        raw=archive(np.zeros(1000))
        def stop():raise InterruptedError('synthetic stop')
        with self.assertRaises(InterruptedError):core.members(raw,stop)
        with self.assertRaises(InterruptedError):core.decode_member(raw,core.members(raw,lambda:None)[0],core.PayloadLedger(),stop)

    def test_sha(self):
        with self.assertRaisesRegex(ValueError,'SHA'):
            core.BoundedArrayLoader().npz(archive(np.ones(1)),'0'*64,'a',lambda:None)

    def test_duplicate_label(self):
        raw=archive(np.ones(1));_,loader=load(raw)
        with self.assertRaisesRegex(ValueError,'duplicate'):
            loader.npz(raw,hashlib.sha256(raw).hexdigest(),'fixture',lambda:None)

    def test_trailer_and_comment(self):
        raw=archive(np.ones(1))
        with self.assertRaises(ValueError):load(raw+b'x')
        b=io.BytesIO(raw)
        with zipfile.ZipFile(b,'a') as z:z.comment=b'comment'
        with self.assertRaises(ValueError):load(b.getvalue())

    def test_member_names(self):
        for name in ('../x.npy','x/y.npy','x.txt','.npy'):
            out=io.BytesIO()
            with zipfile.ZipFile(out,'w') as z:z.writestr(name,b'x')
            with self.assertRaises(ValueError):load(out.getvalue())

    def test_duplicate_member(self):
        out=io.BytesIO()
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',UserWarning)
            with zipfile.ZipFile(out,'w') as z:
                z.writestr('x.npy',b'x');z.writestr('x.npy',b'x')
        with self.assertRaises(ValueError):load(out.getvalue())

    def test_central_size_limit(self):
        raw=bytearray(archive(np.ones(1)));central=raw.index(b'PK\x01\x02')
        struct.pack_into('<I',raw,central+24,128*1024**2)
        with self.assertRaises(ValueError):load(bytes(raw))

    def test_nonfinite(self):
        with self.assertRaisesRegex(ValueError,'nonfinite'):load(archive(np.array([float('nan')])))

    def test_fortran(self):
        with self.assertRaisesRegex(ValueError,'Fortran'):load(archive(np.asfortranarray(np.ones((2,3)))))

    def test_object(self):
        with self.assertRaises(ValueError):load(archive(np.array([object()],dtype=object)))

    def test_limits(self):
        for n in (True,0,-1,core.STAGE_LIMIT+1):
            with self.assertRaises(ValueError):core.PayloadLedger(n)

    def test_production_closed(self):
        with self.assertRaises(RuntimeError):core.native_configuration(synthetic=True)

if __name__=='__main__':unittest.main()
