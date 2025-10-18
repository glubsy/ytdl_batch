from subprocess import run
from sys import argv
from typing import List, Tuple
import re 
import logging
from regex import yt_video_file_pattern
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
logging.basicConfig()


YT_ID_RE = re.compile(yt_video_file_pattern, re.IGNORECASE)
log.debug(f"videoId regular expression: {YT_ID_RE}")


def find_youtube_id(file_list: list):
  ids = []  # a list, not a set to keep the order resulting from the file list
  miss = []
  dupes = []
  for fname in file_list:
    match = YT_ID_RE.match(fname)
    if match:
      group = match.group(1)
      if group in ids:
        log.warning(f"ID \'{group}\' from \'{fname}\' was already found.")
        dupes.append(fname)
      else:   
        ids.append(group)
    else:
      log.info(f"Did not match regex: {fname}")
      miss.append(fname)
  return ids, miss, dupes


def sort_output(output: str) -> Tuple[List[str], int]:
  """Takes the string output of find, split by newline and sort."""
  line_count = 0
  filenames = []
  for line in output.split('\n'):
    line = line.rstrip()
    if len(line) > 0:
      line_count += 1
      filenames.append(line)
  # Sorting, hoping that the first element of the filename is a YYYYMMDD date:
  # TODO use our own sorting method to match any date format in the string
  filenames.sort()
  for fname in filenames:
    log.debug(f"Sorted: {fname}")
  return filenames, line_count


def run_find(target_path) -> str:
  """Run find on target_path for files by extensions, return the output as a string."""
  cmd = [
    "find", target_path, 
    # "-type", "f", r"\(", "-iname", "'*.mkv'", "-o", "-iname", "'*.mp4'", "-printf", r"\)", r"%f\n", 
    "-type", "f", 
    "-iregex", r'.*\.\(mkv\|mp4\|opus\|m4a\|webm\)', "-printf", r"%f\n",
    # "|", "sed", "-n", r's/^.*\][\s_]\?\(.*\)\..\{3,4\}$/\1/p'
  ]

  log.debug(f"command to run: {cmd}")

  proc = run(
    cmd,
    # shell=True,
    check=False,
    capture_output=True, # stdout=DEVNULL, stderr=DEVNULL
    # stdout=PIPE,
    text=True
  )
  return proc.stdout


def main(target_path):
  """
  Crawl files in the given directory and return a set of Youtube videoIds 
  taken from their filenames. Write them to file.
  """
  filenames, count = sort_output(run_find(target_path))
  print(f"Total files found by suffix: {count}")

  ids, misses, dupes = find_youtube_id(filenames)
  print(f"IDs found (most ancient at the top):")

  with open("ids_found_on_disk.txt", "w") as f:
      for _id in ids:  # reversed: ids[::-1]:
          print(_id)
          f.write("youtube " + _id + '\n')
  print(f"Total found: {len(ids)}.")

  print(f"{len(misses)} mismatched files + {len(dupes)} dupes = {len(misses) + len(dupes)} ignored files.")

  print("Files that failed to match regex:")
  for miss in misses:
    print(miss)

  print("Duplicate files according to their Id:")
  for dupe in dupes:
    print(dupe)

if __name__ == "__main__":
  main(argv[1])