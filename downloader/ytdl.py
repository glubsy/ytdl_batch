from subprocess import run, DEVNULL
from pathlib import Path
from .util import find_program
import logging
import yaml

log = logging.getLogger()

YT_WATCH_URL = r"https://www.youtube.com/watch?v="

class YTDLDownloader():
  default_name = "yt-dlp"

  def __init__(self, process_path: str | None, config_path: Path | None = None) -> None:
    self.handle = find_program(self.default_name, process_path)
    self.config = self._load_config(config_path)
  
  def _load_config(self, config_path: Path | None) -> dict:
    """Load configuration from YAML file."""
    if config_path is None:
      config_path = Path(__file__).parent.parent / "config" / "ytdl_options.yaml"
    
    if config_path.exists():
      with open(config_path, 'r') as f:
        return yaml.safe_load(f)
    else:
      log.warning(f"Config file not found: {config_path}. Using defaults.")
      return self._get_default_config()
  
  def _get_default_config(self) -> dict:
    """Fallback to hardcoded defaults if config file not found."""
    return {
      'video_download': {
        'common_options': ['--exec', 'echo', '--embed-thumbnail', '-N', '4', '-4',
                          '--fragment-retries', '50', '--abort-on-unavailable-fragment',
                          '-ciw', '--add-metadata', '--write-subs', '--embed-subs',
                          '--remux-video', 'mkv'],
        'output_template': '%(upload_date)s [%(uploader)s] %(title)s [%(height)s][%(id)s].%(ext)s',
        'format_options': {
          'format': 'bestvideo[vcodec^=avc1]+bestaudio',
          'sort': '+res:240,res:360,vcodec:avc01'
        },
        'subtitle_options': {'langs': 'live_chat'}
      },
      'chat_only': {
        'common_options': ['--skip-download', '--write-subs'],
        'output_template': '%(upload_date)s [%(uploader)s] %(title)s [%(id)s].%(ext)s',
        'subtitle_options': {'langs': 'live_chat'}
      }
    }

  def build_cmd(
    self, 
    videoId: str, 
    cookies: Path | None = None, 
    skip_video=True
  ):
    cmd = [str(self.handle), "-v"]

    if not skip_video:
      opts = self.config['video_download']
      cmd.extend(opts['common_options'])
      cmd.extend(["-o", opts['output_template']])
      cmd.extend(["-f", opts['format_options']['format']])
      cmd.extend(["-S", opts['format_options']['sort']])
      cmd.extend(["--sub-langs", opts['subtitle_options']['langs']])
    else:  # only interested in live chat here
      opts = self.config['chat_only']
      cmd.extend(opts['common_options'])
      cmd.extend(["-o", opts['output_template']])
      cmd.extend(["--sub-langs", opts['subtitle_options']['langs']])

    if cookies is not None:
      cmd.extend(["--cookies", str(cookies)])

    cmd.append(f"{YT_WATCH_URL + videoId}")
    return cmd


def dl_ytdlp(video_id: str, cli_path: str | None = None, cookies: Path | None = None):
  """
  This function will throw any exception from the subprocess module.
  """
  ytdlp = YTDLDownloader(process_path=cli_path)
  cmd = ytdlp.build_cmd(videoId=video_id, cookies=cookies) # use COOKIE_PATH here
  log.info("Running command: {}".format(" ".join(cmd)))
  run(cmd, check=True)
