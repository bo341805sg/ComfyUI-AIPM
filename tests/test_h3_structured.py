import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('contract',Path(__file__).resolve().parents[1]/'h3_contract.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
class StructuredShotsTests(unittest.TestCase):
 def data(self):
  return {'shots':[{'start_seconds':0,'description':'人物继续行走。'}],'overall_soundscape':'脚步声。','non_diegetic_music':'N/A'}
 def test_numbering_is_local_and_compiled(self):
  d=self.data();d['shots'].append({'start_seconds':2.25,'description':'切向门口。'})
  text=h.compile_segment(d,'text_to_video',5)
  self.assertIn('[Shot 1]',text);self.assertIn('[Shot 2] At 00:02.250,',text)
 def test_single_shot_needs_no_model_label(self):
  self.assertEqual(h.compile_segment(self.data(),'text_to_video',5).count('[Shot '),1)
 def test_bad_times_remain_rejected(self):
  for t in [0,-1,6,float('nan')]:
   d=self.data();d['shots'].append({'start_seconds':t,'description':'切镜'})
   with self.assertRaises(h.ContractError):h.compile_segment(d,'text_to_video',5)
 def test_missing_body_is_not_fabricated(self):
  d=self.data();d['shots']=[]
  with self.assertRaises(h.ContractError):h.compile_segment(d,'text_to_video',5)
 def test_ref_mode_preserves_fields_and_dialogue(self):
  d=self.data();d.update(subject_definitions='<Subject 1> 来自 <Picture 1>。',summary='参考生成。',retention_analysis='保留身份。')
  d['shots'][0]['description']='人物 (S1) 说：<d>[Chinese]走吧。</d>'
  text=h.compile_segment(d,'h3_ref2va',5)
  self.assertIn('<d>[Chinese]走吧。</d>',text)
if __name__=='__main__':unittest.main()
