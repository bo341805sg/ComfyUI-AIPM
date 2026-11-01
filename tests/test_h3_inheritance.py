import unittest,importlib.util,ast
from pathlib import Path
R=Path(__file__).resolve().parents[1];sp=importlib.util.spec_from_file_location('h3_inherit',R/'h3_contract.py');h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h)
class InheritanceTests(unittest.TestCase):
 def test_empty_local_inherits_without_warning(self):
  self.assertEqual(h.inheritance_warnings('同一房间','无配乐',['','拿起盒子']),[])
 def test_local_music_override_reports_only_named_segment(self):
  w=h.inheritance_warnings('同一房间','无配乐',['','加入配乐',''])
  self.assertEqual(len(w),1);self.assertIn('第2段',w[0]);self.assertIn('其他段继承全局',w[0])
 def test_global_disagreement_is_visible(self):
  self.assertTrue(h.inheritance_warnings('加入背景音乐','无音乐',[]))
 def test_same_policy_and_ordinary_action_are_not_conflict(self):
  self.assertEqual(h.inheritance_warnings('无音乐','无配乐',['无音乐，打开盒子','关上盒子']),[])
 def test_plan_schema_can_return_warnings(self):
  t=ast.parse((R/'nodes.py').read_text(encoding='utf-8'));fn=next(n for n in ast.walk(t) if isinstance(n,ast.FunctionDef) and n.name=='timeline_plan_format');fn.decorator_list=[];env={"Any":object};exec(compile(ast.Module(body=[fn],type_ignores=[]),'schema','exec'),env)
  s=env['timeline_plan_format'](3)['json_schema']['schema'];self.assertIn('planning_warnings',s['required']);self.assertEqual(s['properties']['planning_warnings']['items']['type'],'string')
 def test_success_ui_does_not_overwrite_video_warnings(self):
  self.assertIn('} else if (!isVideo) setStatus(requestState.currentAction', (R/'web/aipm_ui.js').read_text(encoding='utf-8'))
if __name__=='__main__':unittest.main()
