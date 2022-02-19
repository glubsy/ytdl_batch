#!/bin/env python3
from os import walk
from collections import defaultdict
import re
from pathlib import Path
from typing import DefaultDict, Optional, List, Dict, Generator, Tuple, Any
import argparse
import gzip
import bz2
import shutil
import fileinput
import logging
from ytdl import get_cmd
from constants import COOKIE_PATH, recording_file_pattern, sub_exts
from subprocess import run, CalledProcessError

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class AlreadyPresentError(Exception):
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


def download(videoId: str, out_path: Optional[Path] = None) -> Optional[Path]:
  """Call yt-dlp on videoId. Return the path to the written file."""
  cmd = get_cmd(videoId, cookies=None)  # use COOKIE_PATH here if needed
  cmd.insert(-1, "--skip-download")
  cmd.insert(-1, "--no-write-thumbnail")
  try:
    cmd.remove("--embed-thumbnail")
  except:
    pass
  try:
    proc = run(
      cmd, cwd=out_path, # check=True,
      capture_output=True, text=True, encoding="utf-8"
    )

    log.debug(f"Ran command {proc.args}. CWD: {out_path}")

    if proc.returncode != 0:
      log.warning(f"{proc.args} returned status code {proc.returncode}")
      log.debug(f"STDERR:\n{proc.stderr}")

    for line in proc.stdout.splitlines():
      if "Writing video subtitles to:" in line:
        filename = line.split(":")[-1].strip()
        return Path(filename)
      if "Video subtitle live_chat.json is already present" in line:
        raise AlreadyPresentError()

  except CalledProcessError as e:
    log.exception(e)



def read_file(filepath) -> Generator[str, None, None]:
  with open(filepath, "r") as f:
    for _id in f.readlines():
      yield _id


YT_ID_RE = re.compile(recording_file_pattern, re.IGNORECASE)


def find_if_videoid(path: Path) -> DefaultDict[str, Tuple[List[Path], List[Path]]]:
  """
  Gather files that have a youtube ID in their filename; if it is a subtitle
  file, add it to a hashmap indexed by videoIds. The videoIds without a Path
  in their key means that no subtitle file was found for it.
  """
  # Each videoId (key) found holds two lists:
  # one for the video/media files found, the second for the subtitles found:
  ids: DefaultDict[str, Tuple[List[Path], List[Path]]] = defaultdict(lambda: ([],[]))
  _re = YT_ID_RE
  for root, _, files in walk(path):
    for f in files:
      match = _re.match(f)
      if match:
        if len(match.groups()) != 2:
          log.warning(f"Failed to match second capture group for {f}: {match}.")
          continue
        _id = match.group(1)
        # add to the list of media files or the list of subtitles
        ids[_id][1 if match.group(2) in sub_exts else 0].append(Path(Path(root) / Path(f)))
  return ids


# def download_subs_from_file(supplied_file: Path):
#   """Read the given file and download subs for each videoId in it."""
#   failed = []
#   if supplied_file.is_file():
#     log.info("Supplied path is a file. Reading it for videoIds...")
#     for _id in read_file(supplied_file):
#       try:
#         download(_id)
#       except Exception as e:
#         log.exception(e)
#         failed.append(_id)
#     if failed:
#       log.warning(f"Failed downloading subs for these:")
#       for fail in failed:
#         log.warning(fail)
#     return


def download_subs(
  supplied_path: Path, compression: str, out_path: Optional[Path] = None
) -> Tuple[List[Path], List[Path], List[str]]:
  """
  Find videos without a sub file, then call yt-dlp to download.
  Return a tuple of (successful download, successful compression, failed ids)
  """
  if not supplied_path.is_file():
    # Find all files with a youtubeID on disk, and for each file,
    # check if the same filename with .live_chat.json[.gzip] exists
    # if not, add them to list
    ids = find_if_videoid(supplied_path)

    # Write found IDs with missing subs to a file (in case we want to pause and resume later)
    to_download = [
      (_id, ids[_id][0]) for _id in ids.keys() if len(ids[_id][1]) == 0
    ]

    cache_file_name = "subtitles_to_download.txt"
    with open(cache_file_name, 'w') as f:
      for _id, _ in to_download:
        f.write(_id + "\n")
    # This is used to update the file on success (similar to a pop)
    cached = fileinput.input(cache_file_name, inplace=True, backup='.bak')

  else:
    cache_file_name = supplied_path
    cached = fileinput.input(cache_file_name, inplace=True, backup='.bak')
    to_download = []
    for line in cached:
      _id = line.strip()
      # We don't record any path to the file, only videoIds
      to_download.append((_id, ()))

  print(f"Found {len(to_download)} videoIds with missing subtitle files.")

  # for each videoId, download subs in the same directory
  did_fail = []
  did_download = []
  did_compress = []
  for _id, _paths in to_download:
    if len(_paths) > 1:
      log.warning(
        f"There was more than one file with videoId {_id}: "
        f"{', '.join(str(p) for p in _paths)}. "
        f"Downloaded file will be placed in the first path: {str(_paths[0])}."
      )

    # Determine the output directory for the subtitle file
    _path = _paths[0] if len(_paths) > 0 else None
    _out_path = out_path
    if _path is not None:
      _out_path = _path.parent if out_path is not None else out_path
    try:
      written = download(_id, out_path=_out_path)
      # Remove id from cache file
      for line in cached:
        if line.strip() == _id:
          del line
          break  # we know we have unique ids since we used a hashmap

      if not written:
        log.warning("Somehow could not get filename written by yt-dlp from its stdout.")
        continue
      did_download.append(_id)

      written = _out_path / written if _out_path is not None else Path() / written
      print(f"Written file: \"{written}\".")

      compressed = compress(written, in_fd=None, algo=compression, on_success="remmmmmmove?")
      if compressed:
        did_compress.append(compressed)
    except AlreadyPresentError:
      log.warning(f"File {_out_path} was already present according to yt-dlp.")
    except Exception as e:
      log.exception(e)
      did_fail.append(_id)

  cached.close()
  return did_download, did_compress, did_fail

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
    output_path = Path(pargs.output_path) if pargs.output_path is not None else Path()

    if output_path.is_file():
      log.warning(
        f"{output_path} is an existing file. Will output to current working dir instead.")
      output_path = Path()

    downloaded, compressed, failed = download_subs(
      supplied_path, compression=pargs.compression, out_path=output_path
    )

    print(f"Successfully downloaded {len(downloaded)} subtitle files.")

    if len(failed) > 0:
      log.warning("Failed getting subtitles for these ids:")
      for fail in failed:
        log.warning(fail)

    if len(downloaded) != len(compressed):
      log.warning("Subs that failed to compress:")
      for s in [_s for _s in downloaded if _s not in compressed]:
        log.warning(s)

  elif pargs.mode == "compress":
    for c in compress_subs(supplied_path, compression=pargs.compression):
      if c is not None:
        log.info(f"Written {c}")
  return 0

if __name__ == "__main__":
  logging.basicConfig()
  exit(main())
