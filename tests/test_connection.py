import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('settings_probe', Path(__file__).parents[1] / 'connection_settings.py')
settings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(settings)

class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'AIPM_CONFIG_PATH': str(Path(self.temp.name)/'connection.json'), 'AIPM_API_KEY': '', 'PROMPT_ASSISTANT_API_KEY': ''})
        self.env.start()
    def tearDown(self):
        self.env.stop(); self.temp.cleanup()
    def test_secret_stays_server_side_and_blank_patch_preserves_it(self):
        public = settings.save({'service_url':'http://test/v1', 'model_id':'test-model', 'api_key':'test-secret'})
        self.assertNotIn('api_key', public)
        self.assertNotIn('test-secret', str(public))
        settings.save({'model_id':'next-model'})
        self.assertEqual(settings.api_key_for('http://test/v1/chat/completions'), 'test-secret')
        self.assertEqual(settings.api_key_for('http://other/v1'), '')
        settings.save({'api_key':''})
        self.assertFalse(settings.public()['has_api_key'])
    def test_invalid_update_keeps_previous_file(self):
        settings.save({'service_url':'http://test/v1', 'model_id':'old'})
        for changes in ({'service_url':'file:///tmp'}, {'service_url':'http://name:secret@test/v1'}, {'api_key':'bad\r\nheader'}, {'model_id':''}):
            with self.assertRaises(ValueError): settings.save(changes)
        self.assertEqual(settings.load()['model_id'], 'old')
    def test_environment_fallback(self):
        with patch.dict(os.environ, {'AIPM_API_KEY':'env-secret'}):
            self.assertTrue(settings.public()['has_api_key'])
            self.assertEqual(settings.effective_key(settings.load()), 'env-secret')
    def test_real_request_client_sends_saved_bearer_key(self):
        import json
        from unittest.mock import MagicMock
        node_spec = importlib.util.spec_from_file_location('aipm_request_probe', Path(__file__).parents[1]/'nodes.py')
        nodes = importlib.util.module_from_spec(node_spec); node_spec.loader.exec_module(nodes)
        settings.save({'service_url':'http://test/v1','model_id':'model','api_key':'request-test-secret'})
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({'choices':[]}).encode()
        with patch.object(nodes.urllib.request,'urlopen',return_value=response) as call:
            nodes.OpenAICompatibleClient.request('http://test/v1', {'model':'model'})
            request=call.call_args.args[0]
            self.assertEqual(request.get_header('Authorization'),'Bearer request-test-secret')
            self.assertNotIn('request-test-secret',request.data.decode())
            nodes.OpenAICompatibleClient.request('http://other/v1', {'model':'model'})
            self.assertIsNone(call.call_args.args[0].get_header('Authorization'))
    def test_all_node_calls_use_global_connection_and_cache_changes(self):
        class Fake:
            FUNCTION='run'
            @classmethod
            def INPUT_TYPES(cls): return {'required':{'远程服务地址':('STRING',), '模型名称':('STRING',), 'text':('STRING',)}}
            def run(self, text, 远程服务地址, 模型名称): return text, 远程服务地址, 模型名称
        classes={name:type(name,(Fake,),{}) for name in ('AIPMImagePrompt','AIPMVideoPrompt','AIPMPromptRefinement')}
        settings.configure_nodes(classes)
        settings.save({'service_url':'http://test/v1', 'model_id':'first'})
        for cls in classes.values():
            self.assertEqual(list(cls.INPUT_TYPES()['required']), ['text'])
            self.assertEqual(cls().run(text='hello'), ('hello','http://test/v1','first'))
            before=cls.IS_CHANGED()
            settings.save({'model_id':'second'})
            self.assertNotEqual(before, cls.IS_CHANGED())
            self.assertEqual(cls().run(text='hello', 远程服务地址='http://old', 模型名称='old')[2], 'second')
            settings.save({'model_id':'first'})

if __name__ == '__main__': unittest.main()
