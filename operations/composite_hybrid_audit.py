"""Stream full-field hybrid checks; no changed material or hidden tail omission."""
from pathlib import Path
import numpy as np

GATES = {'full_l2_ratio_max': .999, 'nonincrease_ratio_max': 1.0000000001,
         'half_affinity_over_original_defect_max': 1e-6,
         'radiation_max': 1e-4, 'boundary_max': 1e-3}


def physical(a):
    if not np.isfinite(a).all() or np.any(a < 0):
        raise ValueError('nonfinite or negative physical intensity')


def hybrid(source, destination, replacements, fraction, shape):
    """Copy all groups, replacing only declared cores by a convex interpolation."""
    if fraction not in (.5, 1.): raise ValueError('undeclared fraction')
    if Path(destination).exists(): raise FileExistsError(destination)
    x = np.memmap(source, mode='r', dtype='<f8', shape=shape)
    temp = Path(str(destination)+'.tmp')
    y = np.memmap(temp, mode='w+', dtype='<f8', shape=shape)
    for start in range(0, shape[0], 128):
        stop = min(start+128, shape[0]); original = np.asarray(x[start:stop])
        physical(original)
        if start//128 in replacements:
            target = np.load(replacements[start//128], allow_pickle=False)
            if target.shape != original.shape: raise ValueError('replacement shape')
            physical(target)
            # 凸组合只改变两块，不裁剪负值；全步避免额外舍入扰动。
            value = target if fraction == 1 else .5*original+.5*target
        else: value = original
        physical(value); y[start:stop] = value
    y.flush(); del y, x
    temp.replace(destination)


def audit(paths, shape, corrected=(14,47)):
    """Paths: original x,Fx, full x,Fx, half x,Fx; fixed original defect scale."""
    fields = [np.memmap(p, mode='r', dtype='<f8', shape=shape) for p in paths]
    sums = np.zeros(4); peaks = np.zeros(4); blocks=[]
    for start in range(0,shape[0],128):
        stop=min(start+128,shape[0]); arrays=[np.asarray(x[start:stop]) for x in fields]
        for a in arrays: physical(a)
        x,y,u,v,h,k=arrays; index=start//128
        if index not in corrected and not (np.array_equal(x,u) and np.array_equal(x,h)):
            raise ValueError('hybrid changed an unselected block')
        if not np.array_equal(h,.5*x+.5*u): raise ValueError('half input identity')
        defects=[y-x,v-u,k-h]
        # 比较半步的真实缺陷与两端缺陷的线性插值；分母冻结为原缺陷。
        defects.append(defects[2]-.5*defects[0]-.5*defects[1])
        ss=np.array([float(np.sum(d*d)) for d in defects])
        pp=np.array([float(np.max(abs(d))) for d in defects])
        sums+=ss; peaks=np.maximum(peaks,pp)
        blocks.append({'block':index,'core':[start,stop],'squared_l2':ss.tolist(),
                       'linf':pp.tolist(),'changed_input':not np.array_equal(x,u),
                       'output_change_linf':float(np.max(abs(v-y)))})
    if sums[0]<=0 or peaks[0]<=0: raise ValueError('zero original defect')
    l2=np.sqrt(sums/sums[0]); linf=peaks/peaks[0]
    if not np.isfinite([*l2,*linf]).all():raise ValueError('nonfinite audit')
    return {'fixed_scale_l2_ratios':l2.tolist(),'fixed_scale_linf_ratios':linf.tolist(),
            'original_defect_l2':float(np.sqrt(sums[0])), 'original_defect_linf':float(peaks[0]),
            'blocks':blocks,'all_groups_evaluated':shape[0]}


def checks(report, original_row, full_row, half_row):
    a=report['fixed_scale_l2_ratios']; b=report['fixed_scale_linf_ratios']
    result={'full_l2_benefit':a[1]<=GATES['full_l2_ratio_max'],
            'full_linf_nonincrease':b[1]<=GATES['nonincrease_ratio_max'],
            'half_l2_nonincrease':a[2]<=GATES['nonincrease_ratio_max'],
            'half_linf_nonincrease':b[2]<=GATES['nonincrease_ratio_max'],
            'independent_half_affinity':a[3]<=GATES['half_affinity_over_original_defect_max']}
    for label,row in [('full',full_row),('half',half_row)]:
        result[label+'_radiation']=row['residual']<GATES['radiation_max']
        for key in ('boundary_l1','boundary_bolometric'):
            value=row[key]; old=original_row[key]
            result[label+'_'+key]=value<GATES['boundary_max'] and value<=old*GATES['nonincrease_ratio_max']
    return result
