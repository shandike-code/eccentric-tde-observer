"""New wiring and split-quadrature checks only; no old suite rerun."""
from pathlib import Path
from dataclasses import fields, is_dataclass
import unittest
import numpy as np
from operations.x20_86304_preparation_inflate import PayloadLedger
from operations.x20_86304_preparation_legendre_split import split_weights
from operations import x20_86304_preparation_legendre_context as new
from operations.x20_86304_preparation_motion import context_from_arrays as old_context
from eccentric_tde_observer.radiative_transfer_1d import gauss_legendre_split_mu_weights as old_split


def fixture(moving):
    rho=np.ones((2,128));rho[1]=.5 if moving else 1.
    m=dict(density_g_cm3=rho,cell_mass_g_cm2=np.ones(128),temperature_k=np.full((2,128),8192.),
        hydrogen_fraction=np.tile([.75,.25],(2,128,1)),helium_fraction=np.tile([.5,.25,.25],(2,128,1)),step_duration_s=np.ones(2))
    return m,dict(active_edge_hz=np.arange(1.,115.),maximum_beta=np.array(1e-6 if moving else 0.))


def equal(test,x,y):
    if isinstance(x,np.ndarray):
        test.assertEqual((x.dtype,x.shape,x.tobytes(),x.flags.writeable),(y.dtype,y.shape,y.tobytes(),y.flags.writeable))
    elif is_dataclass(x):
        for f in fields(x):equal(test,getattr(x,f.name),getattr(y,f.name))
    elif isinstance(x,dict):
        test.assertEqual(x.keys(),y.keys())
        for k in x:equal(test,x[k],y[k])
    elif isinstance(x,tuple):
        test.assertEqual(len(x),len(y))
        for a,b in zip(x,y):equal(test,a,b)
    else:test.assertEqual(x,y)


class WiringTests(unittest.TestCase):
    def test_split_original_bytes(self):
        for order in (4,10,22,30):
            for split in (-.5,.125,.75):
                equal(self,split_weights(order,split,PayloadLedger(),lambda:None),old_split(order,split))

    def test_split_every_checkpoint_and_budget(self):
        ticks=[];ledger=PayloadLedger()
        split_weights(22,.375,ledger,lambda:ticks.append(len(ledger.entries)))
        class Stop(Exception):pass
        for target in range(len(ticks)):
            calls=[];partial=PayloadLedger()
            def check():
                calls.append(len(partial.entries))
                if len(calls)-1==target:raise Stop()
            with self.assertRaises(Stop):split_weights(22,.375,partial,check)
            self.assertEqual(partial.entries,ledger.entries[:ticks[target]])
        total=0
        for row in ledger.entries:
            partial=PayloadLedger(total+row[1]-1)
            with self.assertRaises(ValueError):split_weights(22,.375,partial,lambda:None)
            self.assertEqual(partial.entries,ledger.entries[:len(partial.entries)])
            self.assertEqual(sum(x[1] for x in partial.entries),total)
            total+=row[1]
        self.assertFalse(any(x[0]=='quadrature:leggauss-return-capacity' for x in ledger.entries))
        l=PayloadLedger(1)
        with self.assertRaises(ValueError):split_weights(22,.375,l,lambda:None)
        self.assertEqual(l.entries,[])

    def test_split_domains(self):
        for order in (True,np.int64(18),0,3,34):
            with self.assertRaises(ValueError):split_weights(order,0.,PayloadLedger(),lambda:None)
        for split in (-1.,1.,np.nan,np.inf):
            with self.assertRaises(ValueError):split_weights(18,split,PayloadLedger(),lambda:None)

    def test_full_new_context_original_bytes(self):
        for moving in (False,True):
            for order in ('C','F'):
                m,s=fixture(moving);m={k:np.array(v,order=order) for k,v in m.items()}
                before={k:v.tobytes() for k,v in m.items()}
                equal(self,new.context_from_arrays(m,s,PayloadLedger(),lambda:None),old_context(m,s,PayloadLedger(),lambda:None))
                self.assertEqual(before,{k:v.tobytes() for k,v in m.items()})

    def test_wired_stops_at_component_boundaries(self):
        m,s=fixture(False);full=PayloadLedger();new.context_from_arrays(m,s,full,lambda:None)
        class Stop(Exception):pass
        for prefix in ('leggauss:', 'quadrature:','frequency:active:finite','frequency:mu:finite','frequency:block-outer'):
            target=next(i for i,row in enumerate(full.entries) if row[0].startswith(prefix));partial=PayloadLedger()
            def check():
                if len(partial.entries)==target:raise Stop()
            with self.assertRaises(Stop):new.context_from_arrays(m,s,partial,check)
            self.assertEqual(partial.entries,full.entries[:target])

    def test_configuration_exact_declared_changes(self):
        old=Path('operations/x20_86304_preparation_frequency_configuration.py').read_text()
        expected=old.replace('Frequency-wired memory configuration composition','Legendre-wired memory configuration composition').replace('preparation_frequency_context import','preparation_legendre_context import')
        self.assertEqual(Path('operations/x20_86304_preparation_legendre_configuration.py').read_text(),expected)

    def test_native_still_closed(self):
        from operations.x20_86304_preparation_legendre_configuration import native_configuration
        for f in (native_configuration,new.native_configuration):
            with self.assertRaises(RuntimeError):f(synthetic=True)
