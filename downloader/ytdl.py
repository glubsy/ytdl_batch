from typing import Optional
from subprocess import run, DEVNULL
from pathlib import Path
from .util import find_program
import logging
log = logging.getLogger()

YT_WATCH_URL = r"https://www.youtube.com/watch?v="

class YTDLDownloader():
  default_name = "yt-dlp"

  def __init__(self, process_path: Optional[str]) -> None:
    self.handle = find_program(self.default_name, process_path)

  def build_cmd(
    self, videoId: str, cookies: Optional[Path] = None, skip_video=True):
    cmd = [str(self.handle), "-v"]

    if not skip_video:
      cmd.extend(
        [
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
        ]
      )
    else:  # only intersested in live chat here
      cmd.extend(
        [
          "--skip-download",
          "--write-subs",
          "--sub-langs", "live_chat",
          "-o", "%(upload_date)s %(uploader)s %(title)s_%(id)s.%(ext)s",
        ]
      )

    if cookies is not None:
      cmd.extend(["--cookies", str(cookies)])

    cmd.append(f"{YT_WATCH_URL + videoId}")
    return cmd


# FIXME
def dl_ytdlp(video_id: str, cli_path: str, cookies: Optional[Path] = None):
  """This function will throw any exception from the subprocess module."""
  ytdlp = YTDLDownloader(cli_path=cli_path)
  cmd = ytdlp.build_cmd(videoId=video_id, cookies=cookies) # use COOKIE_PATH here
  log.info("Running command: {}".format(" ".join(cmd)))
  run(cmd, check=True)
