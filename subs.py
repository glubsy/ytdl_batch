#!/bin/env python3
from os import walk, sep, getenv
from os.path import join as pjoin
import sys
import re
from pathlib import Path
from typing import Optional, List, Dict, Generator, Tuple, Any, Union
import argparse
import gzip
import bz2
import shutil
from pprint import pprint
# import fileinput
import logging
from subprocess import run, CalledProcessError
from regex import BaseScanner, TwitchScanner, YoutubeScanner
from downloader.twitch import TwitchDownloaderCLI
from downloader.ytdl import YTDLDownloader

log = logging.getLogger()
# log.setLevel(logging.DEBUG)

class AlreadyPresentError(Exception):
  pass

class NotAvailableAnymore(Exception):
  pass

class NeedCookies(Exception):
  pass

class NoSubsAvailable(Exception):
  pass



def compress(
  in_file: Path,
  in_fd = None,
  algo: str = "bz2",
  on_success = "remove"
) -> Optional[Path]:
  """
  Compress file pointed to by in_file. in_fd can be an open file descriptor to
  the file. out_dir is the output directory. If on_success == "remove" the
  original file will be deleted.

  Return:
  ------
  Output bz2 file path on effective compression, otherwise None.
  """
  out_file = in_file.with_suffix(in_file.suffix + f".{algo}")
  log.debug(f"Will compress {in_file.name} into {out_file.name}...")
  written = None

  if in_fd is None:
    with open(in_file, "rb") as in_fd:
      written = _compress_file(in_fd, out_file=out_file, algo=algo)
  else:   # Reuse the open file descriptor if possible
    written = _compress_file(in_fd, out_file=out_file, algo=algo)

  if written:
    if on_success == "remove" and out_file.exists():
      log.info(f"Removing original file \"{in_file}\".")
      in_file.unlink()
    return out_file
  else:
    return None


def _compress_file(in_fd, out_file: Path, algo: str) -> bool:
  """Compress in_fd into the file pointed by out_file.
  If compression has occured, return True. If out file already existed
  return False."""

  if out_file.exists():
    log.warning(f"{out_file} already exists. Skipping compression.")
    return False

  if algo == "bz2":
    with bz2.open(out_file, "wb") as f:
      # Write compressed data to file
      f.write(in_fd.read())
    return True

  elif algo == "gz":
    with gzip.open(out_file, "wb") as f_out:
      shutil.copyfileobj(in_fd, f_out)
    return True

  raise Exception("Incorrect algorithm specified: must be [bz2|gz].")


def find_files(path: Path, exts: List[str] = ["json"]) -> Generator[Path, None, None]:
  """Return all files with the given extensions in exts."""
  # for root, dirs, files in walk(path):
  #   for f in files:
  #     if Path(f).suffix == ext
  for ext in exts:
    for f in Path(path).rglob(f'*.{ext}'):
      yield f


def read_file(filepath) -> Generator[str, None, None]:
  with open(filepath, "r") as f:
    for _id in f.readlines():
      yield _id


def crawl_files(
  path: Path,
  filter_re: Optional[re.Pattern]
) -> Generator[Tuple[str, str], None, None]:
  """
  Filter out files by regex.
  """
  for root, _, files in walk(path):
    if filter_re is not None and filter_re.match(root + sep):
      continue
    for f in files:
      yield root, f


class CacheFile():
  """
  Store errors for each Id as Id\tPath.name\tError message.
  """
  def __init__(self, path: Path) -> None:
    self.path = path
    self.already_existed = True
    if not path.exists():
      self.already_existed = False
      path.touch()

  def write(self, data: str, mode='a'):
    # TODO enforce a consistent format in order to load back safely
    with open(self.path, mode) as f:
      f.write(data)

  def load_lines(self) -> Dict[str, List[Path]]:
    with open(self.path, 'r') as f:
      found = {}
      for line in f.readlines():
        line = line.strip()
        if not line:
          continue

        values = line.split('\t')
        if len(values) == 3:
          # Currently we don't care about loading errors back in
          _id, _path, _ = values
        else:
          _id, _path = values

        found[_id] = [Path(_path)]
    return found

  def __del__(self):
    log.debug(f"Closing cache file handle {self.path}.")
    if self.path.exists() and self.path.stat().st_size == 0:
      log.debug(f"Removing empty {self.path}.")
      self.path.unlink(missing_ok=True)


class ProcessHandler():
  cached_fail_name = "subs_failed.txt"
  service_name = ""
  downloader = None

  def __init__(self, *args, **kwargs) -> None:
    self.cookies: Optional[Path] = None
    if cookies := kwargs.get("cookies"):
      self.cookies = Path(cookies).expanduser()

    self.scanner: BaseScanner = kwargs["regex"]
    self.failed_cache: CacheFile = kwargs["failed_cache"]
    self._to_download: Optional[Dict] = None
    self._failed_download: Dict = {}

    if self.failed_cache.already_existed:
      self._failed_download = self.failed_cache.load_lines()
      if len(self._failed_download):
        print(
          f"Loaded {len(self._failed_download)} failed downloads from "
          f"\"{self.failed_cache.path.name}\"."
        )
        log.debug(f"Loaded failed download Ids:\n{self._failed_download}")
      else:
        print(f"No failed {self.service_name} download found from a previous run.")

  # def __del__(self):
  #   if self._to_download:
  #     log.warning(f"Some files were still awaiting download: {self._to_download}!")

  @property
  def to_download(self) -> Dict[str, List[Path]]:
    """
    Return a new dictionary with only videoIds for which no subtitle file has
    been detected.
    """
    if self._to_download is not None:
      return self._to_download

    ids = self.scanner.store
    self._to_download = dict(
      (
        (_id, ids[_id][0])
        for _id in ids.keys()
        # Only load Ids that do not have any associated subs files already (at index 1)
        if (len(ids[_id][1]) == 0 and len(ids[_id][0]) > 0)
        and _id not in self._failed_download.keys()
      )
    )
    return self._to_download

  def _prepare_args(
    self, videoId: str, paths: List[Path], out_path: Optional[Path]) -> Dict:
    if len(paths) > 1:
      log.warning(
        f"There was more than one file with videoId \"{videoId}\": "
        f"{', '.join(str(p) for p in paths)}. "
        f"Downloaded file will be placed in the first path: {str(paths[0])}."
      )
    # We default to the first path reported
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

  def _download(self, id, args):
    # virtual
    raise NotImplementedError()

  def download(
    self,
    compression: str,
    out_path: Optional[Path] = None,
    remove_compressed: bool = False
  ) -> Tuple[List[Path], List[Path], List[str]]:

    # for each videoId, download subs in the same directory
    did_fail = []
    did_download = []
    did_compress = []
    for _id, _paths in self.to_download.items():
      args = self._prepare_args(videoId=_id, paths=_paths, out_path=out_path)
      _out_path = args.get("out_path")

      print(f"Downloading subs for {_id} ({_paths[0]})...")

      try:
        # written = self.downloader.download(_id, out_path=_out_path)
        written = self._download(_id, args)

        if not written:
          log.warning(
            f"No filename written for Id {_id} by {self.downloader.default_name} "
            f"according to its stdout.")
          continue
        did_download.append(_id)

        written = Path() / written if type(written) is str else written.absolute()
        print(f"Written subtitle file: \"{written}\".")

        compressed = compress(
          written, in_fd=None, algo=compression,
          on_success="remove" if remove_compressed else "nothing"
        )
        if compressed:
          print(f"Compressed file: \"{compressed}\"")
          did_compress.append(compressed)

      except AlreadyPresentError:
        log.warning(
          f"File {_out_path} was already present according to "
          f"{self.downloader.default_name}.")
      except (NotAvailableAnymore, NoSubsAvailable, Exception) as e:
        print(f"Failed to download live chat for {_id}: {e}")
        log.warning(f"VideoId {_id} is not available anymore: {e}")
        did_fail.append(_id)
        self.failed_cache.write(_id + '\t' + str(_paths[0]) + '\t' + str(e) + "\n")

    return did_download, did_compress, did_fail


class YoutubeHandler(ProcessHandler):
  cached_fail_name = "yt_" + ProcessHandler.cached_fail_name
  service_name = "Youtube"

  def __init__(self, *args, **kwargs) -> None:
    super().__init__(
      regex=YoutubeScanner(),
      failed_cache=CacheFile(Path(self.cached_fail_name))
    )
    self.downloader = YTDLDownloader(process_path=kwargs["process_path"])
    
    self.cookies: Optional[Path] = None
    if cookies := kwargs.get("cookies"):
      self.cookies = Path(cookies).expanduser()

  def _download(self, videoId: str, kwargs) -> Optional[Path]:
    """Call yt-dlp on videoId. Return the path to the written file."""
    # use COOKIE_PATH here if needed
    cmd = self.downloader.build_cmd(
      videoId, cookies=self.cookies, skip_video=True
    )
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
          raise NeedCookies("Member-only content. Valid cookies are required.")

        log.debug(f"STDERR:\n{proc.stderr}")
        raise Exception(f"Status code: {proc.returncode}")

      for line in proc.stdout.splitlines():
        if "Writing video subtitles to:" in line:
          filename = line.split(":")[-1].strip()
          return Path(filename)
        if "Video subtitle live_chat.json is already present" in line:
          raise AlreadyPresentError()
        if "no subtitles for the requested language" in line:
          raise NoSubsAvailable("No subtitles available for the requested language.")

    except CalledProcessError as e:
      log.exception(e)


class TwitchHandler(ProcessHandler):
  cached_fail_name = "twitch_" + ProcessHandler.cached_fail_name
  service_name = "Twitch"

  def __init__(self, *args, **kwargs) -> None:    
    super().__init__(
      regex=TwitchScanner(),
      failed_cache=CacheFile(Path(self.cached_fail_name)),
    )
    self.downloader = TwitchDownloaderCLI(process_path=kwargs["process_path"])
    
    self.cookies: Optional[Path] = None
    if cookies := kwargs.get("cookies"):
      self.cookies = Path(cookies).expanduser()

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

  def _download(self, videoId: str, kwargs) -> Optional[Path]:
    if not videoId:
      raise Exception(f"No videoId submitted: {videoId}")

    cmd = self.downloader.build_cmd(videoId, kwargs)
    out_path = kwargs.get("out_path")

    log.debug(f"Running command: {cmd}, out_path: {out_path}")

    proc = run(
      cmd, cwd=out_path, # check=True,
      capture_output=True, text=True, encoding="utf-8")

    if proc.returncode != 0:
      log.warning(f"{proc.args} returned status code {proc.returncode}")
      if proc.returncode == -6 or proc.returncode == 134:
        reason = f"Return code was: {proc.returncode}"
        if "(404) Not Found." in proc.stderr:
          reason = "404 not found."
        elif "Object reference not set to an instance of an object." in proc.stderr:
          reason = "Object reference not set to an instance of an object."
        raise NotAvailableAnymore(reason)

      log.debug(f"STDERR:\n{proc.stderr}")
      raise Exception(f"Status code: {proc.returncode}")

    # Last item should be the output filename

    return out_path / Path(cmd[-1]) if out_path is not None else Path(cmd[-1])


# cf. https://stackoverflow.com/questions/898669
textchars = bytearray({7,8,9,10,12,13,27} | set(range(0x20, 0x100)) - {0x7f})
is_binary_string = lambda bytes: bool(bytes.translate(None, textchars))


def compress_subs(
  supplied_path: Path,
  compression: str,
  remove_compressed: bool
) -> Generator[Optional[Path], None, None]:
  """
  Find json sub files in supplied path and compress them all.
  """
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
        yield compress(
          f,
          fd,
          algo=compression,
          on_success=("remove" if remove_compressed else "nothing")
        )
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
    '--exclude-regex', metavar='EXCLUDE', type=str, default=None,
    help='Regex to filter out directories.')
  parser.add_argument(
    '--remove-compressed', action="store_true", default=False,
    help='Remove subtitle file after compression has succeeded.')
  parser.add_argument(
    '--cookies', metavar="COOKIES", type=str, default=None,
    help='Path to cookie file to pass to downloaders (for members-only videos).')
  parser.add_argument(
    '--log-level', metavar="LOG-LEVEL", type=str, default="WARNING",
    help='Minimum log level to justify writing to log file on disk.')
  parser.add_argument(
    '--dry-run', action="store_true",
    help='Only print what is done but do not download anything.')
  parser.add_argument(
    'path', metavar='PATH', type=str,
    help='Path where to look up for files. This can be a directory in which case'
      ' we will scan for missing subtitle files. If this is a text file, each '
      'line holds a videoId that will be downloaded in the current directory.')
  pargs = parser.parse_args(args)
  return pargs


def setup_logger(
  log_level: str = "WARNING",
  output_path: Optional[Path] = None
) -> None:
  """
  Add file handler to the global log object.
  """
  if not output_path:
    output_path = Path() / ("subs.log")

  level = getattr(logging, log_level.upper())

  # logfile = logging.FileHandler(
  #   filename=output_path, delay=True, encoding='utf-8'
  # )
  # logfile.setLevel(logging.DEBUG)
  # formatter = logging.Formatter(
  #   '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
  # )
  # logfile.setFormatter(formatter)
  # log.addHandler(logfile)
  logging.basicConfig(
    filename=output_path,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    level=level
  )
  log.setLevel(logging.DEBUG)


def main(args=None) -> int:
  pargs: argparse.Namespace = parse_args(args)
  setup_logger(log_level=pargs.log_level)

  filter_dir_re = None
  if pargs.exclude_regex:
    filter_dir_re = re.compile(pargs.exclude_regex, re.IGNORECASE)

  supplied_path = Path(pargs.path)
  if not supplied_path.exists():
    print("Supplied path doesn't exist.")
    return 1

  yt_downloader_path = getenv("YTDL")
  if not yt_downloader_path:
    print("No Youtube downloader found in env variable \"YTDL\"!")

  twitch_downloader_path = getenv("TDCLI")
  if not twitch_downloader_path:
    print("No Twitch downloader found in env variable \"TDCLI\"!")

  if pargs.mode == "download":
    output_path = Path(pargs.output_path) if pargs.output_path is not None \
    else Path()

    if output_path.is_file():
      # FIXME this file should be loaded instead!
      print(
        f"{output_path} is an existing file. Will output to current working "
        "directory instead.")
      output_path = Path()

    # HACK it is important that Twitch handler be first because Youtube's 
    # regex is greedier and would return too many false positives
    services: List[ProcessHandler] = []

    if pargs.service == "twitch" or "all":
      services.append(TwitchHandler(
        cookies=pargs.cookies, process_path=twitch_downloader_path)
      )
    if pargs.service == "youtube" or "all":
      services.append(YoutubeHandler(
        cookies=pargs.cookies, process_path=yt_downloader_path)
      )

    for root, f in crawl_files(supplied_path, filter_re=filter_dir_re):
      for search in services:
        if search.scanner.match(root, f):
          log.debug(f"{search.service_name} videoId found in {f}.")
          # Optimization: we had a match, skip any other lookup
          break
        else:
          log.debug(f"No {search.service_name} videoId found in {f}.")

    for search in services:
      print(f"Found {len(search.to_download)} {search.service_name} videoIds to download: ")
      for _id, _ in search.to_download.items():
        print(_id)

      log.debug(
        f"{len(search.scanner.store.keys())} files found by regexes: ")

      # FIXME This assumes the logger has a FileHandler
      with open(log.handlers[0].baseFilename, 'a') as f:
        # Avoid printing to stdout, only to log file instead
        original_stdout = sys.stdout
        sys.stdout = f
        pprint(search.scanner.store)
        sys.stdout = original_stdout

      log.debug(
        f"{len(search.to_download)} {search.service_name} subs to download:\n" +
        '\n'.join(f'{id}: {paths}' for id, paths in search.to_download.items())
      )

      if len(search.to_download) == 0:
        continue

      if pargs.dry_run:
        continue

      downloaded, compressed, failed = search.download(
        compression=pargs.compression,
        out_path=output_path,
        remove_compressed=pargs.remove_compressed
      )

      print(
        f"Successfully downloaded {len(downloaded)} / "
        f"{len(search.to_download)} subtitle files."
      )

      if len(failed) > 0:
        print("Failed getting subtitles for these ids:")
        for fail in failed:
          print(fail)

      if len(downloaded) != len(compressed):
        print("Subs that failed to compress:")
        for s in [_s for _s in downloaded if _s not in compressed]:
          print(s)

  elif pargs.mode == "compress":
    for c in compress_subs(
      supplied_path,
      compression=pargs.compression,
      remove_compressed=pargs.remove_compressed
    ):
      if c is not None:
        print(f"Written {c}")

  return 0

if __name__ == "__main__":
  exit(main())
