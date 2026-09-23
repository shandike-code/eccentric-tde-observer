"""Archive only small completed source-diagnostic artifacts with a hash manifest."""
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
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--include-tail',action='store_true');a=p.parse_args()
    out=ROOT/a.output;out.relative_to(ROOT/'outputs/review-20260923')
    if out.exists():raise FileExistsError(out)
    names=['formal-source-split-pilot-20260923','formal-source-split-all-20260923']
    if a.include_tail:names.append('source-split-tail-evidence-20260923')
    files={}
    for name in names:
        folder=ROOT/'outputs/hpc'/name;state=json.loads((folder/'status.json').read_text())
        if state['status'] not in ('complete','failed','evidence_complete'):raise RuntimeError('source diagnostic not terminal')
        for path in sorted(folder.iterdir()):
            if path.is_file() and not path.is_symlink() and path.suffix in ('.json','.npz'):
                files[name+'/'+path.name]=path
    for job in (75845,75847):
        folder=ROOT/f'outputs/review-20260923/scheduler-{job}'
        for name in ('launch.json','scheduler-terminal.json'):
            files[f'scheduler-{job}/{name}']=folder/name
    manifest={'files':[{'path':name,'size_bytes':path.stat().st_size,'sha256':digest(path),'source_path':str(path.relative_to(ROOT))} for name,path in files.items()],'radiation_states_included':False}
    out.parent.mkdir(parents=True,exist_ok=True)
    with tarfile.open(out,'w:gz') as t:
        for name,path in files.items():t.add(path,arcname=name,recursive=False)
        data=(json.dumps(manifest,indent=2)+'\n').encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    receipt={'path':str(out.relative_to(ROOT)),'size_bytes':out.stat().st_size,'sha256':digest(out),'files':len(files)}
    out.with_suffix('.receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))

if __name__=='__main__':main()
