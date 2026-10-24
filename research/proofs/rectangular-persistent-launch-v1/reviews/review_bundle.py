import hashlib,json,pathlib,sys
R=pathlib.Path.cwd();sys.path.insert(0,str(R/'scripts'))
from build_fq_fused_hop_job import unpack
J=R/'artifacts/rectangular-persistent-job-v1';O=R/'artifacts/rectangular-runtime-independent-review-v1'
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest();shab=lambda b:hashlib.sha256(b).hexdigest()
SOURCE='fb878006be0daa5bc1c6ce622c3dc58bf39f2b3171d45704f56260368e1df7b9'
source,config,files=unpack(J/'search.py',SOURCE,'xz85')
_,old,parent=unpack(R/'artifacts/fq-cold-transfer-job-v1/search.py','34ea1497cf6e24560eff8da939b3288b08029519640ba1eb8907acc1353d1292','xz85')
assert len(files)==155 and len(source)==830379,'bundle size'
removed={'cold-config.json','cold-inputs.npz','cold-input-proof.json'}
assert set(config['replaced_inactive_root_data'])==removed,'removed inventory'
assert all(files[name]==data for name,data in parent.items()if name not in removed),'unchanged parent'
for name,want in {'experiments/fq_rectangular_persistent_pilot.py':'fa3d0f34433e837d282a470fadf2aefbbaef5a20ee596fd1c7d6edf9334f8aa8','experiments/fq_rectangular_persistent_search.py':'10fee0016db9cf81347d2bce92d0052c0fcf80450f7149ead13f6cfbc4e49a1a','experiments/fq_rectangular_persistent_finish.py':'47d391ec9541f70313451c55036702a21c6a8562dc75a75f7ba09d67a50d75b9'}.items():
 assert shab(files[name])==want==sha(R/name)==config['source_manifest'][name],name
protocol=json.loads(files['rectangular-protocol.json']);assert protocol==config['configuration'],'embedded protocol'
assert protocol['search_seconds']==3000 and protocol['whole_seconds']==7200 and protocol['server_seconds']==7800,'duration'
assert sum(protocol['phase_seconds'].values())*2==6786<protocol['parent_seconds']==7100,'phase sum'
assert protocol['input_archive_sha256']=='1c2d92e19f8cd35d275122b8ed5746aba03c0ed113d4650a34d19447fbb87751','input'
assert protocol['native_reference_results_sha256']==sha(R/'artifacts/fq-rectangular-reference-controls-v1/results.json'),'native control'
fixture=json.loads(files['provenance/rectangular-private-fixture-proof.json'])
assert fixture['status']=='complete' and fixture['is_private'] and fixture['version']==1,'fixture version'
assert config['fixture_transport']['ref']==fixture['ref']+'/1','fixture ref'
assert fixture['downloaded_files']=={k:v['sha256']for k,v in config['fixture_files'].items()} and len(config['fixture_files'])==125,'fixture inventory'
metadata=json.loads((J/'kernel-metadata.json').read_text())
assert metadata['is_private'] and metadata['enable_gpu'] and not metadata['enable_internet'],'metadata'
assert metadata['dataset_sources']==[config['fixture_transport']['ref']],'attachment'
smoke=json.loads((J/'local_import_review.json').read_text())
assert smoke['source_sha256']==SOURCE and smoke['payload_files']==155 and smoke['fixture_members']==125,'smoke binding'
assert smoke['typed_count_design_and_seed_checks'] and smoke['exact_prepare_without_cuda'] and smoke['exact_payload_and_fixture_hashes_verified'] and not smoke['actual_cuda_run'] and not smoke['native_execution'],'smoke scope'
body=source.decode().split('\n',2)[2]
assert all(t in body for t in ['started+7100.','worker.wait(timeout=max(.01,started+7160.-time.monotonic()))','signal.alarm(7195)','stop_owned_tree(worker)']),'supervisor'
receipts={name:dict(path=path,sha256=sha(R/path))for name,path in {
 'inputs':'artifacts/rectangular-inputs-independent-review-v1/review.json',
 'native_finisher':'artifacts/rectangular-finisher-independent-review-v1/review.json',
 'four_original_controls':'artifacts/rectangular-reference-independent-review-v1/review.json',
 'old_wall_fixture_failure':'artifacts/rectangular-wall-control-independent-review-v1/review.json',
 'new_wall_fixture_owner_check':'artifacts/rectangular-runtime-local-review-v1/wall-fixtures.json'}.items()}
tests={str(p):sha(R/p)for p in ['tests/test_fq_rectangular_persistent_search.py','tests/test_fq_rectangular_persistent_controller.py','tests/test_fq_rectangular_persistent_finish.py']}
r=dict(status='GREEN_FOR_MANDATORY_DEVICE_GATED_LAUNCH',source_sha256=SOURCE,source_bytes=len(source),payload_files=155,preserved_parent_files=len(parent)-3,fixture_files=125,configuration_sha256=shab(files['rectangular-protocol.json']),source_manifest=config['source_manifest'],kernel_metadata_sha256=sha(J/'kernel-metadata.json'),isolated_import_review_sha256=sha(J/'local_import_review.json'),review_source_sha256=sha(__file__),tests=dict(passed=15,seconds=.674,source_hashes=tests,actual_nested_process_deadline_controls=True,no_optimizer=True),prior_reviews=receipts,
 checks=[
 'Whole-unit92/146/154/181 counts;4seed groups x4cuts x4independent streams. FP64 physical acceptance sums unordered SAT pairs once plus separateW/H walls; targets/energies never mixed between rectangles.',
 'Quench imports unchanged reviewed symmetric-tie FP64 CUDA with --fmad=false and explicit proposal copy. Each family requires actualN, lastunit, hash-cell overlap, known positive fullrectangle repair/fullcertification, independentW/H oracle, actualB64 includingchain63, unchangedproposal and isolatedH-wall analytical gradient controls.',
 'Corrected wall fixture places lowerfaceH+.03, eliminating pair-force cancellation. Failed old fixture preserved separately.',
 'Atomic current/BEST head commits before scalar publication/in-memory advancement. Every scalar decision/RNG identity retained; full transitions sampled32/phase/zero/terminal with explicit storage skips. No full-history replay claim.',
 'Decision-time cooling at75% of initialized3000s search epoch; tailguard+20s finalreserve. Explicit output ceilings can end search early and are reported; no guaranteed3000s optimization claim.',
 'Two sequential families/GPU,6786s conservative phases within7100parent;7160worker/7195alarm/7200whole/7800server. RegisteredPID/starttime cleanup freezes/kills across setsid/reparenting and verifies gone/zombie before inventories; real tests preserve unrelated process.',
 'Fixed8 nativeBEST slots/family,2workers60+8, actualrectangular offsets, allvalidworse retained. Comparisonlower=min(original lower, matchedcontrol lower); originalupper stillsets searchboxes. Full unit certificate and bothspan transports required for donors; no fullscore inference.',
 'All147 retained parent numerical/native/license files byte-identical;3inactive fixtures removed. Privateversion1 full125-member binding and whole-inventory mount selection prevent duplicateNPZ ambiguity; isolatedprepare/import checks pass.'
 ],scope='Independent source/math/protocol/bundle review plus15 CPU-only tests. No CUDA/optimizer/newgeometrycert/remote launch/canonical mutation/submission. Mandatory actualGPU gates remain before each search.')
(O/'review.json').write_text(json.dumps(r,indent=2)+'\n');(J/'independent_runtime_review.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(dict(status=r['status'],sha256=sha(O/'review.json'),source=SOURCE)))
