"""Immutable retention after the public FTMC raw and pandas certificate gate.

``keep`` is a caller-attestation boundary: call it ONLY after the unchanged
public ``certify(q)`` returned True for these exact coordinates. It does not
certify exploratory inputs. Unknown bank incumbents supplied to ``flush`` are
instead checked with the constructor's original ``certify`` callback. The
unchanged public metric source is pinned and its hash is bound to every record.

Use a different prefix for each worker. Each accepted geometry and its record
are published immediately without replacement. Aggregate NPZ/index checkpoints
are throttled; ``finalflush(bank)`` always publishes the final checkpoint.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import tempfile
import time

import numpy as np


PUBLIC_METRIC_SHA256 = '312458227c78f56bd5e2eec3dc5fbb8787989422bbf72ce66c3c290048e89733'


class ArchiveIntegrityError(ValueError):
    """An immutable path or its certificate metadata has inconsistent content."""


def _snapshot_digest(payload):
    return hashlib.sha256(payload).hexdigest()


def _pose(q):
    result = np.array(q, copy=True, order='C')
    if (result.ndim != 2 or result.shape[1] != 3 or not len(result)
            or result.dtype.kind != 'f' or not np.isfinite(result).all()):
        raise ValueError('Expected a nonempty finite floating (n, 3) pose')
    result.flags.writeable = False
    return result


def _payload(q):
    buffer = io.BytesIO()
    np.save(buffer, q, allow_pickle=False)
    return buffer.getvalue()


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()


def _bloat(q, w, h):
    extent = .5*(np.abs(np.cos(q[:, 2]))+np.abs(np.sin(q[:, 2])))
    dimensions = ((q[:, :2]+extent[:, None]).max(axis=0)
                  - (q[:, :2]-extent[:, None]).min(axis=0))
    return float(max(dimensions-[w, h]))


def _fingerprint(q):
    """CPU-only copy of the public worker's coarse sampling fingerprint."""
    a = (q[:, 2]+np.pi/4) % (np.pi/2)-np.pi/4
    tilted = q[np.abs(a) > .018]
    hist = np.histogram(a, bins=np.linspace(-np.pi/4, np.pi/4, 13))[0]
    if len(tilted):
        xy = tilted[:, :2]-tilted[:, :2].min(axis=0)
        span = np.maximum(np.ptp(xy, axis=0), 1.)
        shape = np.histogram2d(xy[:, 0]/span[0], xy[:, 1]/span[1],
                              bins=(5, 8), range=((0, 1.000001), (0, 1.000001)))[0].ravel()
    else:
        shape = np.zeros(40)
    return hashlib.sha256(np.r_[len(tilted), hist, shape].astype(np.int32).tobytes()).hexdigest()[:12]


def _key_dimensions(key, q, w=None, h=None):
    try:
        ww, hh, d = map(int, key.split('_'))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError('Expected an FTMC w_h_d key') from error
    if (key != f'{ww}_{hh}_{d}' or ww <= 0 or hh <= 0 or d < 0
            or len(q) != ww*hh+d or (w is not None and ww != w)
            or (h is not None and hh != h)):
        raise ValueError('Pose size or bounds disagree with FTMC key: '+key)
    return ww, hh


def _atomic_bytes(path, payload, *, immutable=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if immutable and path.exists():
        if path.read_bytes() != payload:
            raise ArchiveIntegrityError('Immutable archive collision: '+str(path))
        return
    fd, temporary = tempfile.mkstemp(prefix='.'+path.name+'.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if immutable:
            # link is atomic and refuses to replace a concurrent/existing file.
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_bytes() != payload:
                    raise ArchiveIntegrityError('Immutable archive collision: '+str(path))
        else:
            os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _atomic_npz(path, arrays):
    # ZIP_STORED avoids repeatedly compressing immutable geometry at checkpoints.
    buffer = io.BytesIO()
    np.savez(buffer, **arrays)
    payload = buffer.getvalue()
    _atomic_bytes(path, payload)
    return hashlib.sha256(payload).hexdigest()


class CertifiedArchive:
    """Retain every certified exact pose and strict bests independently of wins.

    ``prefix.npz`` contains every certified ``key__geometry_sha256`` pose;
    ``prefix_best.npz`` contains strict per-key bests; ``prefix_incumbents.npz``
    contains the latest certified bank. ``prefix.json`` binds those checkpoints
    to immutable records under ``prefix_snapshots/``. Individual ``.npy`` and
    per-key ``.json`` records are authoritative if a checkpoint is interrupted.

    ``certify`` must be the original raw-and-pandas public admission function,
    or an observer that preserves its result. It is mandatory only if an unseen
    incumbent is provided. ``fingerprint`` can be the public worker's function.
    Every constructor verifies the exact original public metric bytes.
    """

    def __init__(self, prefix, *, metric_path='research/official_metric.py',
                 metric_sha256=None, certify=None, fingerprint=None,
                 flush_seconds=20.0):
        self.prefix = Path(prefix)
        self.metric_path = Path(metric_path)
        self.metric_sha256 = metric_sha256 or PUBLIC_METRIC_SHA256
        if self.metric_sha256 != PUBLIC_METRIC_SHA256:
            raise ArchiveIntegrityError('Only the unchanged public metric is supported')
        self._verify_metric()
        if not math.isfinite(flush_seconds) or flush_seconds < 0:
            raise ValueError('flush_seconds must be finite and nonnegative')
        self.flush_seconds = float(flush_seconds)
        self.snapshot_dir = Path(str(self.prefix)+'_snapshots')
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._certify = certify
        self._fingerprint = fingerprint or _fingerprint
        self._records = {}
        self._poses = {}
        self._best_key = {}
        self._best_signature = {}
        self._incumbents = {}
        self._bank = None
        self._last_flush = -math.inf
        self._dirty = True
        self._reload()

    def _verify_metric(self):
        if hashlib.sha256(self.metric_path.read_bytes()).hexdigest() != self.metric_sha256:
            raise ArchiveIntegrityError('Public metric source hash mismatch')

    def _record(self, key, signature, q, w, h, digest):
        return {'status': 'certified_geometry', 'key': key, 'signature': signature,
                'geometry_sha256': digest, 'npy_sha256': digest,
                'official_metric_sha256': self.metric_sha256,
                'raw': True, 'roundtrip': True, 'official_raw_and_pandas': True,
                'shape': list(q.shape), 'dtype': q.dtype.str,
                'w': w, 'h': h, 'bloat': _bloat(q, w, h),
                'snapshot': digest+'.npy',
                'certification_contract': 'unchanged_public_certify_exact_geometry'}

    def _remember(self, identity, record, q):
        self._records[identity] = record
        self._poses[identity] = q
        key = record['key']
        signature_key = key+'__'+record['signature']
        for table, name in ((self._best_key, key), (self._best_signature, signature_key)):
            previous = table.get(name)
            if previous is None or record['bloat'] < self._records[previous]['bloat']:
                table[name] = identity

    def _reload(self):
        for path in sorted(self.snapshot_dir.glob('*.json')):
            record = json.loads(path.read_text())
            digest = record['geometry_sha256']
            if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                raise ArchiveIntegrityError('Invalid geometry hash in '+str(path))
            payload = (self.snapshot_dir/(digest+'.npy')).read_bytes()
            if _snapshot_digest(payload) != digest:
                raise ArchiveIntegrityError('Snapshot hash mismatch: '+digest)
            q = _pose(np.load(io.BytesIO(payload), allow_pickle=False))
            w, h = _key_dimensions(record['key'], q)
            expected = self._record(record['key'], record['signature'], q, w, h, digest)
            identity = record['key']+'__'+digest
            if record != expected or path.name != identity+'.json' or _payload(q) != payload:
                raise ArchiveIntegrityError('Certificate metadata mismatch: '+str(path))
            self._remember(identity, record, q)
        index_path = Path(str(self.prefix)+'.json')
        if index_path.exists():
            index = json.loads(index_path.read_text())
            if index['official_metric_sha256'] != self.metric_sha256:
                raise ArchiveIntegrityError('Checkpoint metric hash mismatch')
            for key, identity in index['incumbents'].items():
                if identity not in self._records or self._records[identity]['key'] != key:
                    raise ArchiveIntegrityError('Checkpoint references an uncertified incumbent')
                self._incumbents[key] = identity

    @property
    def best_by_key(self):
        return {key: copy.deepcopy(self._records[identity]) for key, identity in self._best_key.items()}

    @property
    def best_by_fingerprint(self):
        return {key: copy.deepcopy(self._records[identity]) for key, identity in self._best_signature.items()}

    def keep(self, wins, key, signature, q, w, h):
        """Retain exact, already-certified q; return whether its signature improved.

        All snapshots are independent copies. A worse same-signature arrival
        remains recoverable as a unique pose, but cannot replace ``wins`` or
        either strict-best table. Input mutation after return cannot alter them.
        """
        q = _pose(q)
        _key_dimensions(key, q, w, h)
        if not isinstance(signature, str) or not signature:
            raise ValueError('A nonempty public fingerprint is required')
        payload = _payload(q)
        digest = _snapshot_digest(payload)
        identity = key+'__'+digest
        record = self._record(key, signature, q, w, h, digest)
        _atomic_bytes(self.snapshot_dir/(digest+'.npy'), payload, immutable=True)
        _atomic_bytes(self.snapshot_dir/(identity+'.json'), _json_bytes(record), immutable=True)
        previous = self._best_signature.get(key+'__'+signature)
        is_best = previous is None or record['bloat'] < self._records[previous]['bloat']
        is_new = identity not in self._records
        self._remember(identity, record, q)
        name = key+'__'+signature
        best = self._poses[self._best_signature[name]]
        # Respect an already better source incumbent (e.g. a resume wins map).
        if name not in wins or _bloat(best, w, h) < _bloat(wins[name], w, h):
            wins[name] = best.copy()
        else:
            wins[name] = _pose(wins[name]).copy()
        self._dirty |= is_new
        return is_best

    def _capture_bank(self, bank):
        incumbents = {}
        for key, pose in bank.items():
            q = _pose(pose)
            w, h = _key_dimensions(key, q)
            digest = _snapshot_digest(_payload(q))
            identity = key+'__'+digest
            if identity not in self._records:
                if self._certify is None:
                    raise ValueError('Unknown bank incumbent requires original certify callback: '+key)
                self._verify_metric()
                if not self._certify(q):
                    raise ValueError('Bank incumbent failed original certification: '+key)
                self.keep({}, key, self._fingerprint(q), q, w, h)
            elif _payload(self._poses[identity]) != _payload(q):
                raise ArchiveIntegrityError('Incumbent content hash collision: '+key)
            incumbents[key] = identity
        self._dirty |= incumbents != self._incumbents
        self._incumbents = incumbents

    def flush(self, bank=None, *, force=False):
        """Publish an aggregate at most once per cadence; return whether written."""
        if bank is not None:
            # Keep the live worker map even on a throttled checkpoint so a
            # finally block can call finalflush() without the worker's locals.
            self._bank = bank
        now = time.monotonic()
        if not force and now-self._last_flush < self.flush_seconds:
            return False
        if self._bank is not None:
            self._capture_bank(self._bank)
        if not force and not self._dirty:
            self._last_flush = now
            return False
        self._verify_metric()
        outputs = {}
        for suffix, poses in (
            ('.npz', self._poses),
            ('_best.npz', {k: self._poses[v] for k, v in self._best_key.items()}),
            ('_incumbents.npz', {k: self._poses[v] for k, v in self._incumbents.items()}),
        ):
            path = Path(str(self.prefix)+suffix)
            outputs[path.name] = _atomic_npz(path, poses)
        index = {'schema_version': 1, 'status': 'certified_geometry',
                 'official_metric_sha256': self.metric_sha256,
                 'records': self._records, 'best_by_key': self._best_key,
                 'best_by_fingerprint': self._best_signature,
                 'incumbents': self._incumbents, 'aggregate_sha256': outputs,
                 'snapshot_directory': self.snapshot_dir.name,
                 'certification_contract': 'keep_only_after_unchanged_public_certify'}
        _atomic_bytes(Path(str(self.prefix)+'.json'), _json_bytes(index))
        self._last_flush = now
        self._dirty = False
        return True

    def finalflush(self, bank=None):
        """Force durable final snapshots, including the supplied current bank."""
        return self.flush(bank=bank, force=True)


def update_search_archive(archive, key, q, w, h, signature, *, fingerprint=None):
    """Retain the lowest-bloat certified pose for up to 12 public signatures.

    Call only after public certification; this is a sampling policy, not an
    admission gate. Existing entries must also be valid complete poses. The
    lowest-bloat pose is protected, stale same-signature poses are replaced on
    strict improvement, and geometry is copied without normalization/rounding.
    """
    fingerprint = fingerprint or _fingerprint
    q = _pose(q)
    _key_dimensions(key, q, w, h)
    best = {}
    for previous in archive.get(key, []):
        previous = _pose(previous)
        _key_dimensions(key, previous, w, h)
        previous_signature = fingerprint(previous)
        if (previous_signature not in best
                or _bloat(previous, w, h) < _bloat(best[previous_signature], w, h)):
            best[previous_signature] = previous
    if signature not in best or _bloat(q, w, h) < _bloat(best[signature], w, h):
        best[signature] = q
    archive[key] = [p.copy() for p in sorted(best.values(), key=lambda p: _bloat(p, w, h))[:12]]
    return archive[key]
