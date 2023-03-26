from typing import Optional
from subprocess import DEVNULL, run
from pathlib import Path
from os.path import expanduser


def find_program(default_proc: str, path: Optional[str]) -> Optional[str]:
  """
  Check whether default_proc is available in PATH. If it is not, try to lookup
  at *path* and return if found, otherwise return None.
  """
  if not path:
    proc = run(
      ['which', default_proc], check=False,
      capture_output=False, stdout=DEVNULL, stderr=DEVNULL
    )
    if not proc.returncode == 0:
      print(
        f"`which {default_proc}` returned exit code {proc.returncode}, "
        "and did not find it.")
      return None 
    return default_proc

  ppath = Path(expanduser(path))
  if ppath.exists():
    print(f"Using process specified in ENV: \"{ppath}\".")
    return str(ppath)
  else:
    print(f"\"{ppath}\" does not exist.")
  return None
