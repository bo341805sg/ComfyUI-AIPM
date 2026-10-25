import importlib.util,unittest,re,ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("h3_only",ROOT/"h3_contract.py");h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
def ref(body):
 return 'subject_definitions:\n<Subject 3>（角色名：张三）是 <Picture 2> 中的成年男性。\n<Subject 1>（角色名：李四）是 <Picture 5> 中的成年女性。\nsummary:\n[reference generation] 张三与李四交谈。\nretention_analysis:\n<Subject 3>: fully_preserved - 身份。\n<Subject 1>: fully_preserved - 身份。\ndetailed_description:\n[Shot 1] '+body+'\noverall_soundscape:\n室内底噪。\nnon_diegetic_music:\nN/A'
class SubjectOnlyTests(unittest.TestCase):
 def test_names_and_parenthesized_aliases_removed_from_prose(self):
  source=ref('<Subject 3>（张三）看向李四，张三点头。')
  actual=h.subject_only_prompt(source)
  self.assertNotIn('张三',actual);self.assertNotIn('李四',actual);self.assertNotIn('角色名',actual)
  self.assertIn('<Subject 3>看向<Subject 1>',actual)
  self.assertEqual(h.subject_only_prompt(actual),actual)
 def test_spoken_names_and_literal_visible_text_are_untouched(self):
  source=ref('<Subject 3>（张三） (S1) 说：<d>[Chinese]李四，叫我张三。</d> 门牌文字为 "张三工作室"；标牌为“李四”。')
  actual=h.subject_only_prompt(source)
  self.assertEqual(h.DIALOGUE.findall(actual),h.DIALOGUE.findall(source))
  self.assertIn('"张三工作室"',actual);self.assertIn('“李四”',actual)
  self.assertNotIn('（张三）',actual)
 def test_english_names_do_not_replace_longer_unrelated_words(self):
  actual=h.subject_only_prompt('John turns toward Johnson.',{'John':'<Subject 2>'})
  self.assertEqual(actual,'<Subject 2> turns toward Johnson.')
 def test_ambiguous_alias_is_not_guessed(self):
  source=ref('张三站立。').replace('角色名：李四','角色名：张三')
  self.assertIn('张三站立',h.subject_only_prompt(source))
 def test_internal_bindings_survive_clean_prompt(self):
  source=ref('张三点头。')
  bindings=h.resolved_role_bindings(source,[],[],{})
  clean=h.subject_only_prompt(source,bindings)
  self.assertNotIn('张三',clean)
  self.assertEqual(h.internal_role_bindings([{'source_prompt':clean,'role_bindings':bindings}]),{'张三':'<Subject 3>','李四':'<Subject 1>'})
 def test_unique_reference_role_link_can_supply_internal_mapping(self):
  source=ref('<Subject 3>站立。').replace('（角色名：张三）','').replace('（角色名：李四）','')
  profiles=[{'picture_id':'<Picture 2>','description':'张三，成年男性'},{'picture_id':'<Picture 5>','description':'李四，成年女性'}]
  self.assertEqual(h.resolved_role_bindings(source,profiles,['张三：你好。','李四：你好。']),{'张三':'<Subject 3>','李四':'<Subject 1>'})
  profiles[1]['description']='张三与李四'
  self.assertNotIn('张三',h.resolved_role_bindings(source,profiles,['张三：你好。']))
 def test_compiler_normalizes_global_and_local_but_leaves_base_mode(self):
  tree=ast.parse((ROOT/'nodes.py').read_text(encoding='utf-8'));fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='compile_h3_prompt');fn.decorator_list=[]
  env={'re':re,'_h3_contract':h};exec(compile(ast.Module(body=[fn],type_ignores=[]),'compiler','exec'),env)
  compiled=env['compile_h3_prompt'](ref('张三点头。'),'张三在客厅。','',{'张三':'<Subject 3>'})
  self.assertNotIn('张三',compiled)
  base='integrated_multimodal_description: [Shot 1] 张三点头。\noverall_soundscape: 风声。\nnon_diegetic_music: N/A'
  self.assertIn('张三',env['compile_h3_prompt'](base,'',''))
 def test_all_ref_examples_have_no_alias_markers(self):
  for path in (ROOT/'skills/aipm-minimax-h3-video/examples').glob('*.md'):
   raw=path.read_text(encoding='utf-8')
   if '<!-- REF -->' in raw:raw=raw.split('<!-- REF -->',1)[1]
   if 'subject_definitions:' in raw:
    self.assertEqual(h.subject_aliases(dict(h.sections(raw))['subject_definitions']),[],path.name)
    self.assertNotRegex(dict(h.sections(raw))['detailed_description'],r'<Subject\s+\d+>\s*[（(](?!S\d)',path.name)
if __name__=='__main__':unittest.main()
