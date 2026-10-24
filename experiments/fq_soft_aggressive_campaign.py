"""Prepared stronger aspect-continuation configuration; separate from soft v1.

This module uses the same traced rigid-return gate. It does not launch work on
import; a separately authorized bounded invocation is required for execution.
"""
import fq_soft_campaign as soft

campaign = soft.campaign


def options(amplitude, steps, hold):
    return ['--loosen', '1', '--soft-compress', '--soft-a0', amplitude,
            '--soft-steps', steps, '--soft-p', '2', '--soft-kick', '.004',
            '--hold-f', hold, '--outer', '45', '--pit', '100', '--flip-top', '16', '--v']


campaign.KICK_OPTIONS = {
    'soft_030_tight': options('.3', '12', '1.001'),
    'soft_030_relaxed': options('.3', '12', '1.005'),
    'soft_060_tight': options('.6', '16', '1.001'),
    'soft_060_relaxed': options('.6', '16', '1.005'),
}
campaign.MODE_SLOTS = ['soft_030_tight', 'soft_060_relaxed',
                       'soft_030_relaxed', 'soft_060_tight']
campaign.FOCUS.update({
    '5_17_8': 4, '17_5_8': 4,
    '9_20_13': 3, '20_9_13': 3,
    '5_17_6': 2, '17_5_6': 2,
    '7_19_12': 2, '19_7_12': 2,
    '7_20_13': 2, '20_7_13': 2,
    '10_23_13': 2, '23_10_13': 2,
})

if __name__ == '__main__':
    campaign.main()
