import unittest,copy,json
from unittest.mock import patch
from test_nodes import nodes
class KeyframeReplanTests(unittest.TestCase):
 def test_new_box_image_triggers_local_replan(self):
  segment={'segment_id':'SEGMENT_001','title':'方块','duration':5,'brief':'方块移到桌边','negative_prompt':'','reference_ids':['<Picture 1>'],'dialogue_lines':[],'opening_state':'桌左','ending_state':'桌右','continuity_from_previous':'','transition':'cut','keyframe_bindings':[{'reference_id':'<Picture 1>','local_frame':0}],'keyframe_transitions':[]}
  plan={'global_prompt':'静物场景','global_negative_prompt':'','global_reference_ids':[],'global_reference_bindings':[],'segments':[segment]}
  phases=[]
  def fake(cls,url,payload,stage,attempts=2,validator=None):
   phases.append(stage)
   if stage=='时间线规划':value=copy.deepcopy(plan)
   elif stage=='补充当前段关键帧规划':
    value=copy.deepcopy(plan);s=value['segments'][0];s['keyframe_bindings'].append({'reference_id':'<Picture 2>','local_frame':119});s['keyframe_transitions']=['方块由左向右平稳滑动'];s['reference_ids'].append('<Picture 2>')
   else:
    value={'shots':[{'start_seconds':0,'description':'第0帧为红色方块在桌左，第119帧为蓝色方块在桌右。镜头固定，方块沿桌面缓慢滑动，保持桌面、光线和背景连续，整个过程清楚平稳，没有突然切镜。'}],'overall_soundscape':'轻微滑动声。','non_diegetic_music':'N/A','needed_picture_ids':['<Picture 2>'] if phases.count('补充当前段关键帧规划')==0 else []}
   if validator:validator(value)
   return value,{'usage':{}}
  with patch.object(nodes.OpenAICompatibleClient,'request_object',classmethod(fake)):
   result=nodes.AIPMVideoPromptCore().generate_timeline_package(service_url='unused',service_model='synthetic',profile='MiniMax H3',mode='h3_keyframe',idea='方块滑动',duration_seconds=5,segment_count=1,aspect_ratio='16:9',requested_language='中文（推荐）',skill_id='aipm-minimax-h3-video',skill='skill',reference_profiles=[{'picture_id':f'<Picture {i}>','visual_profile':'方块','asset_id':f'box{i}.png'} for i in [1,2]],cache_hits=0,has_video=False,has_audio=False,previous=None,modification='')
  package=json.loads(result['ui']['text'][2])['metadata']['aipm']
  self.assertEqual(package['generation_status'],'complete')
  self.assertEqual(package['segments'][0]['effective_reference_ids'],['<Picture 1>','<Picture 2>'])
  self.assertEqual(len(package['segments'][0]['keyframe_bindings']),2)
