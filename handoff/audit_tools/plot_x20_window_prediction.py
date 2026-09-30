import json,csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path('handoff/evidence');a=json.loads((p/'20260930-x20-82187-review.json').read_text());fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
for i,key in enumerate(('l2_ratios','linf_ratios')):
 v=a[key][1:];axes[0].bar([i-.18,i+.18],v,width=.32,color=['#387d54','#599bae'])
 for x,y in zip([i-.18,i+.18],v):axes[0].text(x,y+.02,f'{y:.4f}',ha='center')
axes[0].axhline(1,c='gray',ls=':');axes[0].set_xticks([0,1],['L2 defect','Maximum defect']);axes[0].set_ylim(0,1.16);axes[0].set_title('Full (green) / half (blue), relative to A16')
rows=[]
for i,key in enumerate(('boundary_l1','boundary_bolometric')):
 v=[a['boundary'][j][key]/a['boundary'][0][key] for j in (1,2)];axes[1].bar([i-.18,i+.18],v,width=.32,color=['#387d54','#599bae'])
 for x,y in zip([i-.18,i+.18],v):axes[1].text(x,y+.02,f'{y:.3f}',ha='center')
 rows += [(key,'full',v[0]),(key,'half',v[1])]
axes[1].axhline(1,c='red',ls='--');axes[1].set_xticks([0,1],['Boundary L1','Bolometric']);axes[1].set_ylim(0,1.16);axes[1].set_title('Boundary change / original change')
fig.suptitle('82187: all 11 full-field prediction gates pass; true maps remain untested')
fig.savefig(p/'20260930-x20-82187-review.png',dpi=150)
with (p/'20260930-x20-82187-review.csv').open('w') as f:
 w=csv.writer(f);w.writerow(['metric','fraction','ratio']);w.writerows(rows)
