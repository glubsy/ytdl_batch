#!/bin/env python3
#
# Create a list of Youtube video IDs from playboard.co for example: 
# grep --color=never -rioP 'href="/en/video/(.*){11}"' computed_page.html | sed -n -r 's#.*href="/en/video/([^"]*).*#\1#p' > video_ids_reversed.txt
# tac video_ids_reversed.txt > video_ids.txt
#

from subprocess import run
from os.path import expanduser, exists
from typing import Union
from pathlib import Path

ids_todo = []
ids_done = set()
ids_failed = set()
COOKIE_PATH = expanduser("~/Cookies/firefox_cookies.txt")

SFX = {
    "FAILED": expanduser(
        "~/Music/sfx/242503__gabrielaraujo__failure-wrong-action.wav"),
    "WARNING": expanduser(
        "~/Music/sfx/350860__cabled-mess__blip-c-07.wav"),
    "SUCCESS": expanduser(
        "~/Music/sfx/256113_3263906-lq.ogg")
}
YTDL = expanduser("~/INSTALLED/yt-dlp/yt-dlp.sh") # or "yt-dlp"

for var in (YTDL, COOKIE_PATH):
    pvar = Path(var)
    if not pvar.exists():
        print(f"Error: could not find \"{var}\". Edit the variable")
        if var is YTDL:
            exit(1)

def play_sound(key: str) -> None:
    """snd_path is a key in SFX dict."""
    snd_pathstr = SFX.get(key, None)
    if not snd_pathstr:
        # invalid key
        return

    snd_path = Path(snd_pathstr)
    if not snd_path.exists():
        # File specified does not exist on disk
        print(f"NOTIFICATION: {key}")
        return
    run(['paplay', str(snd_path)])


def load_from_file(fpath: str, add_to: Union[list, set]) -> None:
    if not exists(fpath):
        return
    with open(fpath, 'r') as f:
        if isinstance(add_to, list):
            for line in f:
                add_to.append(line.strip())
        else:
            for line in f:
                add_to.add(line.strip())

def main():
    load_from_file("video_ids.txt", ids_todo)
    load_from_file("done.log", ids_done)
    load_from_file("failed.log", ids_failed)

    ids = [
        _id for _id in ids_todo 
        if _id not in ids_done and _id not in ids_failed
    ]

    if len(ids) == 0:
        print("All videos already processed. Nothing to do.")
        print(f"Done: {len(ids_done)}, Failed: {len(ids_failed)}, Total: {len(ids)}")
        exit(0)

    print(f"Loaded Done videos: {len(ids_done)}, "
           f"Failed: {len(ids_failed)}, "
           f"Remaining todo: {len(ids)}"
        )

    for _id in ids:
        cmd = [
            YTDL, "-vv", 
            "--embed-thumbnail", 
            # "--concurrent-fragments", "2",
            "--throttled-rate", "3000", # extract video data again under this rate
            "--fragment-retries", "50",
            "--abort-on-unavailable-fragment",
            # "-k",
            "-o", "%(upload_date)s %(uploader)s %(title)s_[%(height)s]_%(id)s.%(ext)s",
            "-ciw", 
            # "--cookies", COOKIE_PATH,
            # "-f", "133+251",
            "-f", 'bestvideo[vcodec^=avc1]+bestaudio',
            "-S", '+res:240,res:360,vcodec:avc01', # filter: prefer 240p, otherwise 360p, h264 video codec
            # "--external-downloader", "aria2c", "--external-downloader-args", "-c -j 3 -x 3 -s 3 -k 1M",
            "--add-metadata",
            "--write-subs",
            "--sub-langs", "live_chat",
            "--convert-subs", "srt", # Json live_chat does not work currently
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
            with open("failed.log", "a") as fe:
                print(f"Adding \"{_id}\" to failed.log.")
                fe.write(_id + "\n")
            continue

        with open("done.log", 'a') as f:
            f.write(_id + "\n")
        print(f"------------ {ids.index(_id) + 1}/{len(ids) + 1} ------------------\n")
        play_sound("SUCCESS")

if __name__ == "__main__":
    main()
        
