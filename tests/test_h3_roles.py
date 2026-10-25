import importlib.util,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("h3_roles",ROOT/"h3_contract.py");h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
def prompt(definitions,body):
 return f"subject_definitions:\n{definitions}\nsummary:\n[reference generation] 场景。\nretention_analysis:\n<Subject 3> (appears in [Shot 1]): fully_preserved - 身份。\ndetailed_description:\n[Shot 1] {body}\noverall_soundscape:\n室内底噪。\nnon_diegetic_music:\nN/A"
class RoleContractTests(unittest.TestCase):
 def test_existing_voice_id_is_not_renumbered_by_planned_words(self):
  source="<Subject 3> (S2) 说：<d>[Chinese]收到。</d>"
  self.assertEqual(h.bind_dialogue(source,["张三：收到。"]),source)
 def test_requested_group_speech_is_not_collapsed_or_warned_as_missing(self):
  source="<Subject 3> 与 <Subject 1> (S1,S2) 合说：<d>[Chinese]出发！</d>"
  self.assertEqual(h.bind_dialogue(source,["张三和李四：出发！"]),source)
  self.assertEqual(h.content_warnings(source,["张三和李四：出发！"]),[])
 def test_reused_audio_cue_does_not_invent_speaker(self):
  source="<Audio 1> 播放歌词：<d>[Chinese]向前走。</d>"
  self.assertEqual(h.bind_dialogue(source,["音乐：向前走。"]),source)
  self.assertEqual(h.content_warnings(source,[]),[])
 def test_duplicate_alias_and_continuation_remap_warn_without_mutation(self):
  definitions="<Subject 3>（角色名：张三）来自 <Picture 2>。\n<Subject 1>（角色名：张三）来自 <Picture 1>。"
  source=prompt(definitions,"<Subject 3> 站立。")
  self.assertTrue(any("映射冲突" in w for w in h.identity_warnings(source)))
  old="<Subject 2>（角色名：张三）来自 <Picture 2>。"
  self.assertTrue(any("编号变化" in w for w in h.identity_warnings(source,old)))
 def test_reusing_subject_for_a_different_explicit_alias_warns(self):
  old="<Subject 3>（角色名：张三）来自 <Picture 2>。"
  source=prompt("<Subject 3>（角色名：李四）来自 <Picture 5>。", "<Subject 3>站立。")
  self.assertTrue(any("角色名变化" in w for w in h.identity_warnings(source,old)))
 def test_subject_picture_speaker_numbers_are_independent(self):
  definitions="<Subject 3>（角色名：张三）来自 <Picture 2>。"
  source=prompt(definitions,"<Subject 3>（张三） (S1) 说：<d>[Chinese]收到。</d>")
  self.assertEqual(h.identity_warnings(source,definitions),[])
  h.validate_segment(source,["张三：收到。"],["<Picture 2>"],"h3_ref2va")
 def test_named_turn_without_subject_warns_and_legacy_definitions_remain_usable(self):
  source=prompt("<Subject 3>（角色名：张三）来自 <Picture 2>。","张三 (S1) 说：<d>[Chinese]收到。</d>")
  self.assertTrue(any("缺少人物标签" in w for w in h.identity_warnings(source)))
  self.assertEqual(h.subject_aliases("<Subject 1> 是灰衣男性。"),[])
 def test_identity_history_survives_absence_and_uses_latest_edited_definition(self):
  old=prompt("<Subject 3>（角色名：张三）来自 <Picture 2>。", "<Subject 3>站立。")
  absent=prompt("<Subject 1>（角色名：李四）来自 <Picture 5>。", "<Subject 1>站立。")
  edited=prompt("<Subject 3>（角色名：张三）来自 <Picture 2>，改穿外套。", "<Subject 3>站立。")
  history=h.subject_history([{"source_prompt":old},{"prompt":absent},{"timeline_local_prompt":edited}])
  self.assertIn("李四",history);self.assertIn("改穿外套",history)
  self.assertEqual(history.count("角色名：张三"),1)
  self.assertNotIn("雷声",history)
 def test_group_example_is_selected_only_for_positive_intent(self):
  assets=ROOT/"skills/aipm-minimax-h3-video"
  self.assertEqual(h.selected_example(assets,"h3_ref2va","两人齐声说出发")[0],"group-dialogue")
  self.assertFalse(h.requests_group_speech("不要所有人同时说话"))
  self.assertFalse(h.requests_group_speech("do not speak together"))
 def test_every_ref_example_uses_bracketed_summary(self):
  for p in (ROOT/"skills/aipm-minimax-h3-video/examples").glob("*.md"):
   raw=p.read_text(encoding="utf-8")
   if "<!-- REF -->" in raw:raw=raw.split("<!-- REF -->",1)[1]
   if "subject_definitions:" in raw:
    fields=dict(h.sections(raw));self.assertRegex(fields["summary"],r"^\[[^\]]+\]",p.name)
if __name__=="__main__":unittest.main()
