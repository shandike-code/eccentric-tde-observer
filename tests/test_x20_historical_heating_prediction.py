import json
from copy import deepcopy
from pathlib import Path
import pytest
from operations.x20_historical_heating_prediction import require_screen,live_path


def screen():
    return json.loads((Path(__file__).resolve().parents[1]/'handoff/evidence/20261001-x20-historical-heating-screen-v2.json').read_text())


def test_frozen_global_coefficients_and_live_source_mapping():
    s=screen();assert require_screen(s)==s['selected_coefficients']
    assert str(live_path('outputs/review-20260925/x20-global-feedback-82518-complete-received/historical/config.json'))=='outputs/hpc/x20-global-window-feedback-20261001/historical/config.json'


@pytest.mark.parametrize('damage',['coefficient','scope','order','claim','cap','gram'])
def test_tampering_does_not_launch(damage):
    s=deepcopy(screen())
    if damage=='coefficient':s['selected_coefficients'][0]+=1e-6
    elif damage=='scope':s['new_maps']=1
    elif damage=='order':s['field_order'].reverse()
    elif damage=='claim':s['full_field_positivity_checked']=True
    elif damage=='cap':s['coefficient_l1_cap']=18
    else:s['exact_stored_vector_gram'][1][1]['numerator']='0'
    with pytest.raises((ValueError,AssertionError)):require_screen(s)
