from typing import Optional
from subprocess import DEVNULL, run
from pathlib import Path
from os.path import expanduser
import logging


def find_program(default_proc: str, path: Optional[str]) -> Optional[str]:
  """
  Check whether default_proc is available in PATH. If it is not, try to lookup
  at *path* and return if found, otherwise return None.
  """
  if not path:
    which = run(
      ['which', default_proc], check=False,
      capture_output=False, stdout=DEVNULL, stderr=DEVNULL
    )
    if not which.returncode == 0:
      raise Exception(
        f"`which {default_proc}` returned exit code {which.returncode}, "
        "and did not find the specified program.")
    return default_proc

  ppath = Path(expanduser(path))
  if ppath.exists():
    logging.info(f"Using process specified in ENV: \"{ppath}\".")
    return str(ppath)

  raise Exception(f"\"{ppath}\" does not exist.")
