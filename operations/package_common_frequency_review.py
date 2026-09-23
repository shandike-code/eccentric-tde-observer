"""Hash-manifested small-artifact archive for a terminal common-frequency audit."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile
ROOT=Path(__file__).resolve().parents[1]


def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--kind',choices=('pilot','pair'),required=True);p.add_argument('--job',type=int,required=True);a=p.parse_args()
    run=ROOT/f'outputs/hpc/common-frequency-{a.kind}-20260923'
    if json.loads((run/'status.json').read_text())['status']!='common_source_consistent':raise RuntimeError('audit is not successfully terminal')
    scheduler=ROOT/f'outputs/review-20260923/scheduler-{a.job}'
    terminal=json.loads((scheduler/'scheduler-terminal.json').read_text())
    if terminal['state']!='COMPLETED' or terminal['job_id']!=a.job:raise RuntimeError('scheduler did not complete')
    expected_name='tde-common-'+('pilot' if a.kind=='pilot' else 'pair')
    if ('JobName='+expected_name+' ') not in terminal['scontrol']:raise RuntimeError('job does not name the requested audit kind')
    files={}
    for f in sorted(run.rglob('*')):
        if f.is_symlink():raise RuntimeError('symlink not permitted in archive')
        if f.is_file() and f.suffix in ('.json','.npz'):files[str(f.relative_to(run))]=f
    for name in ('launch.json','scheduler-terminal.json'):files['scheduler/'+name]=scheduler/name
    manifest={'files':[{'path':n,'size_bytes':f.stat().st_size,'sha256':digest(f),'source_path':str(f.relative_to(ROOT))} for n,f in files.items()],'radiation_dat_included':False}
    out=ROOT/f'outputs/review-20260923/common-frequency-{a.kind}-{a.job}.tar.gz'
    if out.exists():raise FileExistsError(out)
    with tarfile.open(out,'w:gz') as t:
        for n,f in files.items():t.add(f,arcname=n,recursive=False)
        data=(json.dumps(manifest,indent=2)+'\n').encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    receipt={'path':str(out.relative_to(ROOT)),'size_bytes':out.stat().st_size,'sha256':digest(out),'files':len(files)}
    out.with_suffix('.receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))


if __name__=='__main__':main()
