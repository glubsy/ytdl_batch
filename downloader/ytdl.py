from typing import Optional
from os import getenv
from os.path import expanduser
from subprocess import run, DEVNULL
from pathlib import Path
from downloader.util import setup_handler
import logging
log = logging.getLogger(__name__)

BASE_URL = r"https://www.youtube.com/watch?v="
YTDLP_NAME = "yt-dlp"

# The environment variable can be set to point to yt-dlp if it is not found by which
YTDL_PATH = setup_handler(YTDLP_NAME, getenv("YTDL"))
if YTDL_PATH is None:
  exit(1)


def get_cmd(videoId: str, cookies: Optional[str] = None):
  cmd = [
    str(YTDL_PATH), "-v", 
    "--exec", "echo", # print name written after postprocessing complete (not sure if this works)
    "--embed-thumbnail",
    # "--concurrent-fragments", "2",
    "-N", "4",
    "-4",
    #"--extractor-args", "youtube:player_client=android", "--sleep-interval", "5",
    #"--throttled-rate", "3000", # extract video data again under this rate
    "--fragment-retries", "50",
    "--abort-on-unavailable-fragment",
    # "-k",
    "-o", "%(upload_date)s %(uploader)s %(title)s_[%(height)s]_%(id)s.%(ext)s",
    # "--print", "filename",  # print filename output according to template
    "-ciw",
    #"--cookies", COOKIE_PATH,
    # "-f", "133+251",
    "-f", 'bestvideo[vcodec^=avc1]+bestaudio',
    "-S", '+res:240,res:360,vcodec:avc01', # filter: prefer 240p, otherwise 360p, h264 video codec
    # "--external-downloader", "aria2c", "--external-downloader-args", "-c -j 3 -x 3 -s 3 -k 1M",
    "--add-metadata",
    "--write-subs",
    "--sub-langs", "live_chat",
    #"--convert-subs", "srt", # Json live_chat does not work currently
    "--embed-subs",
    "--remux-video", "mkv",
    BASE_URL + videoId
  ]
  if cookies is not None:
    cmd.insert(-1, cookies)
  return cmd


def dl_ytdlp(video_id: str, cookies: Optional[str] = None):
  """This function will throw any exception from the subprocess module."""
  cmd = get_cmd(videoId=video_id, cookies=cookies) # use COOKIE_PATH here
  log.info("Running command: {}".format(" ".join(cmd)))
  run(cmd, check=True)
