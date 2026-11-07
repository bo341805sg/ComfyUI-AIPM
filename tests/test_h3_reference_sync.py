import unittest
from test_h3_structured import h
class ReferenceSyncTests(unittest.TestCase):
 def test_new_picture_is_local_only(self):
  active=['<Picture 1>','<Picture 2>','<Picture 3>']
  result=h.reconcile_loaded_pictures('蓝色方块来自 <Picture 4>。',active,active+['<Picture 4>'])
  self.assertEqual(result,active+['<Picture 4>']);self.assertEqual(len(active),3)
 def test_unknown_is_rejected(self):
  with self.assertRaises(h.ContractError):h.reconcile_loaded_pictures('<Picture 5>',[],['<Picture 4>'])
 def test_repeat_is_deduplicated(self):
  self.assertEqual(h.reconcile_loaded_pictures('<Picture 4> <Picture 4>',[],['<Picture 4>']),['<Picture 4>'])
 def test_no_new_video_is_activated(self):
  self.assertEqual(h.reconcile_loaded_pictures('<Video 1>',[],[]),[])
