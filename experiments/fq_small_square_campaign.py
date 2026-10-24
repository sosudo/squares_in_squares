"""High-leverage small-square basin search with rigid, soft and shrink hops.

Shrink hopping is restricted to square containers: the pinned native clamp
uses the common side on both axes, so rectangle offsets are not supported.
Every accepted soft result must reach exact zero aspect and pass the existing
unit-square raw/pandas gates. The shared supervisor bounds all work.
"""
from pathlib import Path
import shutil

import fq_soft_campaign as soft

campaign = soft.campaign
ordinary = soft._ordinary_trial
BASE = ['--loosen','1.001','--outer','55','--pit','100','--flip-top','24']
campaign.KICK_OPTIONS = {
    'small_kick03': BASE+['--kick','.03'],
    'small_kick12': BASE+['--kick','.12'],
    'small_kick25': BASE+['--kick','.25'],
    'small_soft15': ['--loosen','1','--soft-compress','--soft-a0','.15','--soft-steps','12',
        '--soft-kick','.015','--hold-f','1.001','--outer','45','--pit','100','--flip-top','16','--v'],
    'small_soft30': ['--loosen','1','--soft-compress','--soft-a0','.3','--soft-steps','12',
        '--soft-kick','.03','--hold-f','1.002','--outer','45','--pit','100','--flip-top','16','--v'],
    'small_hop3': ['--loosen','1','--shrink','--d0','.002','--dmin','.00001','--hops','4',
        '--hop-sigma','.05','--hop-k','3','--pit','80','--flip-top','16','--v'],
    'small_hop12': ['--loosen','1','--shrink','--d0','.002','--dmin','.00001','--hops','4',
        '--hop-sigma','.12','--hop-k','12','--pit','80','--flip-top','16','--v'],
    'small_round20': ['--loosen','1','--round-r0','.2','--round-compress','--round-steps','12',
        '--round-kick','.025','--outer','45','--pit','100','--flip-top','16'],
}
campaign.MODE_SLOTS = list(campaign.KICK_OPTIONS)
campaign.FOCUS = {}


def small_trial(job, options):
    w,h,d=map(int,job[0].split('_'))
    if w != h or len(job[1]) > 150:
        raise ValueError('This campaign supports square containers with at most150 squares')
    if '--soft-a0' in options:
        return soft.traced_trial(job,options)
    return ordinary(job,options)


campaign.configured_trial = small_trial
base_campaign = campaign.campaign


def frozen_campaign(args):
    # Keep the wrapper and all trial dependencies alongside the supervisor's
    # existing exact input/binary/source hash records before any solving.
    source_dir=args.out.with_name(args.out.name+'-source')
    source_dir.mkdir(exist_ok=False)
    paths=[Path(__file__),Path(soft.__file__),Path(campaign.__file__),Path(campaign.fq.__file__)]
    for path in paths:
        shutil.copy2(path,source_dir/path.name)
    campaign.atomic_json(source_dir/'manifest.json',{
        'files':{p.name:campaign.fq.digest(p) for p in paths},
        'square_only':True,'maximum_squares':150,'options':campaign.KICK_OPTIONS,
        'note':'Native shrink clamp is audited only for zero rectangle offsets. Soft steps require the original exact-zero trace gate.'})
    base_campaign(args)


campaign.campaign=frozen_campaign

if __name__=='__main__':
    campaign.main()
