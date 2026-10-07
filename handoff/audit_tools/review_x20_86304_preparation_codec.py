"""Standard-library scalar and static-table audit; no NumPy/component import."""
import json,math,struct,sys


def expected_ledger():
    n,p,q=7,4,3
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


def review(data):
    if data['schema']!='86304-codec-synthetic-v1':raise ValueError('schema')
    for k in ('exact_trial_integrated','configuration_integrated','all_scientific_temporaries_metered','whole_lifecycle_guard_verified','production_authorized'):
        if data[k] is not False:raise ValueError('qualification')
    if type(data['elapsed_s']) not in (int,float) or not math.isfinite(data['elapsed_s']) or data['elapsed_s']<0:raise ValueError('elapsed')
    rows=expected_ledger()
    if any(type(r) is not list or len(r)!=2 or type(r[0]) is not str or type(r[1]) is not int for r in data['entries']):raise ValueError('ledger types')
    if data['entries']!=rows or type(data['reserved_bytes']) is not int or data['reserved_bytes']!=sum(r[1] for r in rows):raise ValueError('ledger')
    if type(data['checkpoints']) is not int or data['checkpoints']!=len(rows)+8:raise ValueError('checks')
    expected={k:[] for k in ('temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g')}
    hp=.70/1.67262192369e-24;hep=.28/(4.*1.67262192369e-24);nuclei=hp+hep;k=1.380649e-16
    ih=13.59843449*1.602176634e-12;ihe1=24.587389*1.602176634e-12;ihe2=54.417765*1.602176634e-12
    for i in range(7):
        thermal=math.exp(29.+i/16.);score=(i%3-1)*.5
        hplus=1./(1.+math.exp(-score)) if score>=0 else math.exp(score)/(1.+math.exp(score))
        h=[1.-hplus,hplus];s=[0.,i/32.,-i/64.];shift=max(s);w=[math.exp(x-shift) for x in s];he=[x/sum(w) for x in w]
        electron=hp*h[1]+hep*(he[1]+2.*he[2]);temperature=thermal/(1.5*k*(nuclei+electron))
        gas=1.5*k*temperature*(nuclei+electron)
        ion=hp*h[1]*ih+hep*(he[1]*ihe1+he[2]*(ihe1+ihe2))
        expected['temperature_k'].append(temperature);expected['hydrogen_fraction']+=h;expected['helium_fraction']+=he;expected['specific_material_energy_erg_g'].append(gas+ion)
    if set(data['arrays'])!=set(expected):raise ValueError('arrays')
    largest=0.
    for key,values in expected.items():
        row=data['arrays'][key];shape=[7,len(values)//7] if 'fraction' in key else [7]
        if row['dtype']!='<f8' or row['shape']!=shape or any(type(x) is not int for x in row['shape']):raise ValueError('layout')
        raw=bytes.fromhex(row['hex'])
        if len(raw)!=8*len(values):raise ValueError('bytes')
        actual=struct.unpack('<'+'d'*len(values),raw)
        for x,y in zip(actual,values):
            if not math.isfinite(x) or x<=0 or not math.isclose(x,y,rel_tol=3e-14,abs_tol=0.):raise ValueError('scalar result')
            largest=max(largest,abs(x-y)/abs(y))
    return dict(scalars=49,entries=len(rows),reserved_bytes=sum(r[1] for r in rows),checkpoints=len(rows)+8,maximum_relative_scalar_error=largest)

if __name__=='__main__':print(json.dumps(review(json.load(open(sys.argv[1]))),sort_keys=True))
