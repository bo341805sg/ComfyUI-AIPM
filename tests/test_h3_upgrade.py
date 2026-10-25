import ast,re,math,unittest,importlib.util
from pathlib import Path
R=Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('h3_candidate',R/'h3_contract.py');h3=importlib.util.module_from_spec(spec);spec.loader.exec_module(h3)
tree=ast.parse((R/'nodes.py').read_text(encoding='utf-8'));fn=next(x for x in ast.walk(tree) if isinstance(x,ast.FunctionDef) and x.name=='compile_h3_prompt');fn.decorator_list=[];env={'re':re};exec(compile(ast.Module(body=[fn],type_ignores=[]),'candidate-compiler','exec'),env)
class UpgradeTests(unittest.TestCase):
 def test_negative_list_is_not_positive_prompt(self):
  source='integrated_multimodal_description: [Shot 1] 人物拿起书。\noverall_soundscape: 室内底噪。\nnon_diegetic_music: N/A'
  result=env['compile_h3_prompt'](source,'柔和室内光线','畸形肢体、水印')
  self.assertIn('柔和室内光线',result);self.assertIn('人物拿起书',result);self.assertNotIn('畸形',result);self.assertNotIn('视觉限制',result)
 def test_no_dialogue_request_does_not_require_words(self):
  for idea in ['只有轻哼和惊呼，不安排对白','喘息和笑声，不需要台词','无对白，只有环境声']:
   self.assertFalse(h3.requires_dialogue(idea),idea)
  self.assertTrue(h3.requires_dialogue('她喘息后说话，创作一句对白'))
 def test_examples_are_executable_and_mode_scoped(self):
  for name in ['multi-person','continuation','vocal-performance']:
   raw=(R/'skills/aipm-minimax-h3-video/examples'/f'{name}.md').read_text(encoding='utf-8');variants=raw.split('\n<!-- REF -->\n')
   for i,mode in enumerate(['text_to_video','h3_ref2va']):
    text=variants[i];start=re.search(r'(?m)^(subject_definitions|integrated_multimodal_description):',text).start();prompt=text[start:];h3.validate_structure(prompt,mode,15);h3.validate_segment(prompt,[],['<Picture 1>','<Picture 2>','<Picture 3>'],mode)
 def test_examples_route_by_continuation_or_performance(self):
  root=R/'skills/aipm-minimax-h3-video'
  self.assertEqual(h3.selected_example(root,'h3_ref2va','哼声，不安排对白')[0],'vocal-performance')
  self.assertEqual(h3.selected_example(root,'h3_ref2va','motion_context continuation')[0],'continuation')
  self.assertEqual(h3.selected_example(root,'h3_ref2va','三人递给书本')[0],'multi-person')
if __name__ == '__main__': unittest.main()
