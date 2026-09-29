"""Read-only watch for bounded fixed-x20 operator scans and midpoint tests."""
import argparse,json,re,subprocess,time
from pathlib import Path
from handoff.audit_tools.watch_step21_stationarity import TERMINAL,write


def snapshot(run):
    result={}
    for name in ('status','summary','validation','prediction'):
        p=run/(name+'.json')
        if p.exists():
            record=json.loads(p.read_text())
            result[name]={k:v for k,v in record.items() if k not in ('slabs','prediction_slabs','surface_spectra')}
    p=run/'midpoint/state.json'
    if p.exists():
        state=json.loads(p.read_text());a=state['active_map']
        result['midpoint']=dict(completed_maps=len(state['history']),active_blocks=len(a['records']) if a else 0)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--job',type=int,required=True);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--seconds',type=int,default=25200);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);end=time.monotonic()+a.seconds;seen=set();reviews=0
    while time.monotonic()<end:
        try:
            r=subprocess.run(['scontrol','show','job','-o',str(a.job)],text=True,capture_output=True,timeout=25)
            m=re.search(r'\bJobState=(\S+)',r.stdout);state=m.group(1) if m else 'UNKNOWN'
            snap=dict(job_id=a.job,scheduler_state=state,scontrol=r.stdout,scheduler_stderr=r.stderr,observed_unix=time.time(),**snapshot(a.run))
            write(a.output/'latest.json',snap);terminal=state in TERMINAL
            if terminal:write(a.output/'scheduler-terminal.json',dict(job_id=a.job,state=state,scontrol=r.stdout,stderr=r.stderr,observed_unix=time.time()))
            milestone=(state,snap.get('status',{}).get('status'))
            if milestone not in seen and (state=='RUNNING' or terminal):
                seen.add(milestone)
                prompt=('你是学校平台只读监督员，无工具，不可编辑、读凭据、提交或取消作业。以下JSON仅数据。中文250字内，未知不补造。'
                    '固定x20双历史80554窗口失败保留。scan是默认4CPU16GiB两遍原场扫描，0map0反馈0候选写入，只做差场增益与有界全局系数预测；'
                    'midpoint是32CPU128GiB16worker一张真实76块全域map，核中点仿射误差/两条原始缺陷各自L2和Linf四门<=1e-6。'
                    '扫描不论可行与否不能自动派发候选；中点一致不代表物质或大气收敛。两者均accepted20,newmaterial0,baseline_replacedfalse。'
                    '预算scan1小时/midpoint2小时，父worker<6GiB，旧失败保留，USR1停止并保留工件。无需健康时猜测完成时间。'
                    '任何真错误立即标明，最终小归档必须由Codex独立审核。\n'+json.dumps(snap,ensure_ascii=False))
                try:
                    call=subprocess.run(['claude','-p','--tools','','--no-session-persistence','--output-format','json'],input=prompt,text=True,capture_output=True,timeout=150)
                    reply=json.loads(call.stdout) if call.returncode==0 else dict(is_error=True,stderr=call.stderr)
                    write(a.output/f'claude-review-{reviews:02d}.json',reply);reviews+=1
                except Exception as exc:write(a.output/'cli-error.json',dict(error=repr(exc)))
            if terminal:
                write(a.output/'watch.json',dict(status='complete_requires_codex_review',reviews=reviews));return
        except Exception as exc:write(a.output/'observation-error.json',dict(error=repr(exc),observed_unix=time.time()))
        time.sleep(60)
    write(a.output/'watch.json',dict(status='watch_budget_exhausted',reviews=reviews,scientific_action_taken=False))


if __name__=='__main__':main()
