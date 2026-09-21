"""Lightweight exec boundary plus independent /proc memory observation for workers.

No NumPy/science imports: the native grandchild inherits this small address space.
USR1 lets the current worker finish; TERM/INT forward administrative termination.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import time


def memory(pid):
    values={}
    try:
        for line in Path(f'/proc/{pid}/status').read_text().splitlines():
            if line.startswith(('VmRSS:','VmHWM:')):
                k,v,*_=line.split();values[k[:-1]+'_kib']=int(v)
    except (FileNotFoundError,ProcessLookupError):pass
    return values


def run(command,receipt,limit_kib):
    child=None;signals=[]
    def handler(number,frame):
        signals.append(number)
        if number!=signal.SIGUSR1 and child is not None and child.poll() is None:child.send_signal(number)
    for s in (signal.SIGUSR1,signal.SIGTERM,signal.SIGINT):signal.signal(s,handler)
    relay_before=memory(os.getpid());inherited=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    started=time.monotonic();child=subprocess.Popen(command)
    peak=0;samples=0;first={}
    while True:
        fields=memory(child.pid)
        if fields:
            if not first:first=fields
            samples+=1;peak=max(peak,fields.get('VmHWM_kib',0),fields.get('VmRSS_kib',0))
        rc=child.poll()
        if rc is not None:break
        time.sleep(.1)
    payload={'native_pid':child.pid,'returncode':rc,'wall_s':time.monotonic()-started,
             'proc_sample_count':samples,'native_observed_peak_kib':peak,'native_first_sample':first,
             'relay_proc_before':relay_before,'relay_inherited_ru_maxrss_kib':inherited,
             'limit_kib':limit_kib,'memory_guard_passed':samples>0 and peak<limit_kib,
             'signals':signals,'note':'/proc samples are independent observations; native ru_maxrss guard remains unchanged.'}
    receipt=Path(receipt);receipt.parent.mkdir(parents=True,exist_ok=True);tmp=receipt.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload,indent=2)+'\n');tmp.replace(receipt)
    if rc:return rc if rc>0 else 128-rc
    if not payload['memory_guard_passed']:return 96
    return 0


def main():
    p=argparse.ArgumentParser();p.add_argument('--receipt',required=True);p.add_argument('--limit-kib',type=int,default=6*1024**2)
    p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args()
    command=a.command[1:] if a.command[:1]==['--'] else a.command
    if not command:raise SystemExit('no worker command')
    raise SystemExit(run(command,a.receipt,a.limit_kib))


if __name__=='__main__':main()
