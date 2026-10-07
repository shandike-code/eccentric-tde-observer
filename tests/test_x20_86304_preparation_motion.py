import ast
from pathlib import Path
import unittest
import numpy as np
from operations.x20_86304_preparation_inflate import PayloadLedger
from operations import x20_86304_preparation_motion as motion


def fixture():
    material = dict(density_g_cm3=np.array([[1.]*128,[.5]*128,[.25]*128]),
        cell_mass_g_cm2=np.ones(128),temperature_k=np.full((3,128),8192.),
        hydrogen_fraction=np.tile([.75,.25],(3,128,1)),
        helium_fraction=np.tile([.5,.25,.25],(3,128,1)),step_duration_s=np.ones(3))
    master=dict(active_edge_hz=np.arange(1.,67.),maximum_beta=np.array(1e-6))
    return material,master


class MotionTests(unittest.TestCase):
    def test_nonzero_phase_and_scalar_oracle(self):
        m,s=fixture();ledger=PayloadLedger();v=motion.context_from_arrays(m,s,ledger,lambda:None)
        self.assertEqual((v['phase'],v['following'],v['duration_s']),(2,0,1.))
        face=[(float(i-128)-4.*float(i-128))/motion.LIGHT_SPEED_CM_S for i in range(257)]
        parent=[.5*(face[i]+face[i+1]) for i in range(256)]
        self.assertEqual(v['face_beta'][2].tobytes(),np.array(face).tobytes())
        self.assertEqual(v['parent_beta'].tobytes(),np.array(parent).tobytes())
        self.assertEqual(v['beta'].tobytes(),np.array([x for x in parent for _ in range(16)]).tobytes())
        self.assertEqual([(b.core_group_start,b.core_group_stop) for b in v['blocks']],[(0,65)])

    def test_original_motion_tree(self):
        from operations.x20_86304_preparation_context import context_from_arrays
        for order in ('C','F'):
            m,s=fixture();m={k:np.array(v,order=order) for k,v in m.items()}
            a=context_from_arrays(m,s,lambda:None)
            b=motion.context_from_arrays(m,s,PayloadLedger(),lambda:None)
            for k in ('face_beta','parent_beta','beta','mu','weight'):self.assertEqual(a[k].tobytes(),b[k].tobytes())
            for k in ('phase','following','duration_s','selected_block_index','identified_live_bytes'):self.assertEqual(a[k],b[k])

    def test_every_reservation_stops(self):
        m,s=fixture();complete=PayloadLedger();motion.context_from_arrays(m,s,complete,lambda:None)
        class Stop(Exception):pass
        for target in range(len(complete.entries)):
            ledger=PayloadLedger()
            def check():
                if len(ledger.entries)==target:raise Stop()
            with self.assertRaises(Stop):motion.context_from_arrays(m,s,ledger,check)
            self.assertEqual(ledger.entries,complete.entries[:target])

    def test_validation_and_budget(self):
        for role,key,value in [('m','step_duration_s',0.),('s','active_edge_hz',0.),('s','maximum_beta',1.)]:
            m,s=fixture();a=(m if role=='m' else s)[key];a.flat[0]=value
            with self.assertRaises(ValueError):motion.context_from_arrays(m,s,PayloadLedger(),lambda:None)
        m,s=fixture();ledger=PayloadLedger(384)
        with self.assertRaises(ValueError):motion.context_from_arrays(m,s,ledger,lambda:None)
        self.assertEqual(ledger.entries,[])

    def test_configuration_only_declared_edits(self):
        old=Path('operations/x20_86304_preparation_header_configuration.py').read_text()
        new=Path('operations/x20_86304_preparation_motion_configuration.py').read_text()
        expected=old.replace('Bounded-header memory configuration composition','Column/motion-metered memory configuration composition').replace('from operations.x20_86304_preparation_context import','from operations.x20_86304_preparation_motion import').replace("validate_arrays(loaded['old'], loaded['master'])","validate_arrays(loaded['old'], loaded['master'], meter.ledger, check)").replace("context_from_arrays(loaded['old'],loaded['master'],check)","context_from_arrays(loaded['old'],loaded['master'],meter.ledger,check)")
        self.assertEqual(new,expected)

    def test_production_closed(self):
        from operations.x20_86304_preparation_motion_configuration import native_configuration
        with self.assertRaises(RuntimeError):native_configuration(synthetic=True)
        with self.assertRaises(RuntimeError):motion.native_configuration(synthetic=True)


if __name__=='__main__':unittest.main()
