"""Archive a terminal bridge and its independent process/scheduler evidence."""
import argparse
import io
import json
import tarfile
from pathlib import Path
from operations.package_common_frequency_review import digest,ROOT


def main():
    p=argparse.ArgumentParser();p.add_argument('--job',type=int,required=True);a=p.parse_args()
    scheduler=ROOT/f'outputs/review-20260923/scheduler-{a.job}'
    launch=json.loads((scheduler/'launch.json').read_text());run=ROOT/launch['run']
    terminal=json.loads((scheduler/'scheduler-terminal.json').read_text())
    if terminal['state']!='COMPLETED' or terminal['job_id']!=a.job:raise RuntimeError('job not complete')
    if json.loads((run/'status.json').read_text())['status']!='response_evaluated_requires_review':raise RuntimeError('bridge not complete')
    process=run.with_suffix('.process.json');receipt=json.loads(process.read_text())
    if receipt['returncode']!=0 or not receipt['memory_guard_passed']:raise RuntimeError('independent process failed')
    files={}
    for f in sorted(run.rglob('*')):
        if f.is_symlink():raise RuntimeError('no symlinks')
        if f.is_file() and f.suffix in ('.json','.npz','.npy','.png'):files[str(f.relative_to(run))]=f
    files['process.json']=process
    for name in ('launch.json','scheduler-terminal.json'):files['scheduler/'+name]=scheduler/name
    for suffix in ('out','err'):files['scheduler/job.'+suffix]=ROOT/f'outputs/hpc/logs/tde-common-feedback-{a.job}.{suffix}'
    # 首次实现缺陷的失败证据随成功包保留，不抹去失败提交。
    for name,source in {'status.json':'outputs/hpc/common-feedback-bridge-20260923/status.json',
                        'process.json':'outputs/hpc/common-feedback-bridge-20260923.process.json',
                        'scheduler.json':'outputs/review-20260923/scheduler-75941/scheduler-terminal.json',
                        'stderr.txt':'outputs/hpc/logs/tde-common-feedback-75941.err'}.items():files['first-attempt/'+name]=ROOT/source
    manifest={'files':[{'path':n,'size_bytes':f.stat().st_size,'sha256':digest(f),'source_path':str(f.relative_to(ROOT))} for n,f in files.items()],'radiation_dat_included':False}
    out=ROOT/f'outputs/review-20260923/common-feedback-bridge-{a.job}.tar.gz'
    if out.exists():raise FileExistsError(out)
    with tarfile.open(out,'w:gz') as t:
        for n,f in files.items():t.add(f,arcname=n,recursive=False)
        data=(json.dumps(manifest,indent=2)+'\n').encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    record={'path':str(out.relative_to(ROOT)),'size_bytes':out.stat().st_size,'sha256':digest(out),'files':len(files)}
    out.with_suffix('.receipt.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))


if __name__=='__main__':main()
