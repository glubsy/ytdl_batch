from os.path import expanduser
from platform import python_version_tuple
from pathlib import Path
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
