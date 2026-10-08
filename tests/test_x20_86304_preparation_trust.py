"""Only new control/trust compositions; no prior decode fixture reruns."""
import copy
import unittest
import numpy as np
from eccentric_tde_observer.coupled_material_newton_krylov import (
    GroundStateLogSimplexCodec, ground_state_material_trial_within_trust_region as original_trust)
from operations.common_step21_directions import exact_trial as original_exact
from operations.x20_86304_preparation_trust import exact_control_trial, within_trust_region, native_configuration
from operations.x20_86304_preparation_inflate import PayloadLedger
from handoff.audit_tools.exercise_x20_86304_preparation_trust import fixture,LIMITS


class TrustTests(unittest.TestCase):
    def test_original_control_and_inputs(self):
        for n in (3,11,29,128):
            args=fixture(n)
            before=copy.deepcopy(args)
            self.assertIsNone(original_exact(*args,'control'))
            ledger=PayloadLedger();self.assertIsNone(exact_control_trial(*args,ledger,lambda:None))
            p=int(np.count_nonzero(args[1]['encoded_state'].reshape(n,4)[:,1]>=0))
            self.assertEqual(ledger.budget.used,1864*n+24*p+2)
            self.assertEqual(len(ledger.entries),260)
            for record,saved in zip(args,before):
                if isinstance(record,dict):
                    for key in record:self.assertEqual(record[key].tobytes(),saved[key].tobytes())
                else:self.assertEqual(record.tobytes(),saved.tobytes())

    def test_trust_nonzero_and_strided_original(self):
        for n in (3,11,29):
            a=fixture(n)[1]['encoded_state'];codec=GroundStateLogSimplexCodec(n)
            for component in range(4):
                for increment in (-1.,-.03125,0.,.03125,1.):
                    b=a.copy();b.reshape(n,4)[:,component]+=increment
                    backing=np.empty(a.size*2);backing[::2]=b;b=backing[::2]
                    self.assertEqual(within_trust_region(codec,a,b,PayloadLedger(),lambda:None,**LIMITS),
                                     original_trust(codec,a,b,**LIMITS))

    def test_each_checkpoint_and_budget(self):
        args=fixture();complete=PayloadLedger();prefixes=[]
        exact_control_trial(*args,complete,lambda:prefixes.append(list(complete.entries)))
        self.assertEqual(len(prefixes),286)
        class Stop(Exception):pass
        for target in range(1,len(prefixes)+1):
            ledger=PayloadLedger();seen=0
            def stop():
                nonlocal seen
                seen+=1
                if seen==target:raise Stop()
            with self.assertRaises(Stop):exact_control_trial(*args,ledger,stop)
            self.assertEqual(ledger.entries,prefixes[target-1])
        total=0
        for i,(_,size) in enumerate(complete.entries):
            total+=size
            if not size:continue
            # Budget requires used < limit. At a one-byte reservation,
            # total-1 can reject the preceding reservation; retain that boundary.
            for limit in (total,total-1):
                ledger=PayloadLedger(limit)
                with self.assertRaises(ValueError):exact_control_trial(*args,ledger,lambda:None)
                cumulative=0;expected=[]
                for row in complete.entries:
                    cumulative+=row[1]
                    if cumulative>=limit:break
                    expected.append(row)
                self.assertEqual(ledger.entries,expected)

    def test_all_identity_fields_reject(self):
        for record in (0,1,3):
            for key in fixture()[record]:
                args=fixture();a=args[record][key]
                if key=='phase_index':a[...]=2
                elif key=='relaxation':a[...]=.125
                else:a.flat[0]+=1.
                # old phase 0 is unused; mutate actual phase 1 for both old arrays.
                if record==3:
                    args=fixture();args[3][key][1]+=1.
                try:original_exact(*args,'control')
                except Exception as e:
                    with self.assertRaises(type(e)):exact_control_trial(*args,PayloadLedger(),lambda:None)
                else:
                    # Base decoded arrays are not original identity operands.
                    self.assertIn(key,('temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g'))
                    self.assertEqual(record,1)
        args=fixture();args[2][0]=np.nan
        with self.assertRaises(ValueError):exact_control_trial(*args,PayloadLedger(),lambda:None)

    def test_limits_and_domains(self):
        a=fixture()[1]['encoded_state'];c=GroundStateLogSimplexCodec(11)
        for key in LIMITS:
            for value in (0.,1.,-.1,np.nan,np.inf):
                limits=dict(LIMITS);limits[key]=value
                with self.assertRaises(ValueError):original_trust(c,a,a,**limits)
                ledger=PayloadLedger()
                with self.assertRaises(ValueError):within_trust_region(c,a,a,ledger,lambda:None,**limits)
                self.assertEqual(ledger.entries,[])
        for column,value in ((0,1000.),(0,-1000.),(1,np.nan),(2,np.inf)):
            b=a.copy();b.reshape(11,4)[0,column]=value
            with np.errstate(all='ignore'):
                with self.assertRaises((ValueError,ArithmeticError)) as e:original_trust(c,a,b,**LIMITS)
                with self.assertRaises(type(e.exception)):within_trust_region(c,a,b,PayloadLedger(),lambda:None,**LIMITS)

    def test_layout_and_production_refusal(self):
        for key in ('phase_index','encoded_state','temperature_k'):
            args=fixture();args[0][key]=args[0][key].astype('f4');ledger=PayloadLedger()
            with self.assertRaises(ValueError):exact_control_trial(*args,ledger,lambda:None)
            self.assertEqual(ledger.entries,[])
        with self.assertRaises(RuntimeError):native_configuration(synthetic=True)
