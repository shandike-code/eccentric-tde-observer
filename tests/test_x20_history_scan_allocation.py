import pytest
from operations import x20_history_scan_v2 as m


def env(monkeypatch,cpus=4,memory=16384):
    for k,v in dict(SLURM_JOB_ID='synthetic',SLURM_CPUS_PER_TASK=str(cpus),SLURM_MEM_PER_NODE=str(memory),NUMPY_MADVISE_HUGEPAGE='0').items():monkeypatch.setenv(k,v)


def test_actual_default_resource_shape_passes(monkeypatch):
    env(monkeypatch);m.require_scan_allocation()
    # 冻结旧入口确实会把4CPU误当4worker；回归证据不可只mock掉内存守卫。
    with pytest.raises(RuntimeError,match='6 GiB per worker'):m.pipeline.require_allocation(4)


def test_resources_still_enforced(monkeypatch):
    env(monkeypatch,cpus=2)
    with pytest.raises(RuntimeError,match='four allocated'):m.require_scan_allocation()
    env(monkeypatch,memory=4096)
    with pytest.raises(RuntimeError,match='6 GiB per worker'):m.require_scan_allocation()
    monkeypatch.delenv('SLURM_JOB_ID')
    with pytest.raises(RuntimeError,match='Slurm'):m.require_scan_allocation()
