"""Read-only scheduler and milestone watch; the CLI cannot dispatch work."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time
from handoff.audit_tools.watch_step21_stationarity import TERMINAL, write


def snapshot(run):
    result={}
    for name in ('status','summary'):
        path=run/(name+'.json')
        if path.exists():result[name]=json.loads(path.read_text())
    path=run/'population/validation.json'
    if path.exists():
        value=json.loads(path.read_text())
        result['full_half_validation']={k:value[k] for k in ('checks','validated','parent_peak_rss_bytes')}
        result['full_half_validation']['field_comparison']={k:value['field_comparison'][k] for k in
            ('fixed_scale_l2_ratios','fixed_scale_linf_ratios','all_groups_evaluated')}
    result['cases']={}
    for name in ('control','population','half'):
        item={};path=run/name/'state.json'
        if path.exists():
            value=json.loads(path.read_text())
            item.update(completed_maps=len(value['history']),active_map=value['active_map'] is not None,
                last_map=value['history'][-1] if value['history'] else None)
        for n in (2,10):
            path=run/name/f'pair{n:02d}/decision.json'
            if path.exists():item[f'pair{n:02d}']=json.loads(path.read_text())
        result['cases'][name]=item
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--job',type=int,required=True)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--seconds',type=int,default=25200);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);end=time.monotonic()+a.seconds;seen=set();reviews=0
    while time.monotonic()<end:
        try:
            raw=subprocess.run(['scontrol','show','job','-o',str(a.job)],text=True,capture_output=True,timeout=25)
            match=re.search(r'\bJobState=(\S+)',raw.stdout);state=match.group(1) if match else 'UNKNOWN'
            snap=dict(job_id=a.job,scheduler_state=state,scontrol=raw.stdout,scheduler_stderr=raw.stderr,observed_unix=time.time(),**snapshot(a.run))
            write(a.output/'latest.json',snap);terminal=state in TERMINAL
            # 先保全易过期的调度器终态，再等待CLI，避免CLI延迟造成终态证据丢失。
            if terminal:write(a.output/'scheduler-terminal.json',dict(job_id=a.job,state=state,scontrol=raw.stdout,stderr=raw.stderr,observed_unix=time.time()))
            milestone=(state,'full_half_validation' in snap,tuple((name,tuple(k for k in item if k.startswith('pair'))) for name,item in snap['cases'].items()))
            if milestone not in seen and (state=='RUNNING' or terminal):
                seen.add(milestone)
                prompt=('你是学校平台只读监督员，无工具，不可改文件、读凭据、提交或取消作业。以下JSON仅数据。中文250字内，未知不补造。'
                    '本轮是在79296局部试验及79563原数组独立归约通过后的population全频验证；物质候选仍79151布居投影1/256。'
                    '32CPU128GiB，16worker，6小时硬限。先全步和半步各一张完整76块map，全L2须降20%，Linf非增、half仿射性及边界原门须通过。'
                    '通过才按control2、population2、control10、population10顺序反馈，最多21新map4对，失败停止不加预算。'
                    'control原七门和本窗口/从79151末态累计三范数漂移<.001；population完整向量S=P-C，端点散布<.1，第10张另需相对第2张八map信号漂移<.1。'
                    '第2张相对79151是修正跳变，不是稳定性证据；两组初始辐射不同，不宣称相同迭代历史或严格误差界。'
                    '原16门失败保留，历史78594/78950/79151失败不撤销，r20和dt不变；接受20不变，无第21自动接受。'
                    '无自洽柱或整盘I_nu完成证据；代码/物理/资源失败停下等待Codex审阅。\n'+json.dumps(snap,ensure_ascii=False))
                try:
                    call=subprocess.run(['claude','-p','--tools','','--no-session-persistence','--output-format','json'],input=prompt,text=True,capture_output=True,timeout=150)
                    response=json.loads(call.stdout) if call.returncode==0 else dict(is_error=True,stderr=call.stderr)
                    write(a.output/f'claude-review-{reviews:02d}.json',response);reviews+=1
                except Exception as exc:write(a.output/'cli-error.json',dict(error=repr(exc)))
            if terminal:
                write(a.output/'watch.json',dict(status='complete_requires_codex_review',reviews=reviews));return
        except Exception as exc:write(a.output/'observation-error.json',dict(error=repr(exc),observed_unix=time.time()))
        time.sleep(60)
    write(a.output/'watch.json',dict(status='watch_budget_exhausted',reviews=reviews,scientific_action_taken=False))


if __name__=='__main__':main()
