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

  def test_fake_id_in_title_parametrized(self):
    # Examples (although tested prefixes apply to all ids):
    # 20230525 [author] barbazrb GAWME :3333333333 [best][1829043411].mp4
    # 20230525 [author] barbazrb GAWME :3333333333 [best]_1829043411.mp4
    # 20230525 [author] barbazrb GAWME :3333333333 [best]_v1829043411.mp4
    # 20230525 [author] barbazrb GAWME :3333333333 [1080]_v1829043411.mp4
    # 20230525 [author] barbazrb eeevvvvvw :3333333333 ezvezqev [best][1829043411].mp4
    # 20230525 [author] barbazrb eeevvvvvw :3333333333 ezvezqev [best][1829043411_1245364899].mp4
    # 20230525 [author] barbazrb eeevvvvvw :3333333333 ezvezqev [best][v1829043411+v1245364899].mp4
    # 20230525 [author] barbazrb eeevvvvvw :3333333333 ezvezqev [best][v1829043411_v1245364899].mp4
    # 20230525 [author] barbazrb eeevvvvvw :3333333333 ezvezqev [best][v1829043411_v1245364899_1245364899].mp4
    # 20230525 [author] barbazrb eeevvvvvw :3333333333 ezvezqev [best][v1829043411+1245364899+v1245364899].mp4

    base_filename = "20230525 [author] barbazrb GAWME :3333333333 "
    extra_title = ("", "fnck ", "fnck the mafia ")
    quality = ("best", "1080", "720")
    id_separator = ("_", "+")
    id_prefix = ("v", "")
    ids = ["1829043411", "1829043400", "1822043422"]
    extension = ("mp4", )
    for slice_len in range(1, len(ids) + 1):
        for et in extra_title:
          for q in quality:
            for idp in id_prefix:
              slice = ids[:slice_len]
              slice_prefixed = []
              for slice_item in slice:
                slice_prefixed.append(f"{idp}{slice_item}")
              for ext in extension:
                # test with bracket enclosure around ids
                if len(slice) > 1:
                  for sep in id_separator:
                    filename = f"{base_filename}{et}[{q}][{sep.join(slice_prefixed)}].{ext}"
                    print(filename)
                    with self.subTest():
                      scanner = TwitchScanner()
                      self.assertTrue(scanner.match(".", filename))
                      for sliced in slice:
                        self.assertIn(sliced, scanner.store.keys())
                        self.assertIn("author", scanner.store.get(sliced)[0][0].name)
                      self.assertNotIn("3333333333", scanner.store.keys())
                  
                    # test with not enclosure around ids
                    filename = f"{base_filename}{et}[{q}]_{sep.join(slice_prefixed)}.{ext}"
                    print(filename)
                    with self.subTest():
                      scanner = TwitchScanner()
                      self.assertTrue(scanner.match(".", filename))
                      for sliced in slice:
                        self.assertIn(sliced, scanner.store.keys())
                        self.assertIn("author", scanner.store.get(sliced)[0][0].name)
                      self.assertNotIn("3333333333", scanner.store.keys())
                else:
                    filename = f"{base_filename}{et}[{q}][{slice[0]}].{ext}"
                    print(filename)
                    with self.subTest():
                      scanner = TwitchScanner()
                      self.assertTrue(scanner.match(".", filename))
                      for sliced in slice:
                        self.assertIn(sliced, scanner.store.keys())
                        self.assertIn("author", scanner.store.get(sliced)[0][0].name)
                      self.assertNotIn("3333333333", scanner.store.keys())

                    # test with not enclosure around ids
                    filename = f"{base_filename}{et}[{q}]_{slice[0]}.{ext}"
                    print(filename)
                    with self.subTest():
                      scanner = TwitchScanner()
                      self.assertTrue(scanner.match(".", filename))
                      for sliced in slice:
                        self.assertIn(sliced, scanner.store.keys())
                        self.assertIn("author", scanner.store.get(sliced)[0][0].name)
                      self.assertNotIn("3333333333", scanner.store.keys())


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