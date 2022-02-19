from os.path import expanduser
from platform import python_version_tuple
from pathlib import Path
import re
import logging
log = logging.getLogger(__name__)

py_ver_tuple = python_version_tuple()

# Could also use --cookies-from-browser BROWSER[:PROFILE] with yt-dlp
COOKIE_PATH = expanduser("~/Cookies/firefox_cookies.txt")

SFX = {
  "FAILED": expanduser(
    "~/Music/sfx/242503__gabrielaraujo__failure-wrong-action.wav"),
  "WARNING": expanduser(
    "~/Music/sfx/350860__cabled-mess__blip-c-07.wav"),
  "SUCCESS": expanduser(
    "~/Music/sfx/256113_3263906-lq.ogg")
}

for var in (COOKIE_PATH,):
  pvar = Path(var)
  if not pvar.exists():
    print(f"Error: could not find \"{var}\". Edit the variable")

media_exts = ["webm", "mkv", "mp4", "m4a", "opus"]
extensions_re = f"{'|'.join(e for e in media_exts)}"
base_video_file_pattern = r'.*[\s_]?([0-9A-Za-z_-]{11})\.'
video_file_pattern = (
  base_video_file_pattern 
  + r"(" 
  + extensions_re
  + r")$"
)

base_subn = "live_chat"
sub_exts = [f"{base_subn}.json", f"{base_subn}.json.gz", f"{base_subn}.json.bz2"]
sub_exts_esc = '|'.join(re.escape(e) for e in sub_exts)
# This should match both media and sub-title files
recording_file_pattern = (
  base_video_file_pattern
  + r"("
  + extensions_re
  + sub_exts_esc
  + r")$"
)