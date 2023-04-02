import re
from collections import defaultdict
from typing import Pattern, Optional, DefaultDict, Tuple, List
from pathlib import Path
import logging
log = logging.getLogger()
# log.setLevel(logging.DEBUG)

media_exts = ["webm", "mkv", "mp4", "m4a", "opus"]
media_extensions_re = f"{'|'.join(e for e in media_exts)}"
# Expecting a date between [], 
# otherwise the date is a simple YYYYMMDD at the start of the filename
base_yt_video_file_pattern = r'.*[\s_]?(?P<id>[0-9A-Za-z_-]{11})\.'
yt_video_file_pattern = (
  base_yt_video_file_pattern
  + r'(?P<extension>'
  + media_extensions_re
  + r')$'
)

# Use re.findall on this
# date_capture = r'(?:(?P<date>[0-9]{8})\s+.*?)?'
base_twitch_video_file_pattern = r'(?:[\s_]?v?(?P<id>[0-9]{10}))+?'
twitch_video_file_pattern = (
  base_twitch_video_file_pattern
  + r'|(?:\.' # don't capture the period of the extension
  + r'(?P<extension>'
  + media_extensions_re
  + '))$'
)

def sub_extensions(base_sub_name: str) -> List:
  """
  Return a list of extension base names.
  """
  if base_sub_name:
    base_sub_name = base_sub_name + "."
  return [
    f"{base_sub_name}json",
    f"{base_sub_name}json.gz",
    f"{base_sub_name}json.bz2",
    "json"  # FIXME not sure about this one
  ]


yt_base_subn = "live_chat"
yt_sub_exts = sub_extensions(yt_base_subn)
yt_sub_exts_esc = '|'.join(re.escape(e) for e in yt_sub_exts)
# This should match both media and any sub-title files
yt_recording_file_pattern = (
  base_yt_video_file_pattern
  + r'(?P<extension>'
  + media_extensions_re
  + '|'
  + yt_sub_exts_esc
  + r')$'
)

# This should only match sub files in format 20220101_v1234567890, not videos
date_pattern = r'(?:\d{8})'
twitch_base_subn = ""  # No explicit name for twitch subs, only date_twitchVideoId
twitch_sub_exts = sub_extensions(twitch_base_subn)
twitch_sub_exts_esc = '|'.join(re.escape(e) for e in twitch_sub_exts)
twitch_sub_file_pattern = (
  r'^'
  + date_pattern
  + base_twitch_video_file_pattern
  + r'\.(?:' # don't capture the period of the extension
  + twitch_sub_exts_esc
  + r')$'
)


class BaseScanner():
  def __init__(self) -> None:
    # Record path to files found
    # First list in Tuple is found media files
    # Second list in Tuple is found subs files
    self.store: DefaultDict[str, Tuple[List[Path], List[Path]]] = \
      defaultdict(lambda: ([],[]))

  def match(self, root: str, filename: str) -> bool:
    """
    If "root / filename" matches our internal regex, add found ID in filename
    to the store as a media file or a sub file depending on extension.
    """
    raise NotImplementedError()

  def to_download(self):
    for key, paths in self.store.items():
      if len(paths[1]) == 0:
        # There is no found subs files, return the path to the media file
        yield key, paths[0]


class YoutubeScanner(BaseScanner):
  regex = re.compile(yt_recording_file_pattern, re.IGNORECASE)

  def match(self, root: str, filename: str) -> bool:
    match = self.regex.match(filename)
    if not match:
      return False

    # The second group should match the extension (this check might not be necessary)
    if len(match.groups()) < 2:
      log.warning(f"{__class__} failed to match second capture group for {filename}: {match}.")
      return False

    _id = match.group("id")
    if not _id:
      return False

    # Add to the list of media files or the list of subtitles depending on
    # the type of extension detected.
    self.store[_id][1 if match.group("extension") in yt_sub_exts else 0]\
      .append(Path(Path(root) / Path(filename)))
    log.debug(f"{__class__} found youtube media file {filename}")

    return True


class TwitchScanner(BaseScanner):
  vid_regex = re.compile(twitch_video_file_pattern, re.IGNORECASE)
  # Format is usually YYYYMMDD_twitchId
  subt_regex =  re.compile(twitch_sub_file_pattern, re.IGNORECASE)

  def match(self, root: str, filename: str) -> bool:
    match = self.subt_regex.match(filename)
    if match is not None:
      log.debug(f"{__class__} matched twitch sub file {filename}")
      # if not match.group("extension"):
      #   log.debug("No extension matched. Trying again for media file...")
      #   pass
      _id = match.group("id")
      self.store[_id][1].append(Path(Path(root) / Path(filename)))
      return True
    log.debug(f"{__class__} no sub file match for {filename}")

    # We may have mutliple twitchIds in the same filename, hence the iteration
    vid_match = self.vid_regex.finditer(filename)
    if vid_match:
      found = False
      for m in vid_match:
        log.debug(f"{__class__} matched twitch video file {filename}: {m}")
        _id = m.group("id")

        if not _id:
          continue

        _ext = m.group("extension")
        log.debug(f"{__class__} extension for {filename}: {_ext}.")
        # if not _ext:
        #   continue
        # _date = m.group("date")

        self.store[_id][0]\
          .append(
            Path(Path(root) / Path(filename))
          )
        found = True
      return found

    return False