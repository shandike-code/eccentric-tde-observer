"""Mac audit of immutable repeated finite-band measurements and receipts."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read(p):return json.loads(p.read_text())


def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def review(archive,receipt,received,output):
    claim=read(receipt)
    assert digest(archive)==claim['sha256'] and archive.stat().st_size==claim['size_bytes']
    received.mkdir(exist_ok=False)
    with tarfile.open(archive) as t:
        assert all(m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts for m in t.getmembers())
        t.extractall(received,filter='data')
    manifest=read(received/'MANIFEST.json')
    for c in manifest['files']:
        p=received/c['path'];assert digest(p)==c['sha256'] and p.stat().st_size==c['size_bytes']
    assert read(received/'status.json')['completed_endpoints']==3
    fig,axs=plt.subplots(1,3,figsize=(13,4),layout='constrained');results=[];receipts=[]
    names=('backtrack-previous','amplitude-previous','amplitude-final')
    for ax,name in zip(axs,names):
        folder=received/name;s=read(folder/'summary.json');a=dict(np.load(folder/'comparison.npz',allow_pickle=False))
        assert digest(folder/'comparison.npz')==s['arrays']['sha256']
        assert all(np.isfinite(v).all() for v in a.values()) and (a['width_cm']>0).all()
        assert np.array_equal(a['observed']-a['boundary'],a['residual'])
        assert np.array_equal(abs(a['residual']),a['residual_depth_l1'])
        assert np.array_equal(abs(a['observed']),a['observed_depth_l1'])
        metrics={k:float(np.sum(a['width_cm'].astype(np.longdouble)*v.astype(np.longdouble))) for k,v in a.items() if k!='width_cm'}
        for k,v in metrics.items():assert np.isclose(v,s['metrics_erg_s_cm2'][k],rtol=2e-14,atol=1e-6)
        for block in (0,75):
            r=read(folder/f'block{block:02d}.json');p=read(folder/f'block{block:02d}.process.json')
            assert r['original_source_bitwise_replayed'] and r['native_peak_mib']<6144
            assert p['returncode']==0 and p['memory_guard_passed']
            assert digest(folder/f'block{block:02d}.npz')==r['arrays']['sha256']
            receipts.append({'case':name,'block':block,'native_mib':r['native_peak_mib'],'proc_kib':p['native_observed_peak_kib']})
        for k in ('observed','boundary','residual'):
            ax.plot(np.cumsum(a['width_cm']*a[k]),label=k,ls='--' if k=='boundary' else '-')
        ax.set(title=name,xlabel='Radiation depth index',ylabel='Cumulative column source (erg s-1 cm-2)',yscale='symlog');ax.legend()
        results.append({'case':name,'source':s['source'],'endpoint':s['endpoint'],'metrics_erg_s_cm2':metrics,'boundary_components':s['boundary_components']})
    result={'archive':claim,'verified_files':len(manifest['files']),'results':results,'resource_receipts':receipts,'scientific_gates_changed':False,'material_step_accepted':False}
    output.with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    fig.savefig(output.with_suffix('.png'),dpi=160);plt.close(fig)
    print(json.dumps(result,indent=2))


def main():
    p=argparse.ArgumentParser()
    for name in ('archive','receipt','received','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();review(a.archive,a.receipt,a.received,a.output)


if __name__=='__main__':main()
