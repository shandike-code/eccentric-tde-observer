"""Independent stdlib fixed tables and scalar trust decisions; no NumPy/kernel import."""
import json,math,sys

def codec_ledger():
    n,p,q=11,5,6
    rows=[]
    def add(label,count,width=8):rows.append(['codec:'+label,count*width])
    add('vector:finite',4*n,1)
    for label,count,width in [('thermal',n,8),('ionized-empty',n,8),('positive',n,1),('positive-select',p,8),('positive-negate',p,8),('positive-exp',p,8),('positive-denominator',p,8),('positive-fraction',p,8),('negative-select-mask',n,1),('negative-select',q,8),('negative-exp',q,8),('negative-denominator',q,8),('negative-fraction',q,8),('negative-write-mask',n,1),('neutral',n,8),('hydrogen',2*n,8),('helium-zero',n,8),('helium-score',3*n,8),('helium-shift',n,8),('helium-shifted',3*n,8),('helium-weight',3*n,8),('helium-sum',n,8),('helium',3*n,8)]:add(label,count,width)
    for label,count in [('thermal:finite',n),('thermal:nonpositive',n),('hydrogen:finite',2*n),('helium:finite',3*n),('hydrogen:nonpositive',2*n),('helium:nonpositive',3*n)]:add(label,count,1)
    def electron(prefix):
        for suffix in ('hydrogen-electron','helium-double','helium-charge','helium-electron','electron'):add(prefix+':'+suffix,n)
    electron('coefficient')
    for label in ('coefficient:particles','coefficient:value','temperature'):add(label,n)
    for label,count in [('energy-hydrogen:finite',2*n),('energy-helium:finite',3*n),('energy-hydrogen:negative',2*n),('energy-helium:negative',3*n)]:add(label,count,1)
    for species in ('hydrogen','helium'):
        for label in ('sum','sum-minus-one','sum-absolute'):add('energy-'+species+':'+label,n)
        add('energy-'+species+':sum-outside',n,1)
    add('energy-temperature:finite',n,1);add('energy-temperature:nonpositive',n,1)
    electron('energy')
    for label in ('gas-scaled-temperature','gas-particles','gas','ionization-h-number','ionization-h','ionization-he1','ionization-he2','ionization-he-sum','ionization-he','ionization','total'):add(label,n)
    add('total:finite',n,1);add('total:nonpositive',n,1);add('energy-copy',n)
    add('temperature:finite',n,1);add('temperature:nonpositive',n,1)
    for label,count in [('temperature-copy',n),('hydrogen-copy',2*n),('helium-copy',3*n),('decoded-energy-copy',n)]:add(label,count)
    return rows


def trust_ledger():
    rows=[]
    for label,count in [('temperature-delta',11),('temperature-absolute',11),('temperature-relative',11),
                        ('energy-delta',11),('energy-absolute',11),('energy-relative',11),
                        ('hydrogen-delta',22),('hydrogen-absolute',22),('helium-delta',33),('helium-absolute',33)]:
        rows.append(['trust:'+label,count*8])
    return codec_ledger()*2+rows


def control_ledger():
    rows=[]
    def add(label,size):rows.append(['identity:'+label,size])
    add('residual-finite',44);add('direction-copy',352)
    for label in ('base-encoded','base-residual','base-direction'):add(label,44)
    add('scaled-direction',352);add('encoded-sum',352)
    for key in ('base_encoded_state','base_residual','finite_direction','encoded_state'):add('trial-'+key,44)
    add('physical-density_g_cm3',11);add('physical-phase_index',1);add('physical-step_duration_s',1)
    add('old-density',11)
    rows+=codec_ledger()
    for key,size in [('temperature_k',11),('hydrogen_fraction',22),('helium_fraction',33),('specific_material_energy_erg_g',11)]:add('decoded-'+key,size)
    return rows+trust_ledger()


def scalar_decision(increment):
    # 独立标量热能/电子数/基态电离能；本例只改变 ln(gas thermal energy)。
    hp=.70/1.67262192369e-24;hep=.28/(4.*1.67262192369e-24)
    k=1.380649e-16;ev=1.602176634e-12
    tchanges=[];echanges=[]
    for i in range(11):
        x=(i%4-2)/8.
        h=1./(1.+math.exp(-x)) if x>=0 else math.exp(x)/(1.+math.exp(x))
        s=[0.,i/128.,-i/256.];w=[math.exp(v-max(s)) for v in s];he=[v/sum(w) for v in w]
        electron=hp*h+hep*(he[1]+2.*he[2]);coef=1.5*k*(hp+hep+electron)
        t0=math.exp(28.+i/64.)/coef;t1=math.exp(28.+i/64.+increment)/coef
        ion=hp*h*(13.59843449*ev)+hep*(he[1]*(24.587389*ev)+he[2]*((24.587389*ev)+(54.417765*ev)))
        e0=(1.5*k*t0)*(hp+hep+electron)+ion;e1=(1.5*k*t1)*(hp+hep+electron)+ion
        tchanges.append(abs(t1-t0)/t0);echanges.append(abs(e1-e0)/e0)
    return max(tchanges)<=.5 and max(echanges)<=.25,dict(temperature=max(tchanges),energy=max(echanges),population=0.)


def review(data):
    if data['schema']!='86304-trust-control-synthetic-v1' or data['exact_control_component'] is not True:raise ValueError('schema/scope')
    for key in ('configuration_integrated','all_scientific_temporaries_metered','whole_lifecycle_guard_verified','production_authorized'):
        if data[key] is not False:raise ValueError('qualification')
    if [c['mode'] for c in data['cases']]!=['control','small','large']:raise ValueError('cases')
    metrics={}
    for case,inc in zip(data['cases'],(0.,.03125,1.)):
        control=case['mode']=='control';rows=control_ledger() if control else trust_ledger()
        if any(type(r) is not list or len(r)!=2 or type(r[0]) is not str or type(r[1]) is not int for r in case['entries']):raise ValueError('ledger types')
        if case['entries']!=rows or type(case['reserved_bytes']) is not int or case['reserved_bytes']!=sum(r[1] for r in rows):raise ValueError('ledger')
        checks=286 if control else 181
        if type(case['checkpoints']) is not int or case['checkpoints']!=checks:raise ValueError('checks')
        elapsed=case['elapsed_s']
        if type(elapsed) not in (int,float) or not math.isfinite(elapsed) or elapsed<0:raise ValueError('elapsed')
        decision,values=scalar_decision(inc)
        if case['accepted'] is not decision:raise ValueError('decision')
        metrics[case['mode']]=dict(scalar_metrics=values,reserved_bytes=sum(r[1] for r in rows),entries=len(rows),checkpoints=checks)
    return metrics

if __name__=='__main__':print(json.dumps(review(json.load(open(sys.argv[1]))),sort_keys=True))
