from typing import List, Optional
from downloader.util import find_program

# Command to download twitch subtitles using TwitchDownloaderCLI

class TwitchDownloaderCLI():
  default_name = "TwitchDownloaderCLI"

  def __init__(self, process_path: Optional[str]) -> None:
    self.handle = find_program(self.default_name, process_path)

  def get_cmd(self, videoId: str, args):
    """Generate yt-dlp to download from twitch"""
    raise NotImplementedError()

  def build_cmd(self, videoId: str, kwargs) -> List[str]:
    """
    Get command to download a subtitle file for videoId.
    """
    if not videoId:
      raise Exception(f"Invalid videoId: {videoId}.")

    date = kwargs.get("date")
    output_name = f"{date}_{videoId}" if date is not None else videoId
    # if out_path := kwargs.get("out_path"):
    #   output_path = Path(out_path) / (output_name + ".json")
    # else:
    output_path = output_name + ".json"

    cmd = [
      str(self.handle),
      "chatdownload",
      "--id", videoId,
      "-E",
      "-o", str(output_path)
    ]

    # TODO pass in oauth value from cookies
    return cmd
