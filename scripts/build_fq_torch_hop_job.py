"""Freeze a bounded persistent-hop pilot over the exact GPU-proved ALM payload."""
import argparse
import ast
import base64
import hashlib
import io
import json
import lzma
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / 'artifacts/fq-torch-alm-job-v2/search.py'
PARENT_SHA = '477fcf1001bca71020f16c2668951ec279a39c2176f55b7fa989d893e379059e'
CORE_SHA = 'c3ce3b8a99f55776bcb4727ad98dd100bad678593746fbdc828436699c03eb83'
CALIBRATION_SHA = '478da1518b67acc09dab8a32cf6d7deb13347e601816b49659612d87d3d512d9'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def parent_payload():
    source = PARENT.read_bytes()
    if sha(source) != PARENT_SHA:
        raise ValueError('The completed parent source changed')
    tree = ast.parse(source)
    constants = {}
    for node in tree.body[:2]:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            raise ValueError('Unexpected parent source header')
        constants[node.targets[0].id] = ast.literal_eval(node.value)
    manifest = constants['CONFIG']
    with zipfile.ZipFile(io.BytesIO(lzma.decompress(base64.b85decode(constants['PAYLOAD'])))) as archive:
        if set(archive.namelist()) != set(manifest['files']):
            raise ValueError('Parent payload names differ')
        files = {name: archive.read(name) for name in archive.namelist()}
    for name, data in files.items():
        if sha(data) != manifest['files'][name]:
            raise ValueError('Parent payload hash differs: ' + name)
    if sha(files['experiments/fq_torch_alm.py']) != CORE_SHA:
        raise ValueError('Reviewed numerical core differs')
    text = source.decode()
    first = text.index('\n')
    second = text.index('\n', first + 1)
    supervisor = text[second + 1:]
    old = "'experiments/fq_torch_alm_pilot.py'"
    if supervisor.count(old) != 1:
        raise ValueError('Parent supervisor entrypoint is ambiguous')
    supervisor = supervisor.replace(old, "'experiments/fq_torch_hop_pilot.py'")
    return files, manifest, supervisor


def build(args):
    if args.out.exists():
        raise ValueError('Use a fresh source-freeze directory')
    files, parent, supervisor = parent_payload()
    config_bytes = args.config.read_bytes()
    config = json.loads(config_bytes)
    if not 0 < config['search_seconds'] <= 180:
        raise ValueError('Search exceeds the authorized bound')
    for name in ('experiments/fq_torch_hop.py', 'experiments/fq_torch_hop_pilot.py'):
        data = (ROOT / name).read_bytes()
        compile(data, name, 'exec')
        files[name] = data
    files['hop-config.json'] = config_bytes
    calibration = (ROOT / 'artifacts/packer-hop-335-v1-calibration-v2.json').read_bytes()
    if sha(calibration) != CALIBRATION_SHA:
        raise ValueError('Acceptance calibration changed')
    files['provenance/native-hop-calibration.json'] = calibration
    proof_path = ROOT / 'artifacts/fq-torch-alm-results-v1/completion-proof.json'
    proof_bytes = proof_path.read_bytes()
    proof = json.loads(proof_bytes)
    if proof['source_sha256'] != PARENT_SHA or proof['status'] != 'COMPLETE' or not proof['controls_passed']:
        raise ValueError('Completed actual-GPU parent proof required')
    files['provenance/alm-completion-proof.json'] = proof_bytes
    pointer_bytes = (ROOT / 'artifacts/current-best-portfolio.json').read_bytes()
    pointer = json.loads(pointer_bytes)
    baseline = pointer['raw']
    report_bytes = Path(baseline['official_report']).read_bytes()
    report = json.loads(report_bytes)
    if (sha(report_bytes) != baseline['official_report_sha256'] or not report['valid']
            or report['sha256'] != baseline['sha256']):
        raise ValueError('Current portfolio proof differs')
    baseline335 = next(row for row in report['results'] if row['n'] == 335)
    files['provenance/portfolio-pointer.json'] = pointer_bytes
    for name, data in files.items():
        if name.endswith('.py'):
            compile(data, name, 'exec')
        if b'KGAT_' in data:
            raise ValueError('Credential-like text in source payload')
    manifest = dict(
        kind='Minimal persistent fixed-box smooth-ALM hop pilot',
        parent_source_sha256=PARENT_SHA,
        parent_payload_files=parent['files'],
        files={name: sha(data) for name, data in files.items()},
        builder_sha256=sha(Path(__file__).read_bytes()),
        configuration=config,
        baseline=baseline,
        baseline335=baseline335,
        baseline_pointer_sha256=sha(pointer_bytes),
        worker_seconds=300, whole_seconds=480, parent_alarm_seconds=475,
        server_timeout_seconds=600, no_submission=True, devices_used=1,
        source_commit=parent['source_commit'], license=parent['license'],
        unchanged_parent_payload=True,
        supervisor_delta='Only the child entrypoint changes; all process bounds are unchanged.')
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    encoded = base64.b85encode(lzma.compress(stream.getvalue(), preset=6)).decode()
    source = 'CONFIG=' + repr(manifest) + '\nPAYLOAD=' + repr(encoded) + '\n' + supervisor
    compile(source, 'search.py', 'exec')
    if len(source.encode()) >= 1_000_000:
        raise ValueError('Source exceeds Kaggle limit')
    args.out.mkdir(parents=True)
    (args.out / 'search.py').write_text(source)
    metadata = dict(id=args.slug, title=args.slug.split('/')[-1].replace('-', ' '),
                    code_file='search.py', language='python', kernel_type='script',
                    is_private=True, enable_gpu=True, enable_tpu=False, enable_internet=False,
                    dataset_sources=[], kernel_sources=[], competition_sources=[],
                    machine_shape='NvidiaTeslaT4')
    result = dict(source_sha256=sha(source.encode()), source_bytes=len(source.encode()),
                  payload_files=len(files), configuration=manifest, launched=False)
    for name, data in [('kernel-metadata.json', metadata), ('build_report.json', result)]:
        (args.out / name).write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'configuration'}, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--slug', default='sos54352/squares-fq-torch-persistent-hop')
    build(parser.parse_args())


if __name__ == '__main__':
    main()
