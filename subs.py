#!/bin/env python3
from os import walk
from collections import defaultdict
import re
from pathlib import Path
from typing import DefaultDict, Iterable, Optional, List, Dict, Generator, Pattern, Tuple, Any
import argparse
import gzip
import bz2
import shutil
import fileinput
import logging
from downloader import twitch, ytdl
from constants import COOKIE_PATH
from subprocess import run, CalledProcessError
from regex import (
  BaseRegex, TwitchRegex, YoutubeRegex, yt_recording_file_pattern, 
  twitch_sub_file_pattern, twitch_video_file_pattern, sub_exts
)

log = logging.getLogger()
log.setLevel(logging.DEBUG)


class AlreadyPresentError(Exception):
  pass

class NotAvailableAnymore(Exception):
  pass

class NeedCookies(Exception):
  pass



def compress(
  in_file: Path,
  in_fd = None,
  algo: str = "bz2",
  on_success = "remove"
) -> Optional[Path]:
  """
  Compress file pointed to by in_file. fd can be an open file descriptor to
  the file. out_dir is the output directory. If on_success == "remove" the original
  file will be deleted.
  """
  written = None
  if in_fd is None:
    with open(in_file, "rb") as in_fd:
      written = compress_file(in_fd, base_out_path=in_file, algo=algo)
  else:   # Reuse the open file descriptor if possible
    written = compress_file(in_fd, base_out_path=in_file, algo=algo)

  if on_success == "remove" and written is not None and written.exists():
    log.info(f"Removing original file {in_file}.")
    in_file.unlink()

  return written

def compress_file(in_fd, base_out_path: Path, algo: str) -> Optional[Path]:
  """Compress in_fd into the same directory. Return produced file path on success."""
  out_file = base_out_path.with_suffix(base_out_path.suffix + f".{algo}")

  if out_file.exists():
    log.warning(f"{out_file} already exists. Skipping compression.")
    return None

  if algo == "bz2":
    with bz2.open(out_file, "wb") as f:
      # Write compressed data to file
      f.write(in_fd.read())
    return out_file

  if algo == "gz":
    with gzip.open(out_file, "wb") as f_out:
      shutil.copyfileobj(in_fd, f_out)
    return out_file

  raise Exception("Incorrect algorithm supplied: must be [bz2|gz].")


def find_files(path: Path, exts: List[str] = ["json"]) -> Generator[Path, None, None]:
  """Return all files with the given extensions in exts."""
  # for root, dirs, files in walk(path):
  #   for f in files:
  #     if Path(f).suffix == ext
  for ext in exts:
    for f in Path(path).rglob(fr'*.{ext}'):
      yield f


def read_file(filepath) -> Generator[str, None, None]:
  with open(filepath, "r") as f:
    for _id in f.readlines():
      yield _id


YT_ID_RE = re.compile(yt_recording_file_pattern, re.IGNORECASE)
TWITCH_ID_RE = re.compile(twitch_video_file_pattern, re.IGNORECASE)


def crawl_files(path: Path) -> Generator[Tuple[str, str], None, None]:
  for root, _, files in walk(path):
    for f in files:
      yield root, f


class DownloadHandler():
  name = None

  @classmethod
  def download(cls, videoId: str, kwargs) -> Optional[Path]:
    raise NotImplementedError


class YoutubeDownload(DownloadHandler):
  name = "yt-dlp"

  @classmethod
  def download(cls, videoId: str, kwargs) -> Optional[Path]:
    """Call yt-dlp on videoId. Return the path to the written file."""
    cmd = ytdl.get_cmd(videoId, cookies=None)  # use COOKIE_PATH here if needed
    cmd.insert(-1, "--skip-download")
    cmd.insert(-1, "--no-write-thumbnail")
    try:
      cmd.remove("--embed-thumbnail")
    except:
      pass
    out_path = kwargs.get("out_path")

    log.debug(f"Running download method: {cmd}, out_path: {out_path}.")

    try:
      proc = run(
        cmd, cwd=out_path, # check=True,
        capture_output=True, text=True, encoding="utf-8")
      # log.debug(f"Ran command {proc.args}. CWD: {out_path}")

      if proc.returncode != 0:
        log.warning(f"{proc.args} returned status code {proc.returncode}")
        if "members-only content" in proc.stderr:
          raise NeedCookies("Member-only content. Please use your cookies.")

        log.debug(f"STDERR:\n{proc.stderr}")
        raise Exception(f"Status code: {proc.returncode}")

      for line in proc.stdout.splitlines():
        if "Writing video subtitles to:" in line:
          filename = line.split(":")[-1].strip()
          return Path(filename)
        if "Video subtitle live_chat.json is already present" in line:
          raise AlreadyPresentError()

    except CalledProcessError as e:
      log.exception(e)


class TwitchDownload(DownloadHandler):
  name = "TwitchDownloaderCLI"

  @classmethod
  def download(cls, videoId: str, kwargs) -> Optional[Path]:
    if not videoId:
      raise Exception(f"No videoId submitted: {videoId}")
    
    cmd = twitch.get_subs_cmd(videoId, kwargs)
    out_path = kwargs.get("out_path")

    log.debug(f"Running command: {cmd}, out_path: {out_path}")

    proc = run(
      cmd, cwd=out_path, # check=True,
      capture_output=True, text=True, encoding="utf-8")

    if proc.returncode != 0:
      log.warning(f"{proc.args} returned status code {proc.returncode}")
      if proc.returncode == -6 and "(404) Not Found." in proc.stderr:
        raise NotAvailableAnymore("404 not found!")
      
      log.debug(f"STDERR:\n{proc.stderr}")
      raise Exception(f"Status code: {proc.returncode}")

    # Last item should be the output filename
    
    return out_path / Path(cmd[-1]) if out_path is not None else Path(cmd[-1])


class CacheFile():
  def __init__(self, path: Path) -> None:
    self.path = path
    self.already_existed = True
    if not path.exists():
      self.already_existed = False
      path.touch()

  def write(self, data, mode="a"):
    with open(self.path, mode) as f:
      f.write(data)

  def load_lines(self) -> List[str]:
    with open(self.path, 'r') as f:
      found = []
      for line in f.readlines():
        line = line.strip()
        if not line:
          continue
        found.append((
          # Append without path data (although we could save those to disk too)
          line, [])
        )
    return found

  def __del__(self):
    log.debug(f"Closing cache file handle {self.path}.")
    if self.path.exists() and self.path.stat().st_size == 0:
      log.debug(f"Removing empty {self.path}.")
      self.path.unlink(missing_ok=True)


class ProcessHandler():
  cached_name = "subs_to_download.txt"
  cached_fail_name = "subs_failed.txt"
  service_name = ""

  def __init__(self, *args, **kwargs) -> None:
    self.regex: BaseRegex = kwargs['regex']
    self.cache: CacheFile = kwargs['cache']
    self.failed_cache: CacheFile = kwargs['failed_cache']
    self.downloader: DownloadHandler = kwargs['downloader']
    self._to_download = None
    self._failed_download = None
  
  # def __del__(self):
  #   if self._to_download:
  #     log.warning(f"Some files were still awaiting download: {self._to_download}!")

  @property
  def to_download(self) -> List[Tuple[str, List[Path]]]:
    if self._to_download is not None:
      return self._to_download

    ids = self.regex.store
    self._to_download = [
      (_id, ids[_id][0]) 
      for _id in ids.keys() 
      if len(ids[_id][1]) == 0
    ]
    return self._to_download

  def _prepare_args(
    self, videoId: str, paths: List[Path], out_path: Optional[Path]) -> Dict:
    if len(paths) > 1:
      log.warning(
        f"There was more than one file with videoId \"{videoId}\": "
        f"{', '.join(str(p) for p in paths)}. "
        f"Downloaded file will be placed in the first path: {str(paths[0])}."
      )
    _path = paths[0] if len(paths) > 0 else None
    
    # Determine the output directory for the subtitle file
    _out_path = out_path
    if _path is not None:
      _out_path = _path.parent if out_path is not None else out_path
    args = {
      "source_path": _path,
      "out_path": _out_path
    }
    return args

  def download(
    self, 
    compression: str, 
    out_path: Optional[Path] = None) -> Tuple[List[Path], List[Path], List[str]]:
    
    # Load caches from disk if they exist
    if self.cache.already_existed:
      self._to_download = self.cache.load_lines()
      log.debug(
        f"Loaded from {self.cache.path.name} "
        f"_to_download: {self._to_download}")

    if self.failed_cache.already_existed:
      self._failed_download = self.cache.load_lines()
      log.debug(
        f"Loaded from {self.failed_cache.path.name} "
        f"_failed_download: {self._failed_download}")

    # Overwrite todo list of videoIds to disks
    with open(self.cache.path, 'w') as f:
      if self._failed_download:
        for _id in (entry[0] for entry in self.to_download 
                  if entry[0] not in self._failed_download):
          f.write(_id + "\n")
      else:
        for entry in self.to_download:
          f.write(entry[0] + "\n")

    # for each videoId, download subs in the same directory
    did_fail = []
    did_download = []
    did_compress = []
    for _id, _paths in self.to_download:
      args = self._prepare_args(videoId=_id, paths=_paths, out_path=out_path)
      _out_path = args.get("out_path")

      try:
        # written = self.downloader.download(_id, out_path=_out_path)
        written = self.downloader.download(_id, args)

        if not written:
          log.warning(
            f"Could not get filename written by {self.downloader.name} "
            "from its stdout.")
          continue
        did_download.append(_id)

        written = _out_path / written if _out_path is not None else Path() / written
        print(f"Written file: \"{written}\".")

        compressed = compress(written, in_fd=None, algo=compression, 
                              on_success="remmmmmmove?")
        if compressed:
          did_compress.append(compressed)
      except AlreadyPresentError:
        log.warning(
          f"File {_out_path} was already present according to {self.downloader.name}.")
      except NotAvailableAnymore as e:
        log.warning(f"VideoId {_id} is not available anymore: {e}")
        did_fail.append(_id)
        self.failed_cache.write(_id + "\n")
      except Exception as e:
        log.exception(e)
        did_fail.append(_id)
        self.failed_cache.write(_id + "\n")
      
    # Flush remaining downloads to disk if any
    if self.to_download:
      with open(self.cache.path, 'w') as f:
        for _id, _ in self.to_download:
          if _id not in did_fail and _id not in did_download:
            f.write(_id + "\n")

    return did_download, did_compress, did_fail


class YoutubeHandler(ProcessHandler):
  cached_name = "yt_" + ProcessHandler.cached_name
  cached_fail_name = "yt_" + ProcessHandler.cached_fail_name
  service_name = "Youtube"

  def __init__(self) -> None:
    super().__init__(
      regex=YoutubeRegex(), 
      cache=CacheFile(Path(self.cached_name)), 
      failed_cache=CacheFile(Path(self.cached_fail_name)), 
      downloader=YoutubeDownload()
    )


class TwitchHandler(ProcessHandler):
  cached_name = "twitch_" + ProcessHandler.cached_name
  cached_fail_name = "twitch_" + ProcessHandler.cached_fail_name
  service_name = "Twitch"

  def __init__(self) -> None:
    super().__init__(
      regex=TwitchRegex(), 
      cache=CacheFile(Path(self.cached_name)), 
      failed_cache=CacheFile(Path(self.cached_fail_name)), 
      downloader=TwitchDownload()
    )

  def _prepare_args(self, videoId, paths, out_path) -> Dict:
    # Method override to add the date
    args = super()._prepare_args(videoId, paths, out_path)
    if _path := args.get("source_path"):
      # Grab the first 8 characters in the filename, which *should* be the date
      _date = str(_path.name)[:8]
      if not _date.isnumeric():
        log.warning(f"Invalid date \"{_date}\"in twitch filename \"{_path}\".")
        return args
      args["date"] = _date
    return args


# cf. https://stackoverflow.com/questions/898669
textchars = bytearray({7,8,9,10,12,13,27} | set(range(0x20, 0x100)) - {0x7f})
is_binary_string = lambda bytes: bool(bytes.translate(None, textchars))


def compress_subs(supplied_path: Path, compression: str
) -> Generator[Optional[Path], None, None]:
  """Find json sub files and compress them."""
  # Gather all json files
  files = find_files(path=supplied_path, exts=["json"])
  for f in files:
    # Make sure it's a text file
    with open(f, "rb") as fd:
      if is_binary_string(fd.read(1024)):
        log.warning(f"{f} seems to be a binary file. Skipping.")
        continue
      # Have to rewind the cursor after reading the first chunk!
      fd.seek(0)
      try:
        yield compress(f, fd, algo=compression, on_success="NOTHING")
      except Exception as e:
        log.exception(e)


def parse_args(args):
  parser = argparse.ArgumentParser(
    description='Download subtitles, or compress subtitles already present on disk.')
  parser.add_argument(
    '--mode', metavar='MODE', type=str,
    help='download or compress', required=True, choices=["download", "compress"])
  parser.add_argument(
    '--compression', metavar='ALGO', type=str, choices=["bz2", "gz"], default="bz2",
    help='Type of compression to use')
  parser.add_argument(
    '--service', metavar='SERV', type=str, 
    choices=["youtube", "twitch", "all"], default="all",
    help='Services to scrape for.')
  parser.add_argument(
    '--output-path', metavar='OUTPATH', type=str, default=None,
    help='A directory where to put all downloaded subtitles.')
  parser.add_argument(
    'path', metavar='PATH', type=str,
    help='Path where to look up for files. This can be a directory in which case'
      ' we will scan for missing subtitle files. If this is a text file, each '
      'line holds a videoId that will be downloaded in the current durectory.')
  pargs = parser.parse_args(args)
  return pargs


def main(args=None) -> int:
  pargs = parse_args(args)

  supplied_path = Path(pargs.path)
  if not supplied_path.exists():
    log.warning("Supplied path doesn't exist.")
    return 1

  if pargs.mode == "download":
    output_path = Path(pargs.output_path) if pargs.output_path is not None \
    else Path()

    if output_path.is_file():
      log.warning(
        f"{output_path} is an existing file. Will output to current working dir instead.")
      output_path = Path()

    services = []
    if pargs.service == "youtube":
      services.append(YoutubeHandler())
    elif pargs.service == "twitch":
      services.append(TwitchHandler())
    else:  # all
      # It's importa that twitch is first because youtube's regex is greedier
      # and returns too many false positives
      services = [TwitchHandler(), YoutubeHandler()]

    for root, f in crawl_files(supplied_path):
      for search in services:
        if search.regex.match(root, f):
          log.debug(f"{search.service_name} videoId found for {f}.")
          # Optimization: we had a match, skip any other lookup
          break
        else:
          log.debug(f"No {search.service_name} videoId found for {f}.")

    for search in services:
      print(f"Found {len(search.to_download)} {search.service_name} videoIds to download: ")
      for i, _ in search.to_download:
        print(i)
      log.debug(
        f"{len(search.regex.store.keys())} files found by regexes: "
        f"{search.regex.store}.")
      log.debug(f"{search.service_name} videoIds to download: {search.to_download}.")
      
      # # DEBUG
      # continue
      
      downloaded, compressed, failed = search.download(
        compression=pargs.compression, out_path=output_path)

      print(f"Successfully downloaded {len(downloaded)} / "
            f"{len(search.to_download)} subtitle files.")

      if len(failed) > 0:
        print("Failed getting subtitles for these ids:")
        for fail in failed:
          print(fail)

      if len(downloaded) != len(compressed):
        print("Subs that failed to compress:")
        for s in [_s for _s in downloaded if _s not in compressed]:
          print(s)

  elif pargs.mode == "compress":
    for c in compress_subs(supplied_path, compression=pargs.compression):
      if c is not None:
        log.info(f"Written {c}")
  return 0

if __name__ == "__main__":
  logging.basicConfig()
  exit(main())
