import base64,hashlib,json,tempfile,unittest,zlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import read_rectangular_live as reader

class LivePayloadTests(unittest.TestCase):
 def event(self):
  files={}
  for name in reader.FILES:
   data=('exact:'+name).encode();files[name]=dict(bytes=len(data),sha256=reader.sha(data),encoding='zlib1-base85',data=base64.b85encode(zlib.compress(data,1)).decode())
  return dict(stage='rectangular_family_payload',family='5_17_7',input_archive_sha256='input',protocol_sha256='protocol',files=files)
 def test_arbitrary_sse_chunk_boundaries_and_exact_unpack(self):
  event=self.event();line=json.dumps(event,sort_keys=True)+'\n';sizes=[1,11,137,200,509,len(line)]
  chunks=[];start=0
  for end in sizes:
   chunks.append('data: '+json.dumps(dict(stream_name='stdout',data=line[start:end])));start=end
  events,counts=reader.decode(chunks);self.assertEqual(len(events),1);self.assertEqual(events[0]['event'],event)
  with tempfile.TemporaryDirectory()as temp:
   out=Path(temp);receipt=reader.unpack_event(events[0],out,dict(inputs_sha256='input',files={'rectangular-protocol.json':'protocol'}))
   self.assertFalse(receipt['geometry_admitted'])
   for name,r in event['files'].items():self.assertEqual(reader.sha((out/'families/5_17_7'/name).read_bytes()),r['sha256'])
 def test_hash_or_trailing_compressed_data_rejected(self):
  for mutation in('hash','trailing'):
   event=self.event();record=event['files']['family-config.json']
   if mutation=='hash':record['sha256']='0'*64
   else:record['data']=base64.b85encode(base64.b85decode(record['data'])+b'extra').decode()
   with self.subTest(mutation=mutation),tempfile.TemporaryDirectory()as temp:
    with self.assertRaises(ValueError):reader.unpack_event(dict(event=event,line_sha256='line'),Path(temp),dict(inputs_sha256='input',files={'rectangular-protocol.json':'protocol'}))
    self.assertFalse((Path(temp)/'families').exists())
if __name__=='__main__':unittest.main()
