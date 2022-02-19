#!/bin/env python3

from subprocess import run
from sys import argv
from os.path import exists
from typing import Union
from pathlib import Path
from ytdl import dl_ytdlp
from constants import SFX, py_ver_tuple


def play_sound(key: str) -> None:
  """snd_path is a key in SFX dict."""
  snd_pathstr = SFX.get(key, None)
  if not snd_pathstr:
    # invalid key
    return
  print(f"NOTIFICATION: {key}")

  snd_path = Path(snd_pathstr)
  if not snd_path.exists():
    return
  run(['paplay', str(snd_path)])


def load_from_file(fpath: Path, add_to: Union[list, set]) -> None:
  if not exists(fpath):
    print(f"{fpath} does not exists.")
    return
  with open(fpath, 'r') as f:
    if isinstance(add_to, list):
      for line in f:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
          continue
        if stripped not in add_to:
          add_to.append(stripped)
    else:
      for line in f:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
          continue
        add_to.add(stripped)


def main(id_list_file):
  ids_todo = []
  ids_done = set()
  ids_failed = set()
  ids_deleted = set()

  # FIXME Temporary backport
  if int(py_ver_tuple[1]) < 9: 
    print(f"Python version is {py_ver_tuple}. Using backport workaround.")
    def with_stem(path: Path, stem: str):
      """Return a new path with the stem changed."""
      return path.with_name(stem + path.suffix)

    done_list = with_stem(id_list_file, id_list_file.stem + "_done")
    failed_list = with_stem(id_list_file, id_list_file.stem + "_failed")
    deleted_list = with_stem(id_list_file, id_list_file.stem + "_deleted")
    uniqued_ids = with_stem(id_list_file, id_list_file.stem + "_total")
  else:
    done_list = id_list_file.with_stem(id_list_file.stem + "_done")
    failed_list = id_list_file.with_stem(id_list_file.stem + "_failed")
    # This holds a list of IDs we know for sure have been deleted.
    # It is curated by the user, usually updated from the _failed log.
    deleted_list = id_list_file.with_stem(id_list_file.stem + "_deleted")
    uniqued_ids = id_list_file.with_stem(id_list_file.stem + "_total")

  if not id_list_file.exists():
    print(f"File \"{id_list_file}\" does not exist.")
    exit(1)

  # TODO load a Blocked list of videos to discard
  load_from_file(id_list_file, ids_todo)
  load_from_file(done_list, ids_done)
  load_from_file(failed_list, ids_failed)
  load_from_file(deleted_list, ids_deleted)

  # Write unique ids because our user input list may have duplicates 
  with open(uniqued_ids, 'w') as f:
    for _id in ids_todo:
      f.write(_id + "\n")

  ids = [
    _id for _id in ids_todo
    if _id not in ids_done
    and _id not in ids_failed
    and _id not in ids_deleted
  ]

  if len(ids) == 0:
    print("All videos already processed. Nothing else to do.")
    print(
        f"Done: {len(ids_done)}, "
        f"Failed: {len(ids_failed)}, "
        f"Deleted: {len(ids_deleted)}, "
        f"Total: {len(ids)}"
    )
    exit(0)

  print(f"Loaded Done videos: {len(ids_done)}, "
    f"Failed: {len(ids_failed)}, "
    f"Deleted: {len(ids_deleted)}, "
    f"Remaining todo: {len(ids)}"
  )

  for _id in ids:
    try:
      # TODO capture (and pipe) output and report on
      # "[download] Skipping fragment 123 ..."
      dl_ytdlp(_id, cookies=None)  # use COOKIE_PATH here
    except Exception as e:
      play_sound("FAILED")
      print(f"ERROR. Return code: {e}; ")

      with open(failed_list, "a") as fe:
          print(f"Adding \"{_id}\" to {failed_list}")
          fe.write(_id + "\n")
      continue

    with open(done_list, 'a') as f:
        print(f"Adding \"{_id}\" to {done_list}")
        f.write(_id + "\n")

    print(f"{'=' * 20} {ids.index(_id) + 1}/{len(ids)} {'=' * 20}\n")
    play_sound("SUCCESS")


if __name__ == "__main__":
  #
  # Usage: $0 video_ids.txt
  #
  main(Path(argv[1]))
