"""Area-preserving aspect continuation, followed by rigid official certification.

Soft aspect variables are optimizer-only degrees of freedom. FQ returns them
to zero before its ordinary rigid finish; only ordinary unit-square poses can
enter the unchanged raw and numeric-transport certification gates.
"""
import hashlib
from pathlib import Path
import re

import fq_multiscale_campaign as campaign

BASE = ['--loosen', '1', '--soft-compress', '--soft-steps', '8',
        '--soft-kick', '.003', '--outer', '35', '--pit', '80', '--flip-top', '12', '--v']
campaign.KICK_OPTIONS = {
    'soft_003': BASE+['--soft-a0', '.03', '--hold-f', '1'],
    'soft_008': BASE+['--soft-a0', '.08', '--hold-f', '1'],
    'soft_015': BASE+['--soft-a0', '.15', '--hold-f', '1'],
    'soft_008_relaxed': BASE+['--soft-a0', '.08', '--hold-f', '1.002'],
}
campaign.MODE_SLOTS = ['soft_003', 'soft_008', 'soft_015', 'soft_008_relaxed']
campaign.FOCUS = {
    '5_17_7': 4, '17_5_7': 4,
    '7_19_13': 3, '19_7_13': 3,
    '7_20_14': 3, '20_7_14': 3,
    '6_22_16': 3, '22_6_16': 3,
    '10_23_14': 2, '23_10_14': 2,
}

_ordinary_trial = campaign.configured_trial


def traced_trial(job, options):
    record, donor = _ordinary_trial(job, options)
    key, _, mode, _, directory, seed, _, _ = job
    path = Path(directory)/f'{key}-{mode}-{seed}.log'
    if path.exists():
        text = path.read_text()
        values = [float(x) for x in re.findall(r'soft eps ([0-9.eE+-]+) hold', text)]
        steps = int(options[options.index('--soft-steps')+1])
        amplitude = float(options[options.index('--soft-a0')+1])
        trace_valid = (len(values) == steps and values[-1] == 0.
                       and all(a >= b >= 0 for a, b in zip(values, values[1:]))
                       and record.get('fq', {}).get('soft', {}).get('a0') == amplitude)
        record['rigid_return_trace'] = {
            'valid': trace_valid, 'expected_steps': steps, 'reported_aspect_epsilons': values,
            'final_reported_epsilon': values[-1] if values else None,
            'log_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'source_invariant': 'Pinned fq.rs sets e=e0*(1-k/K)^p; at k=K e is exactly0 and p.b is cleared. It calls set_soft(0.0) again before the rigid finish.',
            'unit_square_certificate_valid': record.get('certificate', {}).get('valid', False),
        }
        if donor is not None and not trace_valid:
            return {**record, 'status': 'rejected_soft_return_trace'}, None
    elif donor is not None:
        return {**record, 'status': 'rejected_missing_soft_return_trace'}, None
    return record, donor


campaign.configured_trial = traced_trial

if __name__ == '__main__':
    campaign.main()
