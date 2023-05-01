#!/bin/env python3
#
# To create a list of Youtube video IDs from playboard.co by copying the root 
# html element, then use:
# grep --color=never -rioP 'href="/en/video/(.*){11}"' computed_page.html | sed -n -r 's#.*href="/en/video/([^"]*).*#\1#p' > video_ids_reversed.txt
# tac video_ids_reversed.txt > video_ids.txt
#
# TODO Fetch videos from Youtube and compare with what playboard returns (could 
# use yt-dlp to generate archive.txt without downloading for example)

from sys import argv
from typing import List, Tuple
from urllib.request import Request, urlopen
from urllib.parse import urlencode, quote, urlparse
import json
import gzip
from io import BytesIO
import logging
from datetime import datetime
log = logging.getLogger(__name__)
logging.basicConfig()
# log.setLevel(logging.DEBUG)

BASE_URL = "https://api.playboard.co/v1/"
PATH = "search"
TYPE = "video"
ENDPOINT = f"{BASE_URL}{PATH}/{TYPE}"

HEADERS = {
  "origin": "https://playboard.co",
  "referer": "https://playboard.co/",
  "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"
  "accept" "application/json, text/plain, */*",
  "accept-encoding": "gzip, deflate, br",
  "accept-language": "en,en-US",
  "content-type": "application/json"
}


def req(url, params, headers=None, method="POST", data=None):
  """Just an alternative method with the Requests module."""
  import requests
  headers = HEADERS if headers is None else headers
  # req = requests.Request(method=method, url=url, headers=headers)
  res = requests.post(url, data=None, headers=headers, params=params)
  return res.json()


def do_request(url, headers=None, method="POST", data=None):
  headers = HEADERS if headers is None else headers
  req = Request(
    url,
    headers=HEADERS,
    data=data,
    method=method
  )
  log.debug(f"req: {req.full_url} {req.headers}")
  with urlopen(req) as res:
    if res.headers.get("content-encoding") == "gzip":
      content = gzip.decompress(res.read())
      return json.load(BytesIO(content))

    content = str(res.read().decode())
    log.debug(f"data: {content}")
    return json.loads(content)


def get_videos_for_channel(channel_id: str) -> List[Tuple[str, int]]:
  # Each tuple returned has (videoId, status)
  vids = []
  has_next = True
  cursor = None
  params = {
    "channelId": channel_id,
    "sortTypeId": "10",
  }
  print("Found videoIds:")

  while has_next:
    if cursor is not None:
      params.update({"cursor": cursor})

    url = ENDPOINT + (('&' if urlparse(ENDPOINT).query else '?') + urlencode(params, quote_via=quote))
    _json = do_request(url=url)
    # _json = req(url=ENDPOINT, params=urlencode(params, quote_via=quote))

    has_next = _json.get("hasNext")
    cursor = _json.get("cursor")
    for vid in _json.get("list"):
      print(
        f"{vid['videoId']}"
        + (' (deleted)' if vid.get('status') == 2 else "")
      )
      vids.append(
        (vid["videoId"], vid.get("status"))
      )

  return vids


def main(channel_id: str):
  videos = get_videos_for_channel(channel_id)

  # "2" seems to indicate removed?, "1" and "3" appear to be the same?
  possibly_removed = [v for v,s in videos if s == 2]

  print(f"Found {len(videos)} IDs, among which {len(possibly_removed)} "
        "are advertised as being deleted.")

  date = datetime.now().strftime("%d%m%Y_%H-%M-%S")
  videos_file = f"playboard_ids_{channel_id}_{date}.txt"

  with open(videos_file, "w") as f:
    for _id, _ in videos:
      f.write(_id + "\n")

  if possibly_removed:
    deleted_file = f"playboard_ids_{channel_id}_deleted_{date}.txt"
    with open(deleted_file, "w") as f:
      for _id in possibly_removed:
        f.write(_id + "\n")


if __name__ == "__main__": 
  main(argv[1])
