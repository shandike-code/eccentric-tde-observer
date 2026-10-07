import numpy as np
import pytest
from operations.x20_86304_preparation_leggauss import nodes_weights

class Ledger:
    def __init__(self, limit=1000000):
        self.entries=[];self.total=0;self.limit=limit
    def reserve(self,label,size):
        assert type(size) is int and size>=0
        if self.total+size>self.limit:raise MemoryError('capacity')
        self.total+=size;self.entries.append((label,size))

class Stopped(Exception):pass


def test_all_degrees_original_bytes_flags():
    for n in range(1,17):
        ledger=Ledger(); got=nodes_weights(n,ledger,lambda:None)
        expected=np.polynomial.legendre.leggauss(n)
        for a,b in zip(got,expected):
            assert a.dtype==b.dtype and a.shape==b.shape
            assert a.tobytes()==b.tobytes()
            assert a.flags.writeable==b.flags.writeable
        assert ledger.total>2*n*8


def test_every_checkpoint_stops():
    for n in (1,2,16):
        total=[0]
        def count():total[0]+=1
        nodes_weights(n,Ledger(),count)
        for target in range(1,total[0]+1):
            calls=[0]
            def stop():
                calls[0]+=1
                if calls[0]==target:raise Stopped
            with pytest.raises(Stopped):nodes_weights(n,Ledger(),stop)
            assert calls[0]==target


def test_every_reservation_budget():
    for n in (1,2,16):
        baseline=Ledger();nodes_weights(n,baseline,lambda:None)
        cumulative=0
        for index,(_,size) in enumerate(baseline.entries):
            limited=Ledger(cumulative+size-1)
            with pytest.raises(MemoryError):nodes_weights(n,limited,lambda:None)
            assert limited.entries==baseline.entries[:index]
            cumulative+=size


def test_domain():
    for value in (True,False,0,17,-1,1.0,np.int64(2),'2',None):
        ledger=Ledger()
        with pytest.raises(ValueError):nodes_weights(value,ledger,lambda:None)
        assert ledger.entries==[]


def test_fresh_outputs():
    a=nodes_weights(5,Ledger(),lambda:None)
    saved=[v.tobytes() for v in a]
    b=nodes_weights(5,Ledger(),lambda:None)
    b[0][0]=123
    assert [v.tobytes() for v in a]==saved
