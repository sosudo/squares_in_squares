"""Resolve notebook attachments by expected filename and exact SHA-256, offline.

Kaggle currently ignores version suffixes in kernel_sources and attaches the
latest output. Expected version labels preserve intent; content hashes are the
actual immutable binding. Never accept a different hash after an export race.
"""
from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import re


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_manifest(manifest):
    if manifest.get('schema_version') != 1:
        raise ValueError('Unsupported attachment manifest version')
    donors = manifest.get('gadgets', {})
    groups = manifest.get('groups', {'combined': list(donors)})
    if not isinstance(donors, dict) or not isinstance(groups, dict) or not groups:
        raise ValueError('Named donors and comparison groups must be dictionaries')
    if 'baseline' in donors:
        raise ValueError('The baseline input label is reserved')
    kernels = set()
    for label, record in [('baseline', manifest['baseline']), *donors.items()]:
        if not re.fullmatch(r'[a-z][a-z0-9_]*', label):
            raise ValueError('Unsafe input label')
        modes=[key for key in ('kernel','local_path','embedded_path') if key in record]
        if len(modes)!=1 or (label=='baseline' and modes!=['kernel']):
            raise ValueError('Each input needs exactly one source; baseline must be a notebook output')
        if 'kernel' in record:
            if not re.fullmatch(r'[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/[1-9][0-9]*', record['kernel']):
                raise ValueError('Every notebook source requires an expected numeric version')
            kernels.add(record['kernel'])
        if 'embedded_path' in record:
            embedded=PurePosixPath(record['embedded_path'])
            if embedded.is_absolute() or '..' in embedded.parts or not embedded.name:
                raise ValueError('Unsafe embedded input path')
        path = PurePosixPath(record['file'])
        if path.is_absolute() or '..' in path.parts or not path.name:
            raise ValueError('Unsafe attached output filename')
        if not re.fullmatch(r'[0-9a-f]{64}', record['sha256']):
            raise ValueError('Each attachment requires an exact SHA-256')
    for label, members in groups.items():
        if not re.fullmatch(r'[a-z][a-z0-9_]*', label):
            raise ValueError('Unsafe comparison group label')
        if not isinstance(members, list) or any(member not in donors for member in members):
            raise ValueError('Comparison group references an unknown donor')
        if len(members) != len(set(members)):
            raise ValueError('Duplicate donor inside comparison group')
    return sorted(kernels)


def resolve_inputs(manifest, mount_root='/kaggle/input', embedded_root=None):
    """Mount layout may change; exact pinned content and names must not change."""
    validate_manifest(manifest)
    mount_root = Path(mount_root).resolve()
    if not mount_root.is_dir():
        raise FileNotFoundError('Notebook attachment mount is unavailable')
    hashes, resolved = {}, {}
    for label, record in [('baseline', manifest['baseline']), *manifest.get('gadgets', {}).items()]:
        if 'local_path' in record:
            raise ValueError('Local donor must be embedded by the builder before runtime')
        if 'embedded_path' in record:
            if embedded_root is None:
                raise ValueError('Embedded donor root is unavailable')
            embedded_root=Path(embedded_root).resolve()
            actual=(embedded_root/record['embedded_path']).resolve()
            if not actual.is_relative_to(embedded_root) or not actual.is_file() or digest(actual)!=record['sha256']:
                raise ValueError(f'Embedded donor filename/hash mismatch: {label}')
            resolved[label]={'path':str(actual),'sha256':record['sha256'],'kernel':None,'file':record['file'],
                             'embedded_path':record['embedded_path']}
            continue
        relative = PurePosixPath(record['file'])
        matches = []
        for path in sorted(mount_root.rglob(relative.name)):
            actual = path.resolve()
            if not actual.is_relative_to(mount_root) or not actual.is_file():
                continue
            # Kaggle may flatten an attached output directory. Exact bytes are
            # authoritative; basename avoids hashing unrelated large outputs.
            if str(actual) not in hashes:
                hashes[str(actual)] = digest(actual)
            if hashes[str(actual)] == record['sha256']:
                matches.append(actual)
        if not matches:
            raise ValueError(f'No attachment matches expected filename/hash for {label}')
        resolved[label] = {'path': str(matches[0]), 'sha256': record['sha256'],
                           'kernel': record['kernel'], 'file': record['file']}
    return {'inputs': resolved, 'groups': manifest.get('groups', {'combined': list(manifest.get('gadgets', {}))})}
