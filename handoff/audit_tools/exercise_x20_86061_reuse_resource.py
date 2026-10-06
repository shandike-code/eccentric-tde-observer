"""Tiny explicit-driver lifecycle/receipt exercise. Scheduler records are synthetic.

Never calls production main, native/archived-source work, Slurm, or real dat files.
"""
import argparse
import hashlib
from pathlib import Path
import time
import numpy as np
from operations import x20_85889_chord_reuse_resource as d
from operations import x20_85889_chord_reuse_contract as c
from operations import x20_85889_chord_reuse_receipt as receipt
from handoff.audit_tools import review_x20_85889_chord_reuse_resource as reviewer


def exercise(target):
    target = Path(target); target.mkdir(exist_ok=False)
    inputs = target/'inputs'; inputs.mkdir()
    a = np.arange(33*2*3, dtype=float).reshape(33,2,3)/8+1
    claims = []
    for i, v in enumerate([a,.5*a+4,.25*a+6,a+2,.5*(a+2)+4,.25*(a+2)+6]):
        path = inputs/f'{i}.bin'; raw = v.tobytes(); path.write_bytes(raw)
        claims.append(dict(path=str(path.resolve()), size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    reference = d.v1.probe(claims, [33,2,3], d.core.Guard())
    d.v1.write_new(target/'fixture-reference.json', reference)
    repo = Path(__file__).resolve().parents[2]
    names = sorted(set([str(p.relative_to(repo)) for pattern in ('*chord*.py','*chord*.sbatch')
                       for directory in ('operations','handoff/audit_tools')
                       for p in (repo/directory).glob(pattern)]))
    code = {name:dict(size_bytes=(repo/name).stat().st_size,
                     sha256=hashlib.sha256((repo/name).read_bytes()).hexdigest()) for name in names}
    c.check_code(code, code); d.v1.write_new(target/'fixture-code.json', code)
    job = '900001'; commit = 'synthetic-fixture-not-a-production-commit'
    run = target/'run'
    def work(guard, out, timeline):
        d.v1.write_new(out/'allocation.json', dict(job_id=job, observed_unix=time.time(),
            scontrol='JobId=900001 JobState=RUNNING NumCPUs=4 NumTasks=1 NumNodes=1 Partition=Students QOS=qos_stu_default TimeLimit=00:30:00 MinMemoryNode=16G', synthetic=True))
        result = d.authenticated_probe(claims, [33,2,3], guard, timeline,
                                      lambda name, value:d.v1.write_new(out/(name+'.json'), value))
        comparison = c.compare(result['probe'], reference)
        d.v1.write_new(out/'comparison.json', comparison)
        for side in ('before','after'): d.v1.write_new(out/f'code-{side}.json', code)
        result.update(comparison=comparison, git_commit=commit, git_clean_before_after=True, job_id=job,
                      synthetic=True, peak_rss_bytes=d.core.peak_rss_bytes())
        return result
    if d.execute(run, work): raise ValueError('synthetic driver failed; preserve failure.json')
    d.v1.write_new(run/'batch-exit.json', dict(job_id=job, child_exit_status=0, recorded_unix=time.time(), synthetic=True))
    terminal = dict(job_id=job, observed_unix=time.time(), scontrol='JobId=900001 JobState=COMPLETED ExitCode=0:0', synthetic=True)
    d.v1.write_new(target/'fixture-external-terminal.json', terminal)
    d.v1.write_new(run/'scheduler-terminal.json', terminal)
    answer = reviewer.review_evidence(run, commit, code, terminal, job, reference)
    d.v1.write_new(target/'review.json', answer)
    pack = target/'small.tar.gz'; receipt.archive(run, pack, [])
    receipt.receive(pack, pack.with_suffix('.receipt.json'), target/'received')
    after = reviewer.review_evidence(target/'received', commit, code, terminal, job, reference)
    if not c.exact(answer, after): raise ValueError('receipt roundtrip')
    data = c.read(run/'result.json')
    metadata = dict(synthetic=True, production_resource_verified=False, scheduler_terminal_verified=False,
        old_field_payload_bytes=18432, new_field_payload_bytes=data['field_bytes_read'],
        total_synthetic_field_payload_bytes=18432+data['field_bytes_read'],
        arithmetic=data['probe']['arithmetic'], peak_rss_bytes=d.core.peak_rss_bytes(),
        complete_slab_exact=True, decimal_precision=80, archive_roundtrip=True, new_jobs=0, real_dat_bytes_read=0)
    d.v1.write_new(target/'metadata.json', metadata)
    return metadata


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('output', type=Path); a = p.parse_args()
    print(__import__('json').dumps(exercise(a.output)))
