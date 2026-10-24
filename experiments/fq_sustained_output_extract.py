"""Copy a finite whitelist from one exact sustained-run output attachment.

This worker never imports optimizers, native solvers, metrics or GPU libraries.
The attachment is identified by exact manifest/config bytes, not its mount name.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time
import zipfile

MIB = 1024**2
GLOBAL_OPTIONAL = ('supervisor-summary.json', 'pilot-summary.json', 'worker.log',
                   'queue-0.json', 'queue-1.json', 'queue-0.log', 'queue-1.log')
CASE_OPTIONAL = ('case-config.json', 'pilot-config.json', 'hop-config.json', 'pilot-inputs.npz',
                 'chain-design.json', 'preflight.json', 'search-epoch.json', 'hop-status.json',
                 'pilot-summary.json', 'recovery.json', 'finish-summary.json', 'raw-index.json',
                 'hop-events.jsonl', 'final-current-best.npz', 'preflight.log', 'search.log',
                 'finish.log', 'zero-energy-index.json')
CASE_TREES = ('preflight', 'finish')
PACKET = re.compile(r'packet-[0-9]{4,}\.npz\Z')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def relative_name(name):
    value = PurePosixPath(name)
    if not name or value.is_absolute() or '..' in value.parts or str(value) != name:
        raise ValueError('unsafe_relative_path:'+str(name))
    return name


def regular(root, name):
    path = root/relative_name(name)
    for part in (path, *path.parents):
        if part == root.parent:
            break
        if part.is_symlink():
            raise ValueError('symlink_forbidden:'+name)
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('not_regular_file:'+name)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('outside_attachment:'+name)
    return path


def load_json(path, limit=32*MIB):
    if path.stat().st_size > limit:
        raise ValueError('oversize_json:'+str(path))
    return json.loads(path.read_bytes())


def identify(input_root, config):
    matches = []
    for manifest in sorted(Path(input_root).rglob('job_manifest.json')):
        if len(matches) > 1:
            break
        root = manifest.parent
        if manifest.is_symlink() or manifest.stat().st_size > MIB:
            continue
        if digest(regular(root, 'job_manifest.json')) != config['parent_manifest_sha256']:
            continue
        path = regular(root, 'sustained-config.json')
        if digest(path) != config['parent_config_sha256']:
            raise ValueError('bound_parent_config_changed')
        matches.append(root)
    if len(matches) != 1:
        raise ValueError('expected_one_exact_parent_attachment:'+str(len(matches)))
    return matches[0]


def terminal_packet(root, n, entry):
    """Accept only the indexed packet inside this case's raw-hop directory."""
    value = str(entry['path'])
    prefix = '/kaggle/working/'+f'case-{n}/'
    if value.startswith(prefix):
        value = value[len(prefix):]
    parts = PurePosixPath(value).parts
    if len(parts) != 2 or parts[0] != 'raw-hop' or not PACKET.fullmatch(parts[1]):
        raise ValueError('unexpected_indexed_packet_path:'+value)
    name = f'case-{n}/'+value
    path = regular(root, name)
    if path.stat().st_size != entry['bytes']:
        raise ValueError('terminal_packet_size_changed:'+name)
    return name


def select_files(root, config):
    manifest = load_json(regular(root, 'job_manifest.json'))
    policy = load_json(regular(root, 'sustained-config.json'))
    if sorted(map(int, policy['cases'])) != config['cases']:
        raise ValueError('parent_case_inventory_changed')
    if manifest['configuration'] != policy or manifest['files'] != config['parent_files']:
        raise ValueError('parent_configuration_or_file_inventory_changed')
    selected = {'job_manifest.json':config['parent_manifest_sha256']}
    missing = []
    for name, expected in manifest['files'].items():
        regular(root, name)
        selected[name] = expected

    def optional(name):
        if (root/name).exists() or (root/name).is_symlink():
            regular(root, name); selected.setdefault(name, None)
        else:
            missing.append(name)

    for name in GLOBAL_OPTIONAL:
        optional(name)
    queues = {}
    for device in (0,1):
        path = root/f'queue-{device}.json'
        if path.exists():
            queues.update(load_json(path))
    case_status = {}
    for n in config['cases']:
        folder = root/f'case-{n}'
        for name in CASE_OPTIONAL:
            optional(f'case-{n}/'+name)
        for tree in CASE_TREES:
            base = folder/tree
            if base.is_symlink():
                raise ValueError('symlink_forbidden:'+str(base))
            if not base.exists():
                missing.append(f'case-{n}/{tree}/'); continue
            for directory, dirs, names in os.walk(base, followlinks=False):
                for child in dirs:
                    if (Path(directory)/child).is_symlink():
                        raise ValueError('symlink_forbidden:'+str(Path(directory)/child))
                for name in sorted(names):
                    optional((Path(directory)/name).relative_to(root).as_posix())
                    if len(selected) > config['max_files']:
                        raise ValueError('selected_file_count_cap')
        terminal = None; counts = {'completed':0, 'pending':0, 'other':0}
        index_path = folder/'raw-index.json'
        if index_path.exists():
            index = load_json(index_path)
            for entry in index['packets']:
                status = entry.get('status', 'other')
                counts[status if status in ('completed','pending') else 'other'] += 1
                if status == 'completed':
                    terminal = entry
            if terminal is not None:
                name = terminal_packet(root, n, terminal)
                selected[name] = terminal['sha256']
                terminal = dict(path=name, sha256=terminal['sha256'], bytes=terminal['bytes'])
        slots = {}
        records = {}
        results = folder/'finish/results.json'
        if results.exists():
            records = {str(row['slot']):row.get('status') for row in load_json(results)}
        for slot in range(4):
            prefix = f'case-{n}/finish/slot-{slot:02d}-'
            files = sorted(name for name in selected if name.startswith(prefix))
            slots[str(slot)] = dict(status=records.get(str(slot), 'files_without_result' if files else 'no_slot_files'), files=files)
        case_status[str(n)] = dict(queue_status=queues.get(str(n),{}).get('status', 'not_reported'),
            raw_index_counts=counts, terminal_packet=terminal, finish_slots=slots,
            raw_history_not_copied=True, nonterminal_packets_not_opened=True,
            zero_energy_raw_snapshots_not_copied=True,
            zero_energy_scope='Index metadata is copied; raw zero-energy snapshots remain in the immutable parent outputs.')
    if len(selected) > config['max_files']:
        raise ValueError('selected_file_count_cap')
    return selected, missing, case_status


class CappedOutput:
    """Bound actual ZIP bytes during writes, including its central directory."""
    def __init__(self, stream, maximum):
        self.stream = stream; self.maximum = maximum; self.highwater = 0
    def write(self, data):
        position = self.stream.tell()
        if position+len(data) > self.maximum:
            raise ValueError('zip_byte_cap')
        result = self.stream.write(data)
        self.highwater = max(self.highwater, self.stream.tell())
        return result
    def tell(self): return self.stream.tell()
    def seek(self, *args): return self.stream.seek(*args)
    def flush(self): return self.stream.flush()


def extract(root, out, config):
    started = time.monotonic(); root = Path(root).resolve(); out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise ValueError('fresh_output_directory_required')
    if (root == out.resolve() or out.resolve().is_relative_to(root)):
        raise ValueError('output_must_be_outside_parent_attachment')
    if digest(regular(root, 'job_manifest.json')) != config['parent_manifest_sha256']:
        raise ValueError('bound_parent_manifest_changed')
    if digest(regular(root, 'sustained-config.json')) != config['parent_config_sha256']:
        raise ValueError('bound_parent_config_changed')
    selected, missing, case_status = select_files(root, config)
    uncompressed = sum(regular(root, name).stat().st_size for name in selected)
    if uncompressed > config['max_uncompressed_bytes']:
        raise ValueError('uncompressed_byte_cap:'+str(uncompressed))
    incoming = out/'selected-output.zip.incoming'; inventory = {}; copied = 0
    try:
        with incoming.open('xb') as raw:
            capped = CappedOutput(raw, config['max_zip_bytes'])
            with zipfile.ZipFile(capped, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
                for name in sorted(selected):
                    path = regular(root, name); before = path.stat(); h = hashlib.sha256(); size = 0
                    info = zipfile.ZipInfo.from_file(path, arcname=name)
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info._compresslevel = 1
                    with path.open('rb') as source, archive.open(info, 'w', force_zip64=True) as target:
                        while chunk := source.read(MIB):
                            copied += len(chunk); size += len(chunk)
                            if copied > config['max_uncompressed_bytes']:
                                raise ValueError('streamed_uncompressed_byte_cap')
                            h.update(chunk); target.write(chunk)
                    after = path.stat()
                    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or size != before.st_size:
                        raise ValueError('source_file_changed_during_copy:'+name)
                    if selected[name] is not None and h.hexdigest() != selected[name]:
                        raise ValueError('bound_source_file_changed:'+name)
                    inventory[name] = dict(sha256=h.hexdigest(), bytes=size)
            raw.flush(); os.fsync(raw.fileno())
        if copied != uncompressed:
            raise ValueError('source_inventory_size_changed')
        zip_sha = digest(incoming)
        result = dict(schema_version=1, status='complete', parent_notebook=config['parent_notebook'],
            parent_source_sha256=config['parent_source_sha256'], parent_manifest_sha256=config['parent_manifest_sha256'],
            parent_config_sha256=config['parent_config_sha256'], extractor_worker_sha256=config['worker_sha256'],
            extractor_builder_sha256=config['builder_sha256'], files=inventory,
            zip_filename='selected-output.zip', zip_sha256=zip_sha, zip_bytes=incoming.stat().st_size,
            uncompressed_bytes=copied, file_count=len(inventory), missing_optional=missing, case_status=case_status,
            parent_manifest_files_verified=len(config['parent_files']), finished_slots_planned=4*len(config['cases']),
            terminal_packets_copied=sum(bool(row['terminal_packet']) for row in case_status.values()),
            all_present_finish_files_including_partials_copied=True, no_optimizer=True, no_certification=True,
            no_gpu=True, no_competition_submission=True, seconds=time.monotonic()-started,
            attachment_identity='Exact manifest/config and all manifest-listed file hashes; mount suffix is not identity.',
            ancestry='These bytes were copied through a separate private CPU extractor. Its remote receipt must be retained alongside the parent receipt.')
        data=(json.dumps(result, indent=2, allow_nan=False)+'\n').encode()
        if len(data) > config['max_inventory_bytes'] or len(data)+incoming.stat().st_size > config['max_output_bytes']:
            raise ValueError('final_output_byte_cap')
        (out/'inventory.json.incoming').write_bytes(data)
        incoming.rename(out/'selected-output.zip')
        (out/'inventory.json.incoming').rename(out/'inventory.json')
        return result
    except BaseException:
        # A partial ZIP never masquerades as the published complete bundle.
        incoming.unlink(missing_ok=True)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--input-root',type=Path,default=Path('/kaggle/input'))
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();config=load_json(args.config)
    if digest(Path(__file__)) != config['worker_sha256']:
        raise ValueError('extractor_worker_changed')
    root=identify(args.input_root,config)
    result=extract(root,args.out,config)
    print(json.dumps({k:result[k] for k in ('status','file_count','zip_bytes','uncompressed_bytes','terminal_packets_copied','seconds')}),flush=True)


if __name__=='__main__':main()
