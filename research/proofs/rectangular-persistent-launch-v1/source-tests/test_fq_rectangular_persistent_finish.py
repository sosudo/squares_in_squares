import hashlib
import json
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'experiments'),str(ROOT/'scripts')]
import fq_rectangular_persistent_finish as finish


def fixture(root):
    case=dict(key='1_2_0',w=1,h=2,d=0,n=2,reference_f_lower='0.199999999',
              reference_f_upper='0.2',seed_keys=['a','b','c','d'],batch_size=64,binary_path='unused')
    (root/'family-config.json').write_text(json.dumps(case))
    design=[]
    for i in range(64):
        delta=finish.CUTS[i//16];f=float(case['reference_f_upper'])-delta
        design.append(dict(chain=i,source_key=case['seed_keys'][i%4],seed_group=i%4,delta=delta,
                           target_f=f,width=1+f,height=2+f,temperature=.3,stream=100+i,arm='rectangular'))
    (root/'chain-design.json').write_text(json.dumps(design))
    pose=np.array([[.5,.5,0.],[.5,1.5,0.]])
    arrays=dict(current_after=np.tile(pose,(64,1,1)),best_after=np.tile(pose,(64,1,1)),
                boxes=np.array([[r['width'],r['height']]for r in design]),
                next_energy=np.ones(64),best_energy_after=np.arange(64,dtype=float)/100)
    digests={name:hashlib.sha256(a.tobytes()).hexdigest()for name,a in arrays.items()}
    metadata=dict(round=16,design_sha256=finish.sha(root/'chain-design.json'),
                  family_config_sha256=finish.sha(root/'family-config.json'),array_sha256=digests,event='completed')
    np.savez_compressed(root/'head.npz',**arrays,metadata_json=np.frombuffer(json.dumps(metadata).encode(),dtype=np.uint8))
    np.savez_compressed(root/'final-current-best.npz',**arrays)
    recovery=dict(completed=True,status='recovered_head',state_origin=dict(kind='durable_head',path='head.npz',
                    sha256=finish.sha(root/'head.npz'),round=16,array_sha256=digests),
                  final_archive='final-current-best.npz',final_archive_sha256=finish.sha(root/'final-current-best.npz'),
                  design_sha256=metadata['design_sha256'],family_config_sha256=metadata['family_config_sha256'])
    (root/'recovery.json').write_text(json.dumps(recovery))
    return case,design,arrays


class RectangularFinisherTests(unittest.TestCase):
    def test_both_spans_not_bounding_square(self):
        # Bounding-square side2 equals h, yet the width violates w by1.
        p=np.array([[.5,.5,0.],[1.5,.5,0.]])
        proof=finish.rectangular_certificate(p,1,2)
        self.assertEqual(Decimal(proof['f_upper']),1)
        self.assertFalse(proof['fits_subunit_excess'])
        for row in proof['transports'].values():
            self.assertEqual(Decimal(row['width_upper']),2)
            self.assertEqual(Decimal(row['height_upper']),1)

    def test_rotated_unit_bounds_and_translation(self):
        p=np.array([[1.,2.,np.pi/4]])
        a=finish.rectangular_certificate(p,1,1)
        b=finish.rectangular_certificate(p+np.array([4.,-3.,0.]),1,1)
        self.assertLess(abs(float(a['f_upper'])-(np.sqrt(2)-1)),1e-14)
        self.assertLess(abs(float(a['f_upper'])-float(b['f_upper'])),1e-14)

    def test_d2_row_permutation_and_reflection(self):
        p=np.array([[.4,.6,.13],[.8,1.6,.2],[1.7,2.8,-.3]])
        box=np.array([2.,4.]);other=p[::-1].copy();other[:,0]=box[0]-other[:,0];other[:,2]*=-1
        self.assertEqual(finish.histogram_distance(finish.histogram_orbit(p,box),finish.histogram_orbit(other,box)),0.)

    def test_fixed_cut_slots_duplicate_exclusion(self):
        with tempfile.TemporaryDirectory()as d:
            case,design,arrays=fixture(Path(d))
            slots=finish.select_slots(design,arrays['best_after'],arrays['best_energy_after'],arrays['boxes'])
            self.assertEqual(len(slots),8)
            self.assertEqual([r['chain']for r in slots[::2]],[0,16,32,48])
            self.assertTrue(all(r['chain'] is None for r in slots[1::2]))
            arrays['best_after'][1,0,0]+=.03
            slots=finish.select_slots(design,arrays['best_after'],arrays['best_energy_after'],arrays['boxes'])
            self.assertEqual(slots[1]['chain'],1)
            self.assertTrue(slots[1]['fallback_next_lowest_energy'])

    def test_recovery_exact_byte_binding_and_tamper(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);case,design,arrays=fixture(root)
            loaded,_,_=finish.load_committed(root,case)
            self.assertTrue(np.array_equal(loaded['boxes'],arrays['boxes']))
            arrays['best_after'][0,0,0]=np.nextafter(arrays['best_after'][0,0,0],np.inf)
            np.savez_compressed(root/'final-current-best.npz',**arrays)
            recovery=json.loads((root/'recovery.json').read_text());recovery['final_archive_sha256']=finish.sha(root/'final-current-best.npz')
            (root/'recovery.json').write_text(json.dumps(recovery))
            with self.assertRaisesRegex(ValueError,'not_exact_committed'):
                finish.load_committed(root,case)

    def test_state_origin_cannot_escape_family(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);case,_,_=fixture(root)
            recovery=json.loads((root/'recovery.json').read_text());recovery['state_origin']['path']='../foreign.npz'
            (root/'recovery.json').write_text(json.dumps(recovery))
            with self.assertRaisesRegex(ValueError,'outside_family'):
                finish.load_committed(root,case)

    def test_native_rectangle_offsets_and_preserve_full_cert_on_rect_timeout(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);case,design,arrays=fixture(root)
            slot=dict(slot=0,kind='lowest_best_energy',delta=.002,chain=0,design=design[0])
            p=np.array([[.5,.5,0.],[.5,1.50000001,0.]])
            calls=[]
            def native(command,base,timeout):
                calls.append(command)
                base.with_suffix('.out').write_text('2 1.00000001\n.5 .5 0\n.5 1.50000001 0\n')
                return dict(native_status='returned',returncode=0)
            certificate=dict(valid=True,shared_official_gate=dict(raw_side='2.00000001',roundtrip_side='2.00000001'),
                ordinary_pandas_official_side='2.00000001',independent_raw=dict(n=2,side_upper='2.00000001'),
                independent_roundtrip=dict(n=2,side_upper='2.00000001'))
            with patch.object(finish.terminal,'_recorded_native',side_effect=native), \
                 patch.object(finish.terminal,'full_certificate',return_value=certificate), \
                 patch.object(finish,'rectangular_certificate',side_effect=finish.terminal.CertificateDeadline):
                record,q=finish._finish_slot((str(root),slot,p,case,'unused',time.monotonic()+70))
            self.assertIsNotNone(q)
            self.assertEqual(record['status'],'certified_rectangle_timeout')
            self.assertFalse(record['usable_rectangular_donor'])
            self.assertTrue(Path(record['certified_archive']).exists())
            command=calls[0]
            self.assertEqual(command[command.index('--rect-dx')+1],'0')
            self.assertEqual(command[command.index('--rect-dy')+1],'1')
            self.assertEqual(command[command.index('--seed')+1],'9710000')
            saved=json.loads((root/'slot-00-lowest_best_energy.certificate.json').read_text())
            self.assertEqual(saved['status'],'certified_rectangle_timeout')

    def test_timeout_at_first_certificate_publication_preserves_valid_pose(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);case,design,_=fixture(root)
            slot=dict(slot=0,kind='lowest_best_energy',delta=.002,chain=0,design=design[0])
            p=np.array([[.5,.5,0.],[.5,1.50000001,0.]])
            def native(command,base,timeout):
                base.with_suffix('.out').write_text('2 1.00000001\n.5 .5 0\n.5 1.50000001 0\n')
                return dict(native_status='returned',returncode=0)
            certificate=dict(valid=True,shared_official_gate=dict(raw_side='2.00000001',roundtrip_side='2.00000001'),
                ordinary_pandas_official_side='2.00000001',independent_raw=dict(n=2,side_upper='2.00000001'),
                independent_roundtrip=dict(n=2,side_upper='2.00000001'))
            original_json=finish.terminal.atomic_json;raised=[]
            def publish(path,value):
                if str(path).endswith('.certificate.json')and not raised:
                    raised.append(True);raise finish.terminal.CertificateDeadline()
                return original_json(path,value)
            with patch.object(finish.terminal,'_recorded_native',side_effect=native), \
                 patch.object(finish.terminal,'full_certificate',return_value=certificate), \
                 patch.object(finish.terminal,'atomic_json',side_effect=publish):
                record,q=finish._finish_slot((str(root),slot,p,case,'unused',time.monotonic()+70))
            self.assertTrue(raised)
            self.assertIsNotNone(q)
            self.assertEqual(record['status'],'certified_rectangle_timeout')
            self.assertEqual(finish.sha(record['certified_archive']),record['certified_archive_sha256'])
            saved=json.loads((root/'slot-00-lowest_best_energy.certificate.json').read_text())
            self.assertTrue(saved['certificate']['valid'])
            self.assertEqual(saved['geometry_sha256'],finish.terminal.geometry_sha(q))


if __name__=='__main__':unittest.main()
