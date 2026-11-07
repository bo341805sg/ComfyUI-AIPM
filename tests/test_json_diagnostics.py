import unittest
from unittest.mock import patch
from test_nodes import nodes
class JsonDiagnosticsTests(unittest.TestCase):
 def check(self,text,reason,expected,validator=None):
  response={'choices':[{'finish_reason':reason,'message':{'content':text}}]}
  with patch.object(nodes.OpenAICompatibleClient,'request',return_value=response):
   with self.assertRaises(nodes.PromptAssistantError) as caught:
    nodes.OpenAICompatibleClient.request_object('unused',{},'合成测试',attempts=1,validator=validator)
  self.assertIn(expected,str(caught.exception));self.assertIn('finish_reason='+reason,str(caught.exception))
 def test_parse_error(self):self.check('{invalid','stop','JSON解析失败')
 def test_confirmed_truncation(self):self.check('{','length','接口确认截断')
 def test_validation_is_not_parse_error(self):
  def reject(data):raise nodes.PromptAssistantError('缺少颜色字段')
  self.check('{"object":"box"}','stop','JSON已解析',reject)
 def test_success(self):
  with patch.object(nodes.OpenAICompatibleClient,'request',return_value={'choices':[{'finish_reason':'stop','message':{'content':'{"object":"box"}'}}]}):
   result,_=nodes.OpenAICompatibleClient.request_object('unused',{},'合成测试',attempts=1)
  self.assertEqual(result,{'object':'box'})
