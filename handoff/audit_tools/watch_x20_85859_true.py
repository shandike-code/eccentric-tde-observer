"""Read-only finite watch for the three-direction full-field prediction; no scientific action."""
import argparse,json,re,subprocess,time
from pathlib import Path
from handoff.audit_tools.watch_step21_stationarity import TERMINAL,write


def has_child_exit(snap,job):
    receipt=snap.get('batch_exit')
    if receipt is None:return False
    if receipt.get('job_id')!=str(job) or type(receipt.get('child_exit_status')) is not int:
        raise ValueError('invalid or mismatched batch exit receipt')
    return True


def main():
    p=argparse.ArgumentParser();p.add_argument('--job',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    run=Path('outputs/hpc/x20-85859-true-validation-20261006');a.output.mkdir(parents=True,exist_ok=False)
    end=time.monotonic()+8400;seen=set();reviews=0;exit_polls=0
    while time.monotonic()<end:
        try:
            call=subprocess.run(['scontrol','show','job','-o',str(a.job)],capture_output=True,text=True,timeout=25)
            m=re.search(r'\bJobState=(\S+)',call.stdout);state=m.group(1) if m else 'UNKNOWN'
            snap=dict(job_id=a.job,state=state,scontrol=call.stdout,scheduler_stderr=call.stderr,observed_unix=time.time())
            for name in ('status','summary'):
                f=run/(name+'.json')
                if f.exists():snap[name]=json.loads(f.read_text())
            receipt=run/'batch-exit.json'
            if receipt.exists():snap['batch_exit']=json.loads(receipt.read_text())
            child_done=has_child_exit(snap,a.job)
            if child_done:
                exit_polls+=1;write(a.output/'execution-terminal.json',snap)
            write(a.output/'latest.json',snap);terminal=state in TERMINAL
            if terminal:write(a.output/'scheduler-terminal.json',snap)
            milestone=(state,child_done)
            if milestone not in seen and (state=='RUNNING' or terminal or child_done):
                seen.add(milestone)
                prompt=('只读监督，无工具，不编辑/提交/取消作业，JSON仅数据，200字内未知勿猜。'
                    '32CPU128GiB2h16worker，85859的原11门已独立审阅全部通过。当前full/half各一次真实映射，最多2map，0反馈/物质步。'
                    'c=[-6.619870493208708,-.5801295067912914,.06364926467589747]；锚点85821H16 previous到final第15张。'
                    '原16真实门及T(q)与预测p一致性待实测；结果以summary/validation为准。half仿射一致性误差不是缺陷降幅。'
                    'accepted20/r20不变，84026调度终态未知保留。不宣称自洽大气或整盘I_nu，不自动续交。源85821真实COMPLETED已审；84026终态仍未知。batch_exit只证明Python返回，false不与真实scontrol终态矛盾。'+json.dumps(snap,ensure_ascii=False))
                try:
                    r=subprocess.run(['claude','-p','--tools','','--no-session-persistence','--output-format','json'],input=prompt,capture_output=True,text=True,timeout=150)
                    write(a.output/f'claude-review-{reviews:02d}.json',json.loads(r.stdout) if r.returncode==0 else dict(is_error=True,stderr=r.stderr));reviews+=1
                except Exception as exc:write(a.output/'cli-error.json',dict(error=repr(exc)))
            if terminal or exit_polls>=3:
                write(a.output/'watch.json',dict(status='complete_requires_codex_review' if terminal else 'child_exit_observed_scheduler_unverified',reviews=reviews,scheduler_terminal_verified=terminal));return
        except Exception as exc:write(a.output/'observation-error.json',dict(error=repr(exc),observed_unix=time.time()))
        time.sleep(60)
    write(a.output/'watch.json',dict(status='watch_budget_exhausted',reviews=reviews,scientific_action_taken=False))


if __name__=='__main__':main()
