#!/bin/env python3
#
# Usage: $0 video_ids.txt
#
# Create a list of Youtube video IDs from playboard.co for example (by copying the root html element):
# grep --color=never -rioP 'href="/en/video/(.*){11}"' computed_page.html | sed -n -r 's#.*href="/en/video/([^"]*).*#\1#p' > video_ids_reversed.txt
# tac video_ids_reversed.txt > video_ids.txt

from os import getenv
from subprocess import run, DEVNULL
from sys import argv
from os.path import expanduser, exists
from typing import Union
from pathlib import Path
from platform import python_version_tuple

py_ver_tuple = python_version_tuple()

ids_todo = []
ids_done = set()
ids_failed = set()
ids_deleted = set()

# Could also use --cookies-from-browser BROWSER[:PROFILE] with yt-dlp
COOKIE_PATH = expanduser("~/Cookies/firefox_cookies.txt")

SFX = {
    "FAILED": expanduser(
        "~/Music/sfx/242503__gabrielaraujo__failure-wrong-action.wav"),
    "WARNING": expanduser(
        "~/Music/sfx/350860__cabled-mess__blip-c-07.wav"),
    "SUCCESS": expanduser(
        "~/Music/sfx/256113_3263906-lq.ogg")
}

YTDLP_NAME = "yt-dlp"

# One can set the environment variable "YTDL" to point to yt-dlp (before calling the script)
YTDL_PATH = getenv("YTDL")
if YTDL_PATH:
    YTDL_PATH = expanduser(YTDL_PATH)
    YTDL_PATH_P = Path(YTDL_PATH)
    if not YTDL_PATH_P.exists:
        print(f"{YTDL_PATH_P} does not exist.")
        exit(1)
else:  # If not found, try to look it up in $PATH
    proc = run(
        ['which', YTDLP_NAME], check=False,
        capture_output=False, stdout=DEVNULL, stderr=DEVNULL
    )
    if not proc.returncode == 0:
        print(
            f"`which {YTDLP_NAME}` returned exit code {proc.returncode}, "
            "and did not find it."
        )
        exit(1)

    YTDL_PATH = YTDLP_NAME


for var in (COOKIE_PATH,):
    pvar = Path(var)
    if not pvar.exists():
        print(f"Error: could not find \"{var}\". Edit the variable")


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
                add_to.append(line.strip())
        else:
            for line in f:
                add_to.add(line.strip())


def main():
    id_list_file = Path(argv[1])

    # FIXME Temporary backport
    if int(py_ver_tuple[1]) < 9: 
        print(f"Python version is {py_ver_tuple}. Using backport workaround.")
        def with_stem(path: Path, stem: str):
            """Return a new path with the stem changed."""
            return path.with_name(stem + path.suffix)

        done_list = with_stem(id_list_file, id_list_file.stem + "_done")
        failed_list = with_stem(id_list_file, id_list_file.stem + "_failed")
        deleted_list = with_stem(id_list_file, id_list_file.stem + "_deleted")
    else:
        done_list = id_list_file.with_stem(id_list_file.stem + "_done")
        failed_list = id_list_file.with_stem(id_list_file.stem + "_failed")
        # This holds a list of IDs we know for sure have been deleted.
        # It is curated by the user, usually updated from the _failed log.
        deleted_list = id_list_file.with_stem(id_list_file.stem + "_deleted")

    if not id_list_file.exists():
        print(f"File \"{id_list_file}\" does not exist.")
        exit(1)

    load_from_file(id_list_file, ids_todo)
    load_from_file(done_list, ids_done)
    load_from_file(failed_list, ids_failed)
    load_from_file(deleted_list, ids_deleted)

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
        cmd = [
            str(YTDL_PATH), "-v",
            "--embed-thumbnail",
            # "--concurrent-fragments", "2",
            "-N", "4",
            "-4",
            #"--extractor-args", "youtube:player_client=android", "--sleep-interval", "5",
            #"--throttled-rate", "3000", # extract video data again under this rate
            "--fragment-retries", "50",
            "--abort-on-unavailable-fragment",
            # "-k",
            "-o", "%(upload_date)s %(uploader)s %(title)s_[%(height)s]_%(id)s.%(ext)s",
            "-ciw",
            #"--cookies", COOKIE_PATH,
            # "-f", "133+251",
            "-f", 'bestvideo[vcodec^=avc1]+bestaudio',
            "-S", '+res:240,res:360,vcodec:avc01', # filter: prefer 240p, otherwise 360p, h264 video codec
            # "--external-downloader", "aria2c", "--external-downloader-args", "-c -j 3 -x 3 -s 3 -k 1M",
            "--add-metadata",
            "--write-subs",
            "--sub-langs", "live_chat",
            #"--convert-subs", "srt", # Json live_chat does not work currently
            "--embed-subs",
            "--remux-video", "mkv",
            r"https://www.youtube.com/watch?v=" +_id
        ]
        try:
            # TODO capture (and pipe) output and report on
            # "[download] Skipping fragment 123 ..."
            print("Running command: {}".format(" ".join(cmd)))
            run(cmd, check=True)
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
    main()
