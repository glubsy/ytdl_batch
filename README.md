Various programs to automate downloading Youtube and Twitch VODs, as well as their subtitles.


# ytdl_batch.py

Download videoIds listed by `generate_list.py`

# generate_list.py

Use the playboard.co API to get a list of videoIds for a given channel. Their scraped data is useful to figure out which videos have been deleted from the targeted Youtube channel.

# Subs.py

Scan a given directory for Youtube and Twitch video files (looking for Id in file names) and download subtitles for each found video.

```shell
usage: subs.py [-h] --mode MODE [--compression ALGO] [--service SERV] [--output-path OUTPATH] [--exclude-regex EXCLUDE] [--remove-compressed] [--cookies COOKIES] [--log-level LOG-LEVEL] PATH

Download subtitles, or compress subtitles already present on disk.

positional arguments:
  PATH                  Path where to look up for files. This can be a directory in which case we will scan for missing subtitle files. If this is a text file, each line holds a videoId that will be downloaded in the current
                        directory.

options:
  -h, --help            show this help message and exit
  --mode MODE           download or compress
  --compression ALGO    Type of compression to use
  --service SERV        Services to scrape for.
  --output-path OUTPATH
                        A directory where to put all downloaded subtitles.
  --exclude-regex EXCLUDE
                        Regex to filter out directories.
  --remove-compressed   Remove subtitle file after compression has succeeded.
  --cookies COOKIES     Path to cookie file to pass to downloaders (for members-only videos).
  --log-level LOG-LEVEL
                        Minimum log level to justify writing to log file on disk.
```

The expected pattern for both Youtube and Twitch video files is 
```
date [author_name] stream title [resolution width][video Id].extension`
```
Example of Youtube video file name:
```
20230726 [Komachi Panko] working at a Haunted Pizzeria [360][uSIOTJLqPLg].mp4
```
Example of Twitch video file name:
```
20240422 [vedal987] experimental neuro stream [best][2120650204].mp4
```
Expected video file extensions are webm, mkv, mp4, m4a, opus.


### Usage

Point to the programs expected to do the downloading for us:
```shell
export TDCLI="/path/to/TwitchDownloaderCLI"
export YTDL="/path/to/yt-dlp"
```

Download subtitles for each video Id found in `/target` and all its subdirectories:
```shell
python ./subs.py --mode "download" --remove-compressed --cookies ~/Cookies/cookies.txt /target
```

The `"compress"` mode is not very useful, as it is equivalent to calling your preferred compression program on all JSON files, i.e. `bzip2 **/*.json`. It is kept as convenience in case of a crash mid-process, to rerun the same logic.

Example:
```shell
subs.py --mode "download" --remove-compressed --log-level DEBUG --exclude-regex ".*/excluded/.*|.*/another_excluded/.*" /path/to/downloaded_videos
```

### TODO

* Pass cookies for members-only videos, especially for Twitch. Currently, the downloader has to be called separately with the appropriate argument.
* Decouple the file collecting logic. This step should be a separate script, and the subs.py script should not scan anything, only accept a list of file paths as input.
* Youtube and Twitch processing should be split into two separate scripts