"""Proven40-square/.6 circle and contact moves with ALM release and fixed starts.

The geometry treatment matches the successful bottleneck trials. The only
restart change is the separately verified25% immutable-input schedule. Larger
64/96-square .3 treatments and LP-only releases are deliberately absent here.
"""
import fq_fixed_pool_campaign as fixed

target = fixed.large.target
local = target.local
campaign = target.campaign

OPTIONS = local.aggressive.options('.6', '16', '1.001')+['--kick', '.1']
campaign.KICK_OPTIONS = {
    'productive_circle_060': list(OPTIONS),
    'productive_contact_060': list(OPTIONS),
}
campaign.MODE_SLOTS = ['productive_circle_060', 'productive_contact_060']
campaign.FOCUS = {'7_21_15': 2, '21_7_15': 2, '9_22_16': 1, '22_9_16': 1}
local.RELEASE_OPTIONS = ['--loosen', '1', '--outer', '45', '--pit', '100', '--flip-top', '16']


def productive_trial(job, options):
    contact = job[2] == 'productive_contact_060'
    previous = local.neighborhood
    local.neighborhood = target.contact_neighborhood if contact else target._circular_neighborhood
    try:
        record, donor = local.local_trial(job, options)
    finally:
        local.neighborhood = previous
    record['region_policy'] = 'contact_connected_40' if contact else 'circular_40'
    record['release_policy'] = 'original_alm45_polish100_flip16'
    return record, donor


campaign.configured_trial = productive_trial


def install():
    """Install the reviewed scheduler after configuring the actual trial hook."""
    return fixed.install()


if __name__ == '__main__':
    install()
    campaign.main()
