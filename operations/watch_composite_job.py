"""Bounded read-only Slurm terminal capture; never submits or cancels jobs."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time

TERMINAL={'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True,type=int);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--seconds',type=int,default=86400);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    end=time.monotonic()+a.seconds
    while time.monotonic()<end:
        r=subprocess.run(['scontrol','show','job','-o',str(a.job)],capture_output=True,text=True,timeout=20)
        state=re.search(r'\bJobState=(\S+)',r.stdout)
        if state and state.group(1).split('+')[0] in TERMINAL:
            payload={'job_id':a.job,'state':state.group(1),'observed_unix':time.time(),'scontrol':r.stdout,'stderr':r.stderr}
            temp=a.output/'scheduler-terminal.json.tmp';temp.write_text(json.dumps(payload,indent=2)+'\n');temp.replace(a.output/'scheduler-terminal.json');return
        if r.returncode and not (a.output/'scheduler-last-error.txt').exists():
            (a.output/'scheduler-last-error.txt').write_text(r.stderr)
        time.sleep(30)
    (a.output/'scheduler-terminal-unavailable.json').write_text(json.dumps({'job_id':a.job,'reason':'bounded watcher expired without observed terminal; no state inferred'})+'\n')

if __name__=='__main__':main()
