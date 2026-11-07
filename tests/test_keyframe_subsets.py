import unittest
from test_nodes import nodes
class KeyframeSubsetsTests(unittest.TestCase):
 def test_later_segment_first_uses_new_image(self):
  profiles=[{'picture_id':f'<Picture {i}>','asset_id':f'box{i}.png'} for i in range(1,5)]
  segments=[]
  for number,ids in enumerate([[1,2],[3,4],[4]],1):
   bindings=[{'reference_id':f'<Picture {i}>','local_frame':0 if j==0 else 119} for j,i in enumerate(ids)]
   segments.append({'segment_id':f'SEGMENT_{number:03d}','duration':5,'timeline_local_prompt':'方块移动。','effective_reference_ids':[x['reference_id'] for x in bindings],'keyframe_bindings':bindings})
  package={'schema':'aipm_video_timeline','generation_mode':'h3_keyframe','global':{},'reference_profiles':profiles,'segments':segments,'video_prompt':'方块移动。'}
  timeline=nodes.AIPMCineTimelineAdapter().convert(package,24,'cut')['result'][0]
  refs=timeline['references']
  self.assertEqual(len(refs),5)
  second=[r for r in refs if r['shot_id']=='SEGMENT_002']
  self.assertEqual([r['asset_id'] for r in second],['box3.png','box4.png'])
  self.assertEqual([r['keyframe_role'] for r in second],['first','last'])
  self.assertEqual([r['keyframe_local_frame'] for r in second],[0,119])
  third=[r for r in refs if r['shot_id']=='SEGMENT_003']
  self.assertEqual(len(third),1);self.assertEqual(third[0]['keyframe_local_frame'],0)
