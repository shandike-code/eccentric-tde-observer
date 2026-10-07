import unittest
from dataclasses import fields, replace
import numpy as np
from operations import x20_86304_preparation_stencil as new
from operations.x20_86304_preparation_inflate import PayloadLedger
from eccentric_tde_observer.mixed_frame_ale import mixed_frame_frequency_stencil_from_active_edges as old_stencil
from eccentric_tde_observer.mixed_frame_frequency import lorentz_ray_transform as old_rays
from eccentric_tde_observer.mixed_frame_streaming import plan_mixed_frame_frequency_blocks as old_plan


def fixture():
    return np.array([2.**i for i in range(10)]),np.array([-.75,-.25,.25,.75]),np.full(4,.5),np.array([-.125,0.,.125])


def equal(test,a,b):
    for f in fields(a):
        x=getattr(a,f.name);y=getattr(b,f.name)
        if isinstance(x,np.ndarray):test.assertEqual((x.dtype,x.shape,x.tobytes(),x.flags.writeable),(y.dtype,y.shape,y.tobytes(),y.flags.writeable))
        elif hasattr(x,'__dataclass_fields__'):equal(test,x,y)
        else:test.assertEqual(x,y)


class FrequencyTests(unittest.TestCase):
    def test_original_zero_and_moving(self):
        for speed in (0.,.25):
            edge,mu,w,b=fixture()
            if speed==0:b*=0
            ledger=PayloadLedger();grid=new.stencil(edge,speed,ledger,lambda:None)
            equal(self,grid,old_stencil(edge,speed));equal(self,new.rays(mu,w,b,ledger,lambda:None),old_rays(mu,w,b))
            actual=new.plan(grid,mu,w,b,4,ledger,lambda:None);expected=old_plan(old_stencil(edge,speed),mu,w,b,4)
            self.assertEqual(len(actual),3)
            for x,y in zip(actual,expected):equal(self,x,y)

    def test_strided_inputs_unchanged(self):
        edge,mu,w,b=fixture();edge=np.repeat(edge,2)[::2];mu=mu[::-1];w=w[::-1];b=b[::-1]
        before=[a.tobytes() for a in (edge,mu,w,b)]
        l=PayloadLedger();equal(self,new.stencil(edge,.25,l,lambda:None),old_stencil(edge,.25))
        equal(self,new.rays(mu,w,b,l,lambda:None),old_rays(mu,w,b))
        self.assertEqual(before,[a.tobytes() for a in (edge,mu,w,b)])

    def test_each_reservation_stops(self):
        edge,mu,w,b=fixture()
        def run(l,c):g=new.stencil(edge,.25,l,c);return new.plan(g,mu,w,b,4,l,c)
        full=PayloadLedger();run(full,lambda:None)
        class Stop(Exception):pass
        for n in range(len(full.entries)):
            l=PayloadLedger()
            def check():
                if len(l.entries)==n:raise Stop()
            with self.assertRaises(Stop):run(l,check)
            self.assertEqual(l.entries,full.entries[:n])

    def test_budget_before_array(self):
        e,mu,w,b=fixture();l=PayloadLedger(9)
        with self.assertRaises(ValueError):new.stencil(e,.25,l,lambda:None)
        self.assertEqual(l.entries,[])

    def test_invalid_domains(self):
        e,mu,w,b=fixture()
        for x in (e.astype('float32'),e[::-1],np.array([0.,1.]),np.array([1.,np.inf]),np.ones(9634)):
            with self.assertRaises((ValueError,new.PhysicalDomainError)):new.stencil(x,.25,PayloadLedger(),lambda:None)
        for speed in (-1.,1.,np.nan):
            with self.assertRaises(new.PhysicalDomainError):new.stencil(e,speed,PayloadLedger(),lambda:None)
        for x in (np.array([1.]),np.array([np.nan])):
            with self.assertRaises(new.PhysicalDomainError):new.rays(mu,w,x,PayloadLedger(),lambda:None)
        with self.assertRaises(new.PhysicalDomainError):new.rays(mu,w*2,b,PayloadLedger(),lambda:None)

    def test_guard_insufficient_and_core_bool(self):
        e,mu,w,b=fixture();g=new.stencil(e,0.,PayloadLedger(),lambda:None)
        with self.assertRaises(new.PhysicalDomainError):new.plan(g,mu,w,b,4,PayloadLedger(),lambda:None)
        with self.assertRaises(ValueError):new.plan(g,mu,w,b,True,PayloadLedger(),lambda:None)
        g=replace(g,outer_lab_edge_hz=np.repeat(g.outer_lab_edge_hz,2)[::2])
        with self.assertRaises(ValueError):new.plan(g,mu,w,b,4,PayloadLedger(),lambda:None)

    def test_production_closed(self):
        with self.assertRaises(RuntimeError):new.native_configuration(synthetic=True)
