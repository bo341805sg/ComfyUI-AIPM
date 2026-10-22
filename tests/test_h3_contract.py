import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('h3_contract_probe',ROOT/'h3_contract.py')
h3=importlib.util.module_from_spec(spec); spec.loader.exec_module(h3)

def base(body):
    return f'integrated_multimodal_description: {body}\n\noverall_soundscape: 雨声\n\nnon_diegetic_music: N/A'

class H3ContractTests(unittest.TestCase):
    def test_split_utterance_keeps_actor_and_words(self):
        source=base('[Shot 1] 母亲说：<d>[Chinese] 等一下。</d> 她接着说：<d>[Chinese] 看这里。</d> 女儿回答：<d>[Chinese] 好。</d>')
        bound=h3.bind_dialogue(source,['母亲：等一下。看这里。','女儿：好。'])
        self.assertEqual(bound.count('(S1)'),2); self.assertEqual(bound.count('(S2)'),1)
        self.assertEqual(h3.DIALOGUE.findall(source),h3.DIALOGUE.findall(bound))
        self.assertEqual(h3.bind_dialogue(bound,['母亲：等一下。看这里。','女儿：好。']),bound)
    def test_missing_and_rewritten_dialogue_are_rejected(self):
        for body in ('[Shot 1] 母亲说：<d>[Chinese] 等一下。</d>', '[Shot 1] 母亲说：<d>[Chinese] 请等一下。</d> 女儿回答：<d>[Chinese] 好。</d>'):
            with self.assertRaises(h3.ContractError):
                h3.bind_dialogue(base(body),['母亲：等一下。','女儿：好。'])
    def test_cut_order_is_strict(self):
        for times in [('04','02'),('02','02')]:
            with self.assertRaises(h3.ContractError):
                h3.validate_structure(base(f'[Shot 1] 开场。[Shot 2] At 00:{times[0]}.000, 切镜。[Shot 3] At 00:{times[1]}.000, 切镜。'),'text_to_video',8)
    def test_spoken_clock_is_not_an_action_timestamp(self):
        h3.validate_structure(base('[Shot 1] 母亲 (S1) 说：<d>[English] At 00:09.000 we leave.</d>'),'text_to_video',8)
    def test_add_guide_rejects_ref_labels(self):
        with self.assertRaises(h3.ContractError):
            h3.validate_structure(base('[Shot 1] 第0帧来自 <Picture 1>。'),'h3_keyframe',8)
    def test_reference_must_be_active(self):
        prompt='subject_definitions:\n<Subject 1> 来自 <Picture 2>。\nsummary:\nreference generation.\nretention_analysis:\n<Subject 1> 为 fully_preserved。\ndetailed_description:\n[Shot 1] <Subject 1> 站稳。\noverall_soundscape:\n雨声\nnon_diegetic_music:\nN/A'
        with self.assertRaises(h3.ContractError): h3.validate_segment(prompt,[],['<Picture 1>'],'h3_ref2va')
    def test_examples_follow_selected_mode(self):
        root=ROOT/'skills/aipm-minimax-h3-video'
        for mode in ('h3_ref2va','text_to_video','h3_keyframe','h3_fl2va','h3_i2va','h3_l2va'):
            _,text=h3.selected_example(root,mode,'人物对话')
            self.assertEqual('subject_definitions:' in text,mode=='h3_ref2va')
            if mode=='h3_keyframe': self.assertNotIn('<Picture',text)
            if mode=='h3_i2va': self.assertIn('For the target video, at 0.00',text); self.assertNotIn('Picture 2',text)
    def test_negative_speech_request_does_not_require_dialogue(self):
        self.assertFalse(h3.requires_dialogue('无对白，没有旁白。'))
        self.assertFalse(h3.requires_dialogue('without dialogue'))
        self.assertTrue(h3.requires_dialogue('不要省略对白，母亲说一句话。'))

if __name__=='__main__': unittest.main()
