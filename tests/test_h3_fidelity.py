import unittest,importlib.util,ast,copy
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location('h3_fidelity',R/'h3_contract.py');h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h)
def base(body):return 'integrated_multimodal_description: [Shot 1] '+body+'\noverall_soundscape: Room tone.\nnon_diegetic_music: N/A'
class FidelityTests(unittest.TestCase):
 def test_raw_quoted_speaker_requires_dialogue_tags(self):
  for line in ['(S1) "Hello."','(S2): “Hello.”','(S1,S2) "Hello."']:
   with self.assertRaises(h.ContractError):h.validate_structure(base(line),'text_to_video',15)
 def test_tagged_speech_allows_quoted_content(self):
  h.validate_structure(base('(S1) <d>[English]She said "hello".</d>'),'text_to_video',15)
 def test_nonverbal_speaker_does_not_need_dialogue(self):
  h.validate_structure(base('(S1) laughs softly.'),'text_to_video',15)
 def test_literal_text_without_speaker_is_not_dialogue(self):
  h.validate_structure(base('A sign reads "Hello".'),'text_to_video',15)
 def test_truncated_complete_looking_text_is_not_success(self):
  tree=ast.parse((R/'nodes.py').read_text(encoding='utf-8'));fn=next(x for x in ast.walk(tree) if isinstance(x,ast.FunctionDef) and x.name=='request_text');fn.decorator_list=[]
  env={'copy':copy,'Any':object,'PromptAssistantError':RuntimeError,'_emit_aipm_stage':lambda *a:None};exec(compile(ast.Module(body=[fn],type_ignores=[]),'request-text','exec'),env)
  class Client:
   @staticmethod
   def request(*a):return {'choices':[{'finish_reason':'length','message':{'content':'looks complete'}}]}
   @staticmethod
   def content(r):return r['choices'][0]['message']['content']
  with self.assertRaisesRegex(RuntimeError,'截断'):env['request_text'](Client,'unused',{'messages':[]},'test',attempts=1)
if __name__=='__main__':unittest.main()
