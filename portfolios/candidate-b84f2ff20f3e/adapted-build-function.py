def build(args):
    if args.out.exists():raise ValueError('Use a fresh incremental export directory')
    parent,parent_report,parent_proofs=validate_proofs(args.parent,args.parent_report,args.parent_transport)
    target,target_report,target_proofs=validate_proofs(args.target,args.target_report,args.target_transport)
    completion_raw=(args.parent_export_job/'completion-proof.json').read_bytes();completion=json.loads(completion_raw)
    if not (sha(parent)==PARENT_SHA and completion['output_sha256']==PARENT_SHA and
            completion['ref']+'/'+str(completion['version'])==PARENT_REF and completion['version']==2 and
            completion['output_file']=='submission.csv' and completion['status']=='complete' and completion['is_private']):
        raise ValueError('Exact previously verified private parent export required')
    ns=runtime_namespace();old=ns['_validate_csv'](parent);new=ns['_validate_csv'](target)
    changed={i-1 for i,(a,b)in enumerate(zip(old,new)) if i and a!=b}
    patch_raw=json.dumps({'rows':[[rid,new[rid+1].decode('ascii')]for rid in sorted(changed)]},separators=(',',':')).encode()
    compressed=lzma.compress(patch_raw,preset=6);encoded=base64.b64encode(compressed).decode()
    export_raw=(args.parent_export_job/'export_manifest.json').read_bytes();parent_export=json.loads(export_raw)
    if parent_export['csv_sha256']!=PARENT_SHA:raise ValueError('Parent export provenance differs')
    manifest=dict(format_version=1,kind='exact_safe_csv_row_patch',
        parent_notebook=PARENT_REF,parent_output_file='submission.csv',parent_csv_sha256=sha(parent),parent_csv_bytes=len(parent),
        csv_sha256=sha(target),csv_bytes=len(target),rows=500500,puzzles=1000,
        schema=['id','n','square_id','x','y','angle'],line_ending='CRLF',
        patch_sha256=sha(patch_raw),patch_bytes=len(patch_raw),patch_compressed_sha256=sha(compressed),
        patch_compressed_bytes=len(compressed),changed_rows=len(changed),unchanged_rows=500500-len(changed),
        changed_puzzles=sorted({int(new[rid+1].split(b',')[1])for rid in changed}),
        changed_parent_rows_sha256=ns['_line_digest'](old,changed,True),
        changed_target_rows_sha256=ns['_line_digest'](new,changed,True),
        unchanged_rows_sha256=ns['_line_digest'](old,changed,False),
        official_score=target_report['score'],parent_official_score=parent_report['score'],metric_sha256=METRIC_SHA,
        parent_proofs=parent_proofs,target_proofs=target_proofs,parent_remote_completion_sha256=sha(completion_raw),
        parent_export_manifest_sha256=sha(export_raw),transport_scaling_applied=False,
        source_notices=parent_export.get('source_notices'),
        inherited_sources=[{k:v for k,v in row.items()if k!='puzzles'}for row in parent_export.get('sources',[])],
        inherited_certificates=parent_export.get('certificates',[]),
        local_geometry_provenance='Existing target portfolio proofs and repository notices; exporter makes no new mathematical discovery.',
        runtime_sha256=sha(RUNTIME.encode()),certificate_policy='Reuse only exact previously certified parent/target CSV bytes.')
    additional_path=getattr(args,'additional_provenance',None)
    if additional_path is not None:
        additional_raw=Path(additional_path).read_bytes()
        manifest['additional_source_provenance']=json.loads(additional_raw)
        manifest['additional_source_provenance_sha256']=sha(additional_raw)
    if ns['_line_digest'](new,changed,False)!=manifest['unchanged_rows_sha256']:
        raise ValueError('Unchanged byte sequence differs')
    rebuilt=ns['apply_safe_row_patch'](parent,encoded,manifest)
    if rebuilt!=target:raise ValueError('Local exact-byte reconstruction failed')
    manifest_encoding={'encoding':'literal_python_mapping'}
    if getattr(args,'compress_manifest',False):
        manifest_raw=json.dumps(manifest,separators=(',',':'),ensure_ascii=False).encode('utf8')
        manifest_compressed=lzma.compress(manifest_raw,preset=6)
        manifest_encoded=base64.b64encode(manifest_compressed).decode()
        parameters=(manifest_encoded,len(manifest_raw),sha(manifest_raw),sha(manifest_compressed))
        check={};exec(compile(COMPRESSED_MANIFEST_RUNTIME,'<manifest-codec>','exec'),check)
        if check['_decode_embedded_manifest'](*parameters)!=manifest:
            raise ValueError('Embedded manifest exact reconstruction failed')
        loader=COMPRESSED_MANIFEST_RUNTIME+'\nINCREMENTAL_MANIFEST = _decode_embedded_manifest(*'+repr(parameters)+')\n'
        manifest_encoding=dict(encoding='exact_json_lzma_base64',raw_bytes=len(manifest_raw),
            raw_sha256=sha(manifest_raw),compressed_bytes=len(manifest_compressed),
            compressed_sha256=sha(manifest_compressed),decoder_sha256=sha(COMPRESSED_MANIFEST_RUNTIME.encode()))
    else:
        loader='INCREMENTAL_MANIFEST = '+repr(manifest)+'\n'
    loader+='INCREMENTAL_PATCH = '+repr(encoded)+'\n'+RUNTIME
    source=loader+ENTRYPOINT;compile(source,'export.py','exec')
    if len(source.encode())>=1_000_000:raise ValueError('Incremental source exceeds Kaggle1MB')
    args.out.mkdir(parents=True)
    metadata=notebook_metadata(args.slug)
    report=dict(script_sha256=sha(source.encode()),script_bytes=len(source.encode()),
        parent_csv_sha256=sha(parent),target_csv_sha256=sha(target),changed_rows=len(changed),
        changed_puzzles=manifest['changed_puzzles'],patch_compressed_bytes=len(compressed),
        local_exact_byte_reconstruction=True,transport_scaling_applied=False,launched=False,
        manifest_encoding=manifest_encoding)
    for name,value in [('export_manifest.json',manifest),('kernel-metadata.json',metadata),('build_report.json',report)]:
        (args.out/name).write_text(json.dumps(value,indent=2)+'\n')
    (args.out/'incremental_loader.py').write_text(loader);(args.out/'export.py').write_text(source)
    print(json.dumps(report,indent=2));return report
