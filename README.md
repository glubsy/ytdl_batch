Various programs to automate downloading Youtube and Twitch VODs, as well as their subtitles.


# ytdl_batch.py

Download videoIds listed by `generate_list.py`

# generate_list.py

Use playboard to get a list of videoIds for a channel.


# Subs.py

### Usage

Download subtitle files for each videoId found.

```
subs.py --mode "download" --remove-compressed --cookies ~/Cookies/cookies.txt /target
subs.py --mode "compress" --remove-compressed --cookies ~/Cookies/cookies.txt /target
```

### TODO

* Pass cookies for members-only videos (Twitch handler in subs)