"""New bounded header/interface tests; no old test suite or native execution."""
import hashlib
import io
import struct
import unittest
import numpy as np
from operations.x20_86304_preparation_headers import HeaderArrayLoader, header_from_bytes
from operations.x20_86304_preparation_inflate import PayloadLedger


def npy(a, version=(1,0)):
    out=io.BytesIO();np.lib.format.write_array(out,a,version=version,allow_pickle=False)
    return out.getvalue()


def encoded(header, payload=b''):
    h=(header+'\n').encode('ascii')
    return b'\x93NUMPY\x01\x00'+struct.pack('<H',len(h))+h+payload


class HeaderTests(unittest.TestCase):
    def parse(self,raw):return header_from_bytes(raw,PayloadLedger(),lambda:None)

    def test_three_versions(self):
        for v in ((1,0),(2,0),(3,0)):
            raw=npy(np.arange(12,dtype='<f8').reshape(3,4),v)
            h=self.parse(raw)
            self.assertEqual(h['shape'],[3,4]);self.assertEqual(h['payload_bytes'],96)
            self.assertEqual(len(raw),h['offset']+96)

    def test_scalar_empty_and_rank_eight(self):
        for shape in ((),(0,),(1,)*8):
            h=self.parse(npy(np.zeros(shape)))
            self.assertEqual(h['shape'],list(shape))

    def test_supported_types(self):
        for dt in ('?','i1','u2','<i4','>i8','<f4','>f8','c8','c16','S3','U2'):
            a=np.zeros((2,3),dtype=dt);raw=npy(a)
            loader=HeaderArrayLoader(lambda:None)
            result=loader.npy(raw,hashlib.sha256(raw).hexdigest())
            self.assertEqual(result.dtype,a.dtype);self.assertEqual(result.tobytes(),a.tobytes())
            self.assertFalse(result.flags.writeable)

    def test_reordered_keys(self):
        h=self.parse(encoded("{'shape': (1,), 'descr': '<f8', 'fortran_order': False}",bytes(8)))
        self.assertEqual(h['shape'],[1])

    def test_bad_keys(self):
        for h in ("{'descr':'<f8','descr':'<f8','shape':()}","{'descr':'<f8','unknown':False,'shape':()}"):
            with self.assertRaisesRegex(ValueError,'keys'):self.parse(encoded(h,bytes(8)))

    def test_reject_python_expressions(self):
        for h in ("dict(descr='<f8')","{'descr':'<f8','fortran_order':False,'shape':(2*3,)}",
                  "{'descr':'<f8','fortran_order':False,'shape':(True,)}",
                  "{'descr':'<f8','fortran_order':False,'shape':(-1,)}"):
            with self.assertRaises(ValueError):self.parse(encoded(h))

    def test_shape_rejections(self):
        for shape in ('(1)','(01,)','(1,1,1,1,1,1,1,1,1)','(134217728,)','(999999999999999999999,)'):
            with self.assertRaises(ValueError):self.parse(encoded("{'descr':'<f8','fortran_order':False,'shape':"+shape+"}"))

    def test_dtype_rejections(self):
        for dt in ('|O8','<f16','<b8','<i3','<f0','<f0008'):
            with self.assertRaises(ValueError):self.parse(encoded("{'descr':'"+dt+"','fortran_order':False,'shape':()}"))

    def test_header_length_truncation_and_trailer(self):
        raw=npy(np.ones(1))
        for bad in (raw[:9],raw[:-1],raw+b'x',raw[:8]+b'\xff\xff'+raw[10:]):
            with self.assertRaises(ValueError):self.parse(bad)

    def test_long_token_and_nested(self):
        for text in ("{'"+'a'*100+"':0}","["*10000):
            with self.assertRaises(ValueError):self.parse(encoded(text))

    def test_stop_and_exact_budget_exception(self):
        raw=npy(np.ones(1));ledger=PayloadLedger(2)
        with self.assertRaisesRegex(ValueError,'strict byte limit'):
            header_from_bytes(raw,ledger,lambda:None)
        self.assertEqual(ledger.entries,[])
        def stop():raise InterruptedError('header stop')
        with self.assertRaises(InterruptedError):header_from_bytes(raw,PayloadLedger(),stop)

    def test_padding_stop_checks(self):
        raw=encoded("{'descr':'<f8','fortran_order':False,'shape':()}"+' '*8000,bytes(8))
        calls=[];header_from_bytes(raw,PayloadLedger(),lambda:calls.append(1))
        self.assertGreater(len(calls),125)

    def test_npz_new_wiring(self):
        out=io.BytesIO();a=np.arange(12.).reshape(3,4);np.savez_compressed(out,a=a)
        raw=out.getvalue();loader=HeaderArrayLoader(lambda:None)
        arrays=loader.npz(raw,hashlib.sha256(raw).hexdigest(),'synthetic')
        self.assertEqual(arrays['a'].tobytes(),a.tobytes())
        self.assertEqual(loader.facts()['header_payload_copy_bytes'],0)
        self.assertFalse(loader.facts()['header_ast_created'])
        with self.assertRaisesRegex(ValueError,'duplicate'):loader.npz(raw,hashlib.sha256(raw).hexdigest(),'synthetic')

    def test_copy_mirror_capacity_and_values(self):
        loader=HeaderArrayLoader(lambda:None);a=np.arange(12.).reshape(3,4)
        c=loader.copy(a);m=loader.mirror(c)
        self.assertEqual(loader.facts()['explicit_payload_capacity_reserved_bytes'],288)
        self.assertEqual(m.tobytes(),a.tobytes()+a[::-1].tobytes())
        self.assertFalse(np.shares_memory(c,a))
        with self.assertRaisesRegex(ValueError,'strict byte limit'):HeaderArrayLoader(lambda:None,96).copy(a)

    def test_nonfinite_and_fortran(self):
        for a in (np.array([np.inf]),np.asfortranarray(np.ones((2,3)))):
            raw=npy(a)
            with self.assertRaises(ValueError):HeaderArrayLoader(lambda:None).npy(raw,hashlib.sha256(raw).hexdigest())

    def test_sha_and_mutability(self):
        raw=npy(np.ones(1))
        for b,sha in ((raw,'0'*64),(bytearray(raw),hashlib.sha256(raw).hexdigest())):
            with self.assertRaises(ValueError):HeaderArrayLoader(lambda:None).npy(b,sha)

    def test_boolean_scan_checkpoint_and_storage(self):
        raw=npy(np.ones(65537,dtype=bool));calls=[]
        loader=HeaderArrayLoader(lambda:calls.append(1))
        a=loader.npy(raw,hashlib.sha256(raw).hexdigest())
        self.assertFalse(a.flags.writeable)
        self.assertGreater(len(calls),20)
        bad=raw[:-1]+b'\x02'
        with self.assertRaisesRegex(ValueError,'boolean storage'):
            HeaderArrayLoader(lambda:None).npy(bad,hashlib.sha256(bad).hexdigest())

    def test_production_closed(self):
        from operations.x20_86304_preparation_headers import native_configuration
        with self.assertRaises(RuntimeError):native_configuration(synthetic=True)

if __name__=='__main__':unittest.main()
