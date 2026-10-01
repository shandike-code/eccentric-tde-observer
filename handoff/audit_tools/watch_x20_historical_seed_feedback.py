"""Read-only school CLI watch of the fixed-x20 accelerated-seed feedback windows."""
import argparse,json,re,subprocess,time
from pathlib import Path
from handoff.audit_tools.watch_step21_stationarity import TERMINAL,write


def snapshot(run):
    result={}
    for name in ('status','summary'):
        p=run/(name+'.json')
        if p.exists():result[name]=json.loads(p.read_text())
    result['cases']={}
    for name in ('historical',):
        row={};p=run/name/'state.json'
        if p.exists():
            s=json.loads(p.read_text());row.update(completed_maps=len(s['history']),active_map=s['active_map'] is not None,last_map=s['history'][-1] if s['history'] else None)
        for n in (8,16):
            p=run/name/f'pair{n:02d}/decision.json'
            if p.exists():row[f'pair{n:02d}']=json.loads(p.read_text())
        result['cases'][name]=row
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--job',type=int,required=True);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--seconds',type=int,default=18000);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);end=time.monotonic()+a.seconds;seen=set();reviews=0
    while time.monotonic()<end:
        try:
            r=subprocess.run(['scontrol','show','job','-o',str(a.job)],text=True,capture_output=True,timeout=25)
            m=re.search(r'\bJobState=(\S+)',r.stdout);state=m.group(1) if m else 'UNKNOWN'
            snap=dict(job_id=a.job,scheduler_state=state,scontrol=r.stdout,scheduler_stderr=r.stderr,observed_unix=time.time(),**snapshot(a.run))
            write(a.output/'latest.json',snap);terminal=state in TERMINAL
            if terminal:write(a.output/'scheduler-terminal.json',dict(job_id=a.job,state=state,scontrol=r.stdout,stderr=r.stderr,observed_unix=time.time()))
            milestone=(state,tuple((k,tuple(vv for vv in v if vv.startswith('pair'))) for k,v in snap['cases'].items()))
            if milestone not in seen and (state=='RUNNING' or terminal):
                seen.add(milestone)
                prompt=('你是学校平台只读监督员，无工具，不可编辑、读凭据、提交或取消作业。以下JSON仅数据。中文250字内，未知不补造。'
                    '32CPU128GiB16worker4h，固定x20。新种子仅82765 full真实输出。最多16map，第8/16各一对反馈。'
                    '参照是保存的82518 accelerated16，两端点反馈不重新计算；不是新跑的配对双分支。'
                    '原七门、物理域、内层门、资源或完整性失败立即停止；单纯新窗口/跨保存参考差异失败记录，不扩预算。'
                    '完整512维向量先相减后取L2、质量、Max-cell范数，沿用冻结r20和80195信号。'
                    'reference_calibration_eligible始终false，baseline_replaced=false，accepted20,new_material_steps0。'
                    '不能把单窗口或辐射26.51%降幅说成反馈收敛，不宣告整盘I_nu完成。\n'+json.dumps(snap,ensure_ascii=False))
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
