"""Only tiny standard-library fault injection; no native/data entry point."""
import json
from pathlib import Path
import sys

from operations.x20_86304_preparation_supervisor import supervise


def exercise(destination):
    destination=Path(destination); destination.mkdir(exist_ok=False)
    boundary=Path(__file__).resolve().parents[2]/'operations/x20_86304_preparation_boundary.py'
    preamble=f'''import time
started=time.monotonic()
import runpy,signal,os
b=runpy.run_path({str(boundary)!r})
'''
    cases={
        'normal': (preamble+"g=b['StopGuard'](started);g.install();print(g.check())",150),
        'rss': (preamble+"g=b['StopGuard'](started,rss_bytes=1);g.install()",3),
        'time': (preamble+"g=b['StopGuard'](started,seconds=.1);g.install();time.sleep(30)",3),
        'signal': (preamble+"g=b['StopGuard'](started);g.install();os.kill(os.getpid(),signal.SIGUSR1)",3),
        'ignored': (preamble+"signal.signal(signal.SIGALRM,signal.SIG_IGN);signal.signal(signal.SIGTERM,signal.SIG_IGN);signal.setitimer(signal.ITIMER_REAL,.05);print('partial',flush=True);time.sleep(30)",.5),
        'partial': ("print('partial',flush=True);raise RuntimeError('injected partial failure')",3),
        'parent_signal': ("import os,signal,time;os.kill(os.getppid(),signal.SIGUSR1);time.sleep(30)",3),
        'output': ("import os;os.write(1,b'x'*65536)",3),
    }
    results={}
    for name,(code,limit) in cases.items():
        results[name]=supervise([sys.executable,'-I','-S','-c',code],destination/name,
            outer_seconds=limit,output_limit=257 if name=='output' else 8*1024**2)
    summary={'synthetic':True,'complete_native_context_verified':False,
        'production_resource_stop_guards_integrated':False,
        'whole_lifecycle_guard_verified':False,'cases':results}
    with (destination/'summary.json').open('x') as f:json.dump(summary,f,indent=2)
    return summary


if __name__=='__main__':
    exercise(sys.argv[1])
