"""Auditable immutable-source schedule for a future whole-packing GPU run.

This module is not used by the frozen v1 notebook. Source IDs arrive in frozen
builder order; runtime floating-point sorting cannot silently change the order.
"""
from collections import defaultdict


class BalancedSeedScheduler:
    MODES=('identity','column_slide','bend','hinge')
    AMPLITUDES=(.03,.08,.18,.30)
    TARGET_DEPTHS=(.00001,.0002,.002,.01,.02)
    LOOSE_SLACK=(.015,.04,.08)

    def __init__(self,source_ids):
        self.sources={int(n):tuple(names)for n,names in source_ids.items()}
        if not self.sources or any(not names or len(set(names))!=len(names)for names in self.sources.values()):
            raise ValueError('Each family requires nonempty unique frozen source IDs')
        if any(any(not isinstance(name,str)or not name or name.startswith('current_')for name in names)for names in self.sources.values()):
            raise ValueError('Alternative IDs must be strings distinct from current-reference IDs')
        self.family_starts=defaultdict(int)
        self.alternative_cursor=defaultdict(int)
        self.source_visits=defaultdict(int)

    def next(self,n):
        n=int(n)
        if n not in self.sources:raise ValueError('Unknown frozen family')
        ordinal=self.family_starts[n]
        is_reference=ordinal%4==0
        if is_reference:
            source_id=f'current_{n}';source_index=None;stratum_index=0
        else:
            source_index=self.alternative_cursor[n]%len(self.sources[n])
            source_id=self.sources[n][source_index];stratum_index=source_index
            self.alternative_cursor[n]+=1
        visit_key=(n,source_id);visit=self.source_visits[visit_key]
        self.source_visits[visit_key]+=1;self.family_starts[n]+=1
        return dict(n=n,source_id=source_id,source_index=source_index,is_reference=is_reference,
                    family_start_ordinal=ordinal,source_visit=visit,
                    alternative_cursor_after=self.alternative_cursor[n],
                    mode=self.MODES[(stratum_index+visit)%len(self.MODES)],
                    amplitude=self.AMPLITUDES[(stratum_index+visit//len(self.MODES))%len(self.AMPLITUDES)],
                    target_depth=self.TARGET_DEPTHS[(stratum_index+visit)%len(self.TARGET_DEPTHS)],
                    loose_slack=self.LOOSE_SLACK[(stratum_index+visit)%len(self.LOOSE_SLACK)])

    def snapshot(self):
        return dict(frozen_source_ids={str(n):list(names)for n,names in self.sources.items()},
                    family_starts={str(n):v for n,v in self.family_starts.items()},
                    alternative_cursors={str(n):v for n,v in self.alternative_cursor.items()},
                    source_visits={str(n):{name:self.source_visits[(n,name)]for name in (f'current_{n}',*names)}
                                   for n,names in self.sources.items()})
