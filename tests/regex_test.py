from types import NoneType
from unittest import TestCase
import logging
log = logging.getLogger()
log.setLevel(logging.DEBUG)

from ytdl_batch.regex import TwitchScanner, YoutubeScanner
from .conftest import *


def flatten(defaultdict, convert_to=str):
  """Flatten values in a default dictionary."""
  l = []
  for matched in defaultdict.values():
    for _tuple in matched:
      for path in _tuple:
        l.append(convert_to(path) if type(convert_to) != NoneType else path)
        log.info(f"converted {path} to {convert_to}")
  return l


def is_in(haystack, needle):
  index = None
  if type(needle) in (TwitchVideo, YoutubeVideo):
    index = 0
  if type(needle) in (TwitchSub, YoutubeSub):
    index = 1

  for _tuple in haystack.values():
    assert (len(_tuple[index]) > 0)
    for path in _tuple[index]:
      if str(path) == needle.name:
        return True
  return False


def assert_matched(lookup, regex_type):
  regex = regex_type()
  matched = regex.match(".", lookup.name)
  assert matched
  assert len(regex.store.values()) > 0
  items = flatten(regex.store, str)
  assert lookup.name in items
  assert lookup.videoId in [x for x in regex.store.keys()]
  # Make sure it is in the appropriate list of the tuple
  assert is_in(regex.store, lookup)


def test_regexes():
  for test_case in TEST_CASES:
    _type = TwitchScanner \
      if type(test_case) in (TwitchVideo, TwitchSub) \
      else YoutubeScanner
    assert_matched(lookup=test_case, regex_type=_type)


class TestTwitchRegex(TestCase):

  def test_multiple_ids(self):
    # All Ids should be detected
    filename = "20220210 [Matsuro Meru] EAT EAT EAT EAT EAT nuggie & appo juice #016 [270]_v1293952620_v1294022479.mp4"
    scanner = TwitchScanner()
    self.assertTrue(scanner.match(".", filename))
    self.assertIn("1293952620", scanner.store.keys())
    self.assertIn("1294022479", scanner.store.keys())

  def test_multiple_ids_no_v(self):
    # An Id without "v" should also be detected
    filename = "20220210 [Matsuro Meru] EAT EAT EAT EAT EAT nuggie & appo juice #016 [270]_v1293952620_v1294022479_1234567890.mp4"
    scanner = TwitchScanner()
    self.assertTrue(scanner.match(".", filename))
    self.assertIn("1293952620", scanner.store.keys())
    self.assertIn("1294022479", scanner.store.keys())
    self.assertIn("1234567890", scanner.store.keys())

  def test_bracket_around_author(self):
    filename = "20230323 [Amaris Yuri] drawing stickers [180]_1773634033.mp4"
    scanner = TwitchScanner()
    self.assertTrue(scanner.match(".", filename))
    self.assertIn("1773634033", scanner.store.keys())
    self.assertIn("Amaris Yuri", scanner.store.get("1773634033")[0][0].name)

  def test_bracket_around_id(self):
    filename = "20230323 [Amaris Yuri] drawing stickers [180][1773634033].mp4"
    scanner = TwitchScanner()
    self.assertTrue(scanner.match(".", filename))
    self.assertIn("1773634033", scanner.store.keys())
    self.assertIn("Amaris Yuri", scanner.store.get("1773634033")[0][0].name)

  def test_bracket_around_id_v_prefix(self):
    filename = "20230323 [Amaris Yuri] drawing stickers [180][v1773634033].mp4"
    scanner = TwitchScanner()
    self.assertTrue(scanner.match(".", filename))
    self.assertIn("1773634033", scanner.store.keys())
    self.assertIn("Amaris Yuri", scanner.store.get("1773634033")[0][0].name)

  def test_bracket_around_multiple_ids(self):
    filename = "20230323 [Amaris Yuri] drawing stickers [180][v1773634033_v1234567890].mp4"
    scanner = TwitchScanner()
    self.assertTrue(scanner.match(".", filename))
    self.assertIn("1773634033", scanner.store.keys())
    self.assertIn("1234567890", scanner.store.keys())
    self.assertIn("Amaris Yuri", scanner.store.get("1773634033")[0][0].name)

  def test_bracket_around_multiple_ids_no_v(self):
    filename = "20230323 [Amaris Yuri] drawing stickers [180][1773634033_v1234567890].mp4"
    scanner = TwitchScanner()
    self.assertTrue(scanner.match(".", filename))
    self.assertIn("1773634033", scanner.store.keys())
    self.assertIn("1234567890", scanner.store.keys())
    self.assertIn("Amaris Yuri", scanner.store.get("1773634033")[0][0].name)


class TestYoutubeIdDetection(TestCase):

  def test_sub_file_detected(self):
    # youtube Id should be detected
    filename = "20230127 Purin 【Project Zomboid】Play with me~ ：3_Emb76dePufw.live_chat.json"
    scanner = YoutubeScanner()
    scanner.match(root=".", filename=filename)
    self.assertIn("Emb76dePufw", scanner.store.keys())
    self.assertIn("Emb76dePufw", scanner.store["Emb76dePufw"][1][0].name)

  def test_compressed_file_detected(self):
    filename = "20230127 Purin 【Project Zomboid】Play with me~ ：3_Emb76dePufw.live_chat.json.bz2"
    scanner = YoutubeScanner()
    scanner.match(root=".", filename=filename)
    self.assertIn("Emb76dePufw", scanner.store.keys())
    self.assertIn("Emb76dePufw", scanner.store["Emb76dePufw"][1][0].name)

  def test_compressed_file_detected_bracket_around_id(self):
    filename = "20230127 Purin 【Project Zomboid】Play with me~ ：3 [Emb76dePufw].live_chat.json.bz2"
    scanner = YoutubeScanner()
    scanner.match(root=".", filename=filename)
    self.assertIn("Emb76dePufw", scanner.store.keys())
    self.assertIn("Emb76dePufw", scanner.store["Emb76dePufw"][1][0].name)

  def test_media_detected(self):
    filename = "20230330 [Gawr Gura Ch. hololive-EN] 【MINECRAFT】i love minecraft [240p][dh4s0bBrPx0].mp4"
    scanner = YoutubeScanner()
    scanner.match(root=".", filename=filename)
    self.assertIn("dh4s0bBrPx0", scanner.store.keys())
    self.assertIn("dh4s0bBrPx0", scanner.store["dh4s0bBrPx0"][0][0].name)