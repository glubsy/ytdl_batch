from os.path import expanduser
from os import getenv
from pathlib import Path
from downloader.util import setup_handler
from downloader.ytdl import YTDL_PATH

# Command to download twitch subtitle
# using TwitchDL

TDCLI_NAME = "TwitchDownloaderCLI"

TDCLI_PATH = setup_handler(TDCLI_NAME, getenv("TDCLI"))
if TDCLI_PATH is None:
  # FIXME this should not be fatal, handle graciously
  print(f"Missing downloader: {TDCLI_NAME}. Please set TDCLI env variable.")
  exit(1)


def get_cmd(videoId: str, args):
  """Generate yt-dlp to download from twitch"""
  raise NotImplementedError()


def get_subs_cmd(videoId: str, kwargs):
  if not videoId:
    raise Exception(f"Invalid videoId: {videoId}.")
  
  date = kwargs.get("date")
  output_name = f"{date}_{videoId}" if date is not None else videoId
  # if out_path := kwargs.get("out_path"):
  #   output_path = Path(out_path) / (output_name + ".json")
  # else:
  output_path = output_name + ".json"

  cmd = [
    str(TDCLI_PATH), 
    "chatdownload", 
    "--id", videoId,
    "-o", str(output_path)
  ]
  # TODO pass in oauth value from cookies
  return cmd