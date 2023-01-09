Various programs to automate downloading Youtube and Twitch VODs, as well as their subtitles.


# ytdl_batch.py

Download videoIds listed by `generate_list.py`

# generate_list.py

Use playboard to get a list of videoIds for a channel.


# Subs.py

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

### Usage


```shell
export TDCLI="/path/to/TwitchDownloaderCLI_1.51.1"
export YTDL="/path/to/yt-dlp/yt-dlp.sh"
```

Download subtitle files for each videoId found.

```shell
subs.py --mode "download" --remove-compressed --cookies ~/Cookies/cookies.txt /target
subs.py --mode "compress" --remove-compressed --cookies ~/Cookies/cookies.txt /target
```

Example:

```shell
subs.py --mode "download" --remove-compressed --log-level DEBUG --exclude-regex ".*/MISC/.*|.*/dox/.*" /path/to/directory
```

### TODO

* Pass cookies for members-only videos (Twitch handler in subs)