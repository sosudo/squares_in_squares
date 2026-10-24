"""Small metadata/byte fixtures; no optimizer, metric or GPU execution."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
import fq_sustained_output_extract as extract


def sha(data):return hashlib.sha256(data).hexdigest()
def put(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
def js(value):return (json.dumps(value,indent=2)+'\n').encode()


class OutputExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name);self.parent=self.folder/'mount'/'random-unpinned-suffix'
        policy={'cases':{'412':{'n':412},'544':{'n':544}}}
        files={'sustained-config.json':js(policy),'experiments/unchanged.py':b'# source\n',
               'bin/fq':b'exact native bytes','vendor/fq/NOTICE':b'upstream notice\n',
               'controls/full-certified.json':b'{"valid":true}\n'}
        for name,data in files.items():put(self.parent/name,data)
        manifest={'configuration':policy,'files':{name:sha(data) for name,data in files.items()}}
        put(self.parent/'job_manifest.json',js(manifest))
        self.config=dict(parent_notebook='owner/exact/1',parent_source_sha256='1'*64,
            parent_manifest_sha256=sha(js(manifest)),parent_config_sha256=sha(js(policy)),
            parent_files=manifest['files'],cases=[412,544],worker_sha256='2'*64,builder_sha256='3'*64,
            max_files=100,max_uncompressed_bytes=1024**2,max_zip_bytes=1024**2,
            max_inventory_bytes=1024**2,max_output_bytes=2*1024**2)
        case=self.parent/'case-412'
        old=b'UNREAD OLD PACKET';latest=b'EXACT COMMITTED PACKET';pending=b'INCOMPLETE EXCLUDED'
        for number,data in [(0,old),(1,latest),(2,pending)]:put(case/f'raw-hop/packet-{number:04d}.npz',data)
        index={'packets':[
            dict(path='raw-hop/packet-0000.npz',sha256='invalid-old-pin-is-never-read',bytes=len(old),status='completed'),
            dict(path='/kaggle/working/case-412/raw-hop/packet-0001.npz',sha256=sha(latest),bytes=len(latest),status='completed'),
            dict(path='raw-hop/packet-0002.npz',sha256=sha(pending),bytes=len(pending),status='pending')]}
        put(case/'raw-index.json',js(index));put(case/'final-current-best.npz',b'FINAL')
        put(case/'preflight/preflight_entries/partial-control.npz',b'CERTIFIED CONTROL')
        put(case/'preflight/failed-preflight.log',b'failed control detail')
        put(case/'finish/slot-00-cold-0.out',b'EXACT NATIVE DECIMAL OUTPUT')
        put(case/'finish/slot-00-cold-0.raw.npz',b'RAW')
        put(case/'finish/slot-01-selected.npz',b'SELECTED BEFORE TIMEOUT')
        put(case/'finish/slot-01-cold.incoming',b'INTERRUPTED PARTIAL')
        put(case/'finish/results.json',js([dict(slot=0,status='certified')]))
        put(case/'zero-energy-index.json',js([{'raw':'zero-energy/large.npz'}]))
        put(case/'zero-energy/large.npz',b'EXCLUDED OPTIONAL')
        put(self.parent/'queue-0.json',js({'412':{'status':'bounded_partial'}}))
        self.out=self.folder/'result'

    def test_exact_whitelist_terminal_only_and_all_partial_finish_files(self):
        root=extract.identify(self.folder/'mount',self.config)
        self.assertEqual(root,self.parent)
        result=extract.extract(root,self.out,self.config)
        with zipfile.ZipFile(self.out/'selected-output.zip') as archive:
            names=set(archive.namelist())
            self.assertIn('case-412/raw-hop/packet-0001.npz',names)
            self.assertNotIn('case-412/raw-hop/packet-0000.npz',names)
            self.assertNotIn('case-412/raw-hop/packet-0002.npz',names)
            self.assertNotIn('case-412/zero-energy/large.npz',names)
            self.assertIn('case-412/zero-energy-index.json',names)
            self.assertIn('case-412/finish/slot-01-cold.incoming',names)
            self.assertIn('case-412/preflight/preflight_entries/partial-control.npz',names)
            for name in names:
                self.assertEqual(archive.read(name),(self.parent/name).read_bytes())
                self.assertEqual(sha(archive.read(name)),result['files'][name]['sha256'])
        self.assertEqual(extract.digest(self.out/'selected-output.zip'),result['zip_sha256'])
        self.assertEqual(result['terminal_packets_copied'],1)
        self.assertEqual(result['finished_slots_planned'],8)
        self.assertEqual(result['case_status']['412']['finish_slots']['1']['status'],'files_without_result')
        self.assertEqual(result['case_status']['544']['finish_slots']['3']['status'],'no_slot_files')
        self.assertIn('case-544/raw-index.json',result['missing_optional'])

    def test_source_and_terminal_hashes_fail_closed_without_published_archive(self):
        for name in ['vendor/fq/NOTICE','case-412/raw-hop/packet-0001.npz']:
            path=self.parent/name;data=path.read_bytes();path.write_bytes(data+b'CHANGED')
            with self.assertRaisesRegex(ValueError,'(bound_source_file_changed|terminal_packet_size_changed)'):
                extract.extract(self.parent,self.out,self.config)
            self.assertFalse((self.out/'selected-output.zip').exists())
            self.assertFalse((self.out/'inventory.json').exists())
            self.assertFalse((self.out/'selected-output.zip.incoming').exists())
            path.write_bytes(data)

    def test_exact_parent_identity_duplicate_mount_and_path_escape_rejected(self):
        changed=dict(self.config,parent_config_sha256='0'*64)
        with self.assertRaisesRegex(ValueError,'config_changed'):extract.identify(self.folder/'mount',changed)
        index=self.parent/'case-412/raw-index.json';data=json.loads(index.read_bytes())
        data['packets'][1]['path']='../../outside.npz';index.write_bytes(js(data))
        with self.assertRaisesRegex(ValueError,'packet_path'):extract.extract(self.parent,self.out,self.config)
        with self.assertRaisesRegex(ValueError,'unsafe_relative_path'):extract.relative_name('../escape')

    def test_symlinks_and_size_caps_fail_closed(self):
        link=self.parent/'case-412/finish/link';link.symlink_to(self.parent/'bin/fq')
        with self.assertRaisesRegex(ValueError,'symlink_forbidden'):extract.extract(self.parent,self.out,self.config)
        link.unlink()
        with self.assertRaisesRegex(ValueError,'uncompressed_byte_cap'):
            extract.extract(self.parent,self.out,dict(self.config,max_uncompressed_bytes=20))
        with self.assertRaisesRegex(ValueError,'zip_byte_cap'):
            extract.extract(self.parent,self.out,dict(self.config,max_zip_bytes=20))
        self.assertFalse((self.out/'selected-output.zip').exists())

    def test_interruption_cannot_publish_partial_bundle(self):
        original=extract.CappedOutput.write;calls=0
        def interrupted(stream,data):
            nonlocal calls
            calls+=1
            if calls>=4:raise KeyboardInterrupt('forced interruption')
            return original(stream,data)
        with patch.object(extract.CappedOutput,'write',interrupted):
            with self.assertRaises(KeyboardInterrupt):extract.extract(self.parent,self.out,self.config)
        self.assertFalse((self.out/'inventory.json').exists())
        self.assertFalse((self.out/'selected-output.zip').exists())
        self.assertFalse((self.out/'selected-output.zip.incoming').exists())


if __name__=='__main__':unittest.main()
