"""Select retained input/output of each last actual map, without splicing runs."""
from operations.material_direction_diagnostic import latest_pair


def last_actual_map(state):
    latest_pair(state)
    previous, row = state['history'][-2:]
    if (previous['output_path'] != row['input_path']
        or previous['output_sha256'] != row['input_sha256']
        or state['slots'][state['current_slot']] != row['output_path']
        or state['current_sha256'] != row['output_sha256']):
        raise ValueError('latest real map or retained output lineage differs')
    # 中文：X是末次已测map的输入，Y是其真实输出；Y尚不是新的正式反馈端点。
    return [{'path':row[k+'_path'],'sha256':row[k+'_sha256']} for k in ('input','output')]
