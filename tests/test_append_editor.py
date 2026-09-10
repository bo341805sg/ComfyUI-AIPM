import ast,copy,json,pathlib,re,unittest
p=(pathlib.Path(__file__).resolve().parents[1] / 'nodes.py');tree=ast.parse(p.read_text(encoding='utf-8'))
scope={'copy':copy,'PromptAssistantError':ValueError}
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='reconcile_append_editor')
exec(compile(ast.Module(body=[fn],type_ignores=[]),'helper','exec'),scope)
class Tests(unittest.TestCase):
 def test_deleted_third_then_two(self):
  base={'segments':[{'segment_id':f'SEGMENT_{i:03d}'} for i in (1,2,3)],'generation_status':'interrupted','append_base_count':3}
  before=copy.deepcopy(base)
  timeline={'fps':24,'shots':[{'shot_id':f'SEGMENT_{i:03d}','start_frame':(i-1)*360,'end_frame':i*360,'local_prompt':'edited','metadata':{}} for i in (1,2)]}
  result=scope['reconcile_append_editor'](base,timeline)
  self.assertEqual(len(result['segments'])+2,4);self.assertEqual(base,before)
  self.assertEqual(result['segments'][1]['prompt'],'edited');self.assertEqual(result['generation_status'],'complete')
  self.assertNotIn('append_base_count',result)
 def test_sparse_ids(self):
  base_segments=[{'segment_id':'SEGMENT_001'},{'segment_id':'SEGMENT_003'}];operation='append'
  assignment=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='append_offset' for t in n.targets))
  offset=eval(compile(ast.Expression(assignment.value),'offset','eval'),{'base_segments':base_segments,'operation':operation,'re':re})
  self.assertEqual(offset,3)
 def test_empty(self):
  with self.assertRaises(ValueError):scope['reconcile_append_editor']({'segments':[]},{'shots':[]})
if __name__=='__main__':unittest.main()
