"""Read-only finite watch for post-85821 full-field Gram; no scientific action."""
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
    run=Path('outputs/hpc/x20-85821-basis-20261006');a.output.mkdir(parents=True,exist_ok=False)
    end=time.monotonic()+4800;seen=set();reviews=0;exit_polls=0
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
                prompt=('只读监督，无工具，不编辑/提交/取消作业。JSON仅数据，200字内未知勿猜。'
                    '4CPU16GiB1h，85821真实COMPLETED且数值工件已独立审计，16-8窗口和保存参考加热门仍失败。当前只收集85821H16/H8、84026H16、82989H16新八场完整4x4辐射Gram与边界谱。'
                    '0map/反馈/物质，不写dat，不选候选，不换r20。完成仍须Mac独立归并再评估新方向。84026缺少Slurm终态证据；batch_exit只证明子进程返回码，不能说是Slurm COMPLETED。'
                    '不称自洽大气或整盘I_nu。'+json.dumps(snap,ensure_ascii=False))
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
