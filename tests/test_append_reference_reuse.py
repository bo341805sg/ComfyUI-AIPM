import ast,copy,pathlib,unittest
src=(pathlib.Path(__file__).resolve().parents[1] / 'nodes.py').read_text(encoding='utf-8')
tree=ast.parse(src)
helper=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='reuse_append_global_images')
scope={};exec(compile(ast.Module(body=[helper],type_ignores=[]),'helper','exec'),scope)
reuse=scope['reuse_append_global_images']
class ReuseTests(unittest.TestCase):
 def base(self):
  return {'global':{'reference_ids':['<Picture 1>']},'reference_profiles':[{'picture_id':'<Picture 1>','image_sha256':'aaa'},{'picture_id':'<Picture 3>','image_sha256':'bbb'}]}
 def test_same_global(self):
  base=self.base();before=copy.deepcopy(base)
  result=reuse([{'image_sha256':'AAA'}],base,'h3_ref2va')
  self.assertEqual(result[0]['picture_id'],'<Picture 1>');self.assertEqual(base,before)
 def test_new_and_reordered(self):
  result=reuse([{'image_sha256':'new'},{'image_sha256':'aaa'},{'image_sha256':'other'}],self.base(),'h3_ref2va')
  self.assertEqual([p['picture_id'] for p in result],['<Picture 2>','<Picture 1>','<Picture 4>'])
 def test_local_and_unknown_not_promoted(self):
  for p in [{'image_sha256':'bbb'},{'filename':'same.png'},{}]:
   self.assertEqual(reuse([p],self.base(),'h3_ref2va')[0]['picture_id'],'<Picture 2>')
 def test_keyframes_remain_distinct(self):
  result=reuse([{'image_sha256':'aaa'},{'image_sha256':'aaa'}],self.base(),'h3_keyframe')
  self.assertEqual([p['picture_id'] for p in result],['<Picture 2>','<Picture 4>'])
 def test_duplicate_global(self):
  result=reuse([{'image_sha256':'aaa'},{'image_sha256':'aaa'}],self.base(),'h3_ref2va')
  self.assertEqual([p['picture_id'] for p in result],['<Picture 1>','<Picture 1>'])
if __name__=='__main__':unittest.main()
