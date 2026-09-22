"""Three bounded 1/64 response steps, each gated by dual confirmation.

Reuse the tested sequence and explicit-amplitude confirmation preparation in
one process. Frozen modules and historical declarations remain unchanged.
"""
from contextlib import contextmanager
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'scripts'),str(ROOT/'hpc')]
from operations import bounded_outer_sequence as sequence
from operations import confirm12_then_step13 as confirmation
stage=sequence.stage
SOURCE='outputs/hpc/step12-amplitude-20260922'
FIRST_INDEX=13
ALPHAS={'full':1/64,'half':1/128}


@contextmanager
def sequence_contract():
    old_sequence=(sequence.SOURCE,sequence.FIRST_INDEX)
    old_stage=(stage.configure,stage.prepare_confirmation,
               stage.SOURCE,stage.ACCEPTED_INDEX,stage.FORMAL_SOURCE)
    old_confirmation=(confirmation.SOURCE,confirmation.ACCEPTED_INDEX,confirmation.FORMAL_SOURCE)
    old_alphas=stage.batch.ALPHAS
    original_configure=stage.configure
    def configure(source,index):
        if not isinstance(index,int) or isinstance(index,bool) or not 12<=index<=15:
            raise ValueError('source index outside steps 12 through 15')
        original_configure(source,index)
        confirmation.SOURCE=stage.SOURCE
        confirmation.ACCEPTED_INDEX=stage.ACCEPTED_INDEX
        confirmation.FORMAL_SOURCE=stage.FORMAL_SOURCE
    sequence.SOURCE=SOURCE
    sequence.FIRST_INDEX=FIRST_INDEX
    stage.configure=configure
    stage.prepare_confirmation=confirmation.prepare_confirmation
    stage.batch.ALPHAS=dict(ALPHAS)
    try:
        if (sequence.STEP_COUNT!=3 or sequence.MAXIMUM_MAPS!=78
            or sequence.MAXIMUM_PAIRS!=27 or confirmation.ACCEPTED_ALPHA!=1/64):
            raise RuntimeError('bounded sequence or accepted amplitude contract changed')
        yield
    finally:
        sequence.SOURCE,sequence.FIRST_INDEX=old_sequence
        (stage.configure,stage.prepare_confirmation,stage.SOURCE,
         stage.ACCEPTED_INDEX,stage.FORMAL_SOURCE)=old_stage
        (confirmation.SOURCE,confirmation.ACCEPTED_INDEX,
         confirmation.FORMAL_SOURCE)=old_confirmation
        stage.batch.ALPHAS=old_alphas


def main():
    with sequence_contract():
        sequence.main()


if __name__=='__main__':main()
