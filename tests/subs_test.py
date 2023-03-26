# import tempfile
import pytest
from unittest import mock
from .conftest import *

# TODO test Handlers
# FIXME rework this

@pytest.fixture
def crawl_twitch_files():
  with mock.patch('subs.crawl_files') as mock_f:
    mock_f.return_value = iter(TWITCH_MEDIA_W_SUB + TWITCH_MEDIA_WO_SUB)
    return mock_f()

@pytest.fixture
def crawl_yt_files():
  with mock.patch('subs.crawl_files') as mock_f:
    mock_f.return_value = iter(YT_MEDIA_W_SUB + YT_MEDIA_WO_SUB)
    return mock_f()


# These allow multiple calls to the same mocked function
@pytest.fixture
@mock.patch('subs.crawl_files')
def twitch_files(mm):
  def fake():
    yield from (TWITCH_MEDIA_W_SUB + TWITCH_MEDIA_WO_SUB)
  mm.side_effect = fake
  return mm

@pytest.fixture
@mock.patch('subs.crawl_files')
def yt_files(mm):
  def fake():
    yield from (YT_MEDIA_W_SUB + YT_MEDIA_WO_SUB)
  mm.side_effect = fake
  return mm

def test_regex(twitch_files, yt_files):
  
  from subs import YoutubeHandler, TwitchHandler
  yt = YoutubeHandler()
  tr = TwitchHandler()

  for media in ([f for f in twitch_files()] + [i for i in yt_files()]):
    print(f"filename {media}")
    yt.scanner.match(root=".", filename=media.name)
    tr.scanner.match(root=".", filename=media.name)

    print(f"store {tr.scanner.store.values()}")
    for f in TWITCH_MEDIA_W_SUB + TWITCH_MEDIA_WO_SUB:
      assert f in [(files, subs) for files, subs in tr.scanner.store.values()]

