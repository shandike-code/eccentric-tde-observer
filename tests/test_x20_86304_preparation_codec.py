"""New tiny decode tests only; no saved scientific inputs."""
import unittest
import numpy as np
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec
from eccentric_tde_observer.source import PhysicalDomainError
from operations.x20_86304_preparation_codec import decode, native_configuration
from operations.x20_86304_preparation_inflate import PayloadLedger


def fixture(n=7):
    return np.array([[29.+i/16., (i%3-1)*.5, i/32., -i/64.] for i in range(n)]).reshape(-1)


class CodecTests(unittest.TestCase):
    def test_original_bytes_layout_and_ownership(self):
        for n in (1,7,19,128):
            for kind in ('mixed','positive','negative','strided','reverse'):
                a=fixture(n)
                if kind in ('positive','negative'): a.reshape(n,4)[:,1] = .5 if kind=='positive' else -.5
                if kind=='strided':
                    backing=np.zeros(a.size*2);backing[::2]=a;a=backing[::2]
                if kind=='reverse': a=a.reshape(n,4)[::-1].copy().reshape(-1)
                before=a.tobytes(); flags=a.flags.writeable
                codec=GroundStateLogSimplexCodec(n)
                expected=codec.decode(a); observed=decode(codec,a,PayloadLedger(),lambda:None)
                for key in expected.__dataclass_fields__:
                    x=getattr(expected,key);y=getattr(observed,key)
                    self.assertEqual((x.dtype,x.shape,x.tobytes(),x.flags.writeable),(y.dtype,y.shape,y.tobytes(),y.flags.writeable))
                    self.assertFalse(np.shares_memory(y,a))
                self.assertEqual((a.tobytes(),a.flags.writeable),(before,flags))

    def test_every_checkpoint_stops(self):
        a=fixture();c=GroundStateLogSimplexCodec(7); count=0; prefixes=[]; ledger=PayloadLedger()
        def check():
            nonlocal count
            count+=1;prefixes.append(list(ledger.entries))
        decode(c,a,ledger,check)
        class Stop(Exception): pass
        for target in range(1,count+1):
            got=PayloadLedger();seen=0
            def stop():
                nonlocal seen
                seen+=1
                if seen==target: raise Stop()
            with self.assertRaises(Stop):decode(c,a,got,stop)
            self.assertEqual(got.entries,prefixes[target-1])

    def test_every_reservation_budget(self):
        a=fixture();c=GroundStateLogSimplexCodec(7); complete=PayloadLedger()
        decode(c,a,complete,lambda:None); cumulative=0
        for i,(_,size) in enumerate(complete.entries):
            cumulative+=size
            if size==0: continue
            got=PayloadLedger(cumulative-1)
            with self.assertRaises(ValueError):decode(c,a,got,lambda:None)
            self.assertEqual(got.entries,complete.entries[:i])

    def test_domain_rejection_matches_original(self):
        c=GroundStateLogSimplexCodec(7)
        for column,value in ((0,1000.),(0,-1000.),(1,1000.),(1,-1000.),(2,1000.),(3,-1000.),(0,np.nan),(2,np.inf)):
            a=fixture();a.reshape(7,4)[0,column]=value
            with np.errstate(over='ignore',under='ignore',invalid='ignore',divide='ignore'):
                with self.assertRaises((PhysicalDomainError,ArithmeticError)) as original:c.decode(a)
                with self.assertRaises(type(original.exception)):decode(c,a,PayloadLedger(),lambda:None)

    def test_bounded_domain_and_production(self):
        for c,a in ((GroundStateLogSimplexCodec(129),fixture(129)),(GroundStateLogSimplexCodec(7),fixture().astype('f4')),(GroundStateLogSimplexCodec(7),fixture().tolist())):
            ledger=PayloadLedger()
            with self.assertRaises(ValueError):decode(c,a,ledger,lambda:None)
            self.assertEqual(ledger.entries,[])
        with self.assertRaises(RuntimeError):native_configuration(synthetic=True)

    def test_output_isolation(self):
        a=fixture();c=GroundStateLogSimplexCodec(7)
        first=decode(c,a,PayloadLedger(),lambda:None);second=decode(c,a,PayloadLedger(),lambda:None)
        for key in first.__dataclass_fields__:self.assertFalse(np.shares_memory(getattr(first,key),getattr(second,key)))
