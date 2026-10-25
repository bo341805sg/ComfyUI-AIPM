import importlib.util, unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("camera_h3",R/"h3_contract.py")
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
class CameraContextTests(unittest.TestCase):
 def test_empty_history_stays_unknown(self):
  self.assertEqual(h.previous_shot_context({}),{})
 def test_ref_body_preserves_last_camera_without_sound_or_definitions(self):
  prompt="subject_definitions: 身份\ndetailed_description: [Shot 1] 固定镜头。\n[Shot 2] At 00:04.000, 摄影机向右横移，结尾继续。\noverall_soundscape: 雷声\nnon_diegetic_music: N/A"
  result=h.previous_shot_context({"timeline_local_prompt":prompt,"ending_state":"横移中"})
  self.assertIn("向右横移",result["visual_description"])
  self.assertNotIn("雷声",result["visual_description"])
  self.assertNotIn("身份",result["visual_description"])
  self.assertEqual(result["ending_state"],"横移中")
  self.assertIn("not_observed",result["basis"])
 def test_base_and_legacy_history_can_continue(self):
  for key in ["source_prompt","prompt"]:
   result=h.previous_shot_context({key:"integrated_multimodal_description: [Shot 1] 缓慢推进。\noverall_soundscape: 风"})
   self.assertIn("缓慢推进",result["visual_description"])
   self.assertEqual(result["ending_state"],"")
 def test_edited_timeline_prompt_takes_precedence(self):
  result=h.previous_shot_context({"timeline_local_prompt":"新机位","source_prompt":"旧机位"})
  self.assertEqual(result["visual_description"],"新机位")
if __name__=="__main__":unittest.main()
