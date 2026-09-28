"""Disjoint defect budget and signed boundary ledger; no unknown-error claims."""
import math


def defect_budget(slabs, selected=tuple(range(34,48))):
    blocks=[]
    for index in sorted({r['block'] for r in slabs}):
        rows=[r for r in slabs if r['block']==index]
        values=[math.fsum(r['squared_l2'][i] for r in rows) for i in range(4)]
        if any(not math.isfinite(v) or v<0 for v in values):raise ValueError('invalid squared defect')
        blocks.append(dict(block=index,squared_l2=values,linf=[max(r['linf'][i] for r in rows) for i in range(4)],
            maximum_output_change=max(r['output_change_linf'] for r in rows),selected=index in selected))
    total=[math.fsum(r['squared_l2'][i] for r in blocks) for i in range(4)]
    if total[0]<=0:raise ValueError('zero original defect')
    regions={}
    for label,predicate in [('selected',lambda r:r['selected']),('unselected',lambda r:not r['selected']),
        ('unselected_changed_output',lambda r:not r['selected'] and r['maximum_output_change']>0),
        ('unselected_unchanged_output',lambda r:not r['selected'] and r['maximum_output_change']==0)]:
        rows=[r for r in blocks if predicate(r)]
        sums=[math.fsum(r['squared_l2'][i] for r in rows) for i in range(4)]
        regions[label]=dict(blocks=[r['block'] for r in rows],squared_l2=sums,
            original_square_fraction=sums[0]/total[0],full_square_fraction=(sums[1]/total[1] if total[1]>0 else None))
    # 该下限只适用于“其它块缺陷完全不变”的反事实，不是任何全域算法的下限。
    bound=math.sqrt(regions['unselected']['squared_l2'][0]/total[0])
    return dict(blocks=blocks,regions=regions,total_squared_l2=total,
        hypothetical_ratio_if_selected_zero_and_all_others_unchanged=bound,
        bound_is_conditional_on_unchanged_other_defects=True,strict_solution_error_bound=False)


def boundary_ledger(reports):
    if not reports:raise ValueError('empty boundary ledger')
    rows=[]
    for r in reports:
        a,b=r['current_boundary_bolometric'],r['mapped_boundary_bolometric']
        if not all(math.isfinite(v) for v in (a,b)):raise ValueError('nonfinite flux')
        rows.append(dict(block=r['block_index'],input=a,mapped=b,signed_change=b-a))
    current=math.fsum(r['input'] for r in rows);mapped=math.fsum(r['mapped'] for r in rows)
    signed=math.fsum(r['signed_change'] for r in rows);absolute=math.fsum(abs(r['signed_change']) for r in rows)
    scale=max(abs(current),abs(mapped))
    if scale<=0:raise ValueError('zero boundary scale')
    return dict(rows=rows,total_input=current,total_mapped=mapped,signed_block_sum=signed,
        absolute_block_change_sum=absolute,net_over_absolute=(abs(signed)/absolute if absolute else None),
        absolute_block_sum_over_scale=absolute/scale,net_block_sum_over_scale=abs(signed)/scale,
        reported_definition_bolometric=abs(mapped-current)/scale,
        summation_closure_over_scale=abs((mapped-current)-signed)/scale)
