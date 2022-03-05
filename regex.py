import re
from collections import defaultdict
from typing import Pattern, Optional, DefaultDict, Tuple, List
from pathlib import Path
import logging
log = logging.getLogger()
# log.setLevel(logging.DEBUG)

media_exts = ["webm", "mkv", "mp4", "m4a", "opus"]
media_extensions_re = f"{'|'.join(e for e in media_exts)}"
base_yt_video_file_pattern = r'.*\][\s_]?(?P<id>[0-9A-Za-z_-]{11})\.'
yt_video_file_pattern = (
  base_yt_video_file_pattern
  + r'(?P<extension>'
  + media_extensions_re
  + r')$'
)

# Use re.findall on this
# date_capture = r'(?:(?P<date>[0-9]{8})\s+.*?)?'
base_twitch_video_file_pattern = r'(?:[\s_]?v?(?P<id>[0-9]{10}))+'
twitch_video_file_pattern = (
  base_twitch_video_file_pattern
  + r'|(?:\.' # don't capture the period of the extension
  + r'(?P<extension>'
  + media_extensions_re
  + '))$'
)

base_subn = "live_chat"
sub_exts = [
  f"{base_subn}.json", f"{base_subn}.json.gz", f"{base_subn}.json.bz2", "json"
]
sub_exts_esc = '|'.join(re.escape(e) for e in sub_exts)
# This should match both media and any sub-title files
yt_recording_file_pattern = (
  base_yt_video_file_pattern
  + r'(?P<extension>'
  + media_extensions_re
  + '|'
  + sub_exts_esc
  + r')$'
)

# This should only match sub files in format 20220101_v1234567890, not videos
date_pattern = r'(?:\d{8})'
twitch_sub_file_pattern = (
  r'^'
  + date_pattern
  + base_twitch_video_file_pattern
  + r'\.(?:' # don't capture the period of the extension
  + sub_exts_esc
  + r')$'
)


class BaseRegex():
  def __init__(self) -> None:
    # Record path to files found
    # First list in Tuple is found media files
    # SEcond list in Tuple is found subs files
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
        yield key, paths[0]


class YoutubeRegex(BaseRegex):
  regex = re.compile(yt_recording_file_pattern, re.IGNORECASE)

  def match(self, root: str, filename: str) -> bool:
    match = self.regex.match(filename)
    if not match:
      return False
    # The second group should match the extension (this check might not be necessary)
    if len(match.groups()) < 2:
      log.warning(f"Failed to match second capture group for {filename}: {match}.")
      return False
    _id = match.group("id")
    if not _id:
      return False
    # Add to the list of media files or the list of subtitles depending on
    # the type of extension detected.
    self.store[_id][1 if match.group("extension") in sub_exts else 0]\
      .append(Path(Path(root) / Path(filename)))
    log.debug(f"Found youtube media file {filename} against {self.regex}")
    return True


class TwitchRegex(BaseRegex):
  vid_regex = re.compile(twitch_video_file_pattern, re.IGNORECASE)
  # Format is usually YYYYMMDD_twitchId
  subt_regex =  re.compile(twitch_sub_file_pattern, re.IGNORECASE)

  def match(self, root: str, filename: str) -> bool:
    match = self.subt_regex.match(filename)
    if match is not None:
      log.debug(f"Matched twitch sub file {filename} against {self.subt_regex}")
      # if not match.group("extension"):
      #   log.debug("No extension matched. Trying again for media file...")
      #   pass
      _id = match.group("id")
      self.store[_id][1].append(Path(Path(root) / Path(filename)))
      return True
    log.debug(f"No match for {filename} against {self.subt_regex}.")
    
    # We may have mutliple twitchIds in the same filename, hence the iteration
    vid_match = self.vid_regex.finditer(filename)
    if vid_match:
      found = False
      for m in vid_match:
        log.debug(f"Matched twitch video file {filename} against {self.vid_regex}: {m}")
        _id = m.group("id")
        if not _id:
          continue
        _ext = m.group("extension")
        log.debug(f"Extension for {filename} in {self.vid_regex}: {_ext}.")
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