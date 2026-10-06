from pathlib import Path
import pytest
from handoff.audit_tools.audit_x20_86191_cost import audit, classify, PINS
ROOT=Path(__file__).resolve().parents[1]


def test_ordered_products_are_not_algebraically_merged():
    rows=[{'expression':('a','b')},{'expression':('b','a')},{'expression':('a','a')}]
    c=classify(rows,[{'expression':'delta'}])
    assert c['matrix_diagonal']==1 and c['matrix_off_diagonal']==2 and c['total_dot_calls']==4


def test_pinned_inventory_and_payload_units():
    r=audit(ROOT);c=r['counts'];p=r['school_slab']
    assert (c['matrix_diagonal'],c['matrix_off_diagonal'],c['reconstruction_squares'])==(15,42,15)
    assert c['sum_reductions']==144 and c['discarded_reconstruction_absolute_sums']==15
    assert c['underflow_boolean_expression_results']==360
    assert p['one_longdouble_array_bytes']==64*1024**2
    assert p['cumulative_product_and_absolute_array_payload_bytes']==9216*1024**2
    assert p['cumulative_underflow_boolean_result_payload_bytes']==1440*1024**2
    assert not r['numeric_equivalence_tested'] and not r['component_profile_measured']


@pytest.mark.parametrize('name',list(PINS))
def test_each_source_mutation_rejected(tmp_path,name):
    for path in PINS:
        q=tmp_path/path;q.parent.mkdir(parents=True,exist_ok=True)
        q.write_bytes((ROOT/path).read_bytes()+(b'\n' if path==name else b''))
    with pytest.raises(ValueError,match='source pin'):audit(tmp_path)
