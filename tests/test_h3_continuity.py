import importlib.util
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('h3_continuity_contract',ROOT/'h3_contract.py')
h3=importlib.util.module_from_spec(spec);spec.loader.exec_module(h3)

class H3ContinuityTests(unittest.TestCase):
    def test_negative_cut_requests_do_not_select_cut_example(self):
        for idea in ('一镜到底信封交接','信封交接，不要突然切到特写',
                     'Do not cut to close-up during the handoff','No additional camera cuts during the handoff',
                     '两张人物身份图，信封交接'):
            with self.subTest(idea=idea):
                name,_=h3.selected_example(ROOT/'skills/aipm-minimax-h3-video','h3_ref2va',idea)
                self.assertEqual(name,'action')
    def test_requested_cut_sample_obeys_the_selected_mode(self):
        assets=ROOT/'skills/aipm-minimax-h3-video'
        for mode in ('text_to_video','h3_ref2va'):
            with self.subTest(mode=mode):
                name,text=h3.selected_example(assets,mode,'第3秒切到双手近景，信封交接')
                self.assertEqual(name,'continuity')
                match=re.search(r'(?m)^(subject_definitions:|integrated_multimodal_description:)',text)
                prompt=text[match.start():]
                h3.validate_structure(prompt,mode,8)
                h3.validate_segment(prompt,[],['<Picture 1>','<Picture 2>'],mode)
                body=dict(h3.sections(prompt)).get('detailed_description',dict(h3.sections(prompt)).get('integrated_multimodal_description'))
                self.assertEqual(re.findall(r'\[Shot (\d+)\]',body),['1','2'])

if __name__=='__main__':unittest.main()
