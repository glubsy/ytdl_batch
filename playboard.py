#!/bin/env python3
#
# To create a list of Youtube video IDs from playboard.co by copying the root
# html element, then use:
# grep --color=never -rioP 'href="/en/video/(.*){11}"' computed_page.html | sed -n -r 's#.*href="/en/video/([^"]*).*#\1#p' > video_ids_reversed.txt
# tac video_ids_reversed.txt > video_ids.txt
#
# TODO Fetch videos from Youtube and compare with what playboard returns (could
# use yt-dlp to generate archive.txt without downloading for example:
# --flat-playlist Do not extract the videos of a playlist, only list them

from sys import argv
from typing import List, Mapping
from urllib.request import Request, urlopen
from urllib.parse import urlencode, quote, urlparse
import json
import gzip
from io import BytesIO
import logging
from datetime import datetime, date
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


def get_videos_for_channel(channel_id: str):
  """
  Generator of video mappings from Playboard.
  """
  has_next = True
  cursor = None
  params = {
    "channelId": channel_id,
    "sortTypeId": "10",
  }

  while has_next:
    if cursor is not None:
      params.update({"cursor": cursor})

    url = ENDPOINT + (('&' if urlparse(ENDPOINT).query else '?') + urlencode(params, quote_via=quote))
    _json = do_request(url=url)
    # _json = req(url=ENDPOINT, params=urlencode(params, quote_via=quote))

    has_next = _json.get("hasNext")
    cursor = _json.get("cursor")

    for vid in _json.get("list"):
      yield vid


def generate_lists(channel_id: str):
  print(f"Finding video Ids in Playboard for channel \"{channel_id=}\":")

  pb_videos = []

  for vid in get_videos_for_channel(channel_id):
    pb_videos.append(vid)

    title = vid.get("title")
    publishedAt = vid.get("publishedAt")
    if publishedAt is not None and type(publishedAt) is int:
      publishedAt = date.fromtimestamp(publishedAt)

    print(
      f"{vid['videoId']}"
      + ("\t(deleted)" if vid.get("status") == 2 else '')
      + (f"\tpublished={str(publishedAt)}" if publishedAt is not None else '')
      + (f"\t{title=}" if title is not None else '')
    )

  # "2" seems to indicate removed?, "1" and "3" appear to be the same?
  possibly_removed = [v["videoId"] for v in pb_videos if v["status"] == 2]

  print(
    f"Found {len(pb_videos)} IDs, among which {len(possibly_removed)} "
    "are advertised as being deleted.")

  date_fmt = datetime.now().strftime("%Y%d%m_%H-%M-%S")
  videos_file = f"playboard_ids_{channel_id}_{date_fmt}.txt"

  with open(videos_file, "w") as f:
    for _id, _ in pb_videos:
      f.write(_id + "\n")

  if possibly_removed:
    deleted_file = f"playboard_ids_{channel_id}_deleted_{date_fmt}.txt"
    with open(deleted_file, "w") as f:
      for _id in possibly_removed:
        f.write(_id + "\n")


if __name__ == "__main__":
  generate_lists(argv[1])
