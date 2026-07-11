# Monitor Scripts

This directory contains small shell helpers for launching tmux-based monitor sessions, mainly for livestream tracking.
The scripts are designed to:

- build tmux session definitions from local per-target config
- launch Twitch and YouTube monitor sessions consistently
- allow the individual monitor scripts to be run directly or through the shared wrapper

The current focus is livestream monitoring, but the layout is intentionally simple enough to extend to other monitor-style workflows later.

## Usage

Use the shared wrapper to launch a target:

```sh
./tmux_livestreams.sh twitch|youtube
```

You can also run the delegate scripts directly if you only want one target:

```sh
./tmux_livestreams_twitch.sh
./tmux_livestreams_youtube.sh
```

Pass `--detach` when launching from tmux-independent contexts, including systemd:

```sh
./tmux_livestreams.sh twitch --detach
./tmux_livestreams_twitch.sh --detach
```

The Twitch and YouTube scripts read their target-specific local config from XDG first, then fall back to this directory:

- `${XDG_CONFIG_HOME:-$HOME/.config}/tmux_livestreams/twitch.local.sh`
- `${XDG_CONFIG_HOME:-$HOME/.config}/tmux_livestreams/youtube.local.sh`
- local fallback copies in this directory with the same filenames

Tracked `*.example.sh` files show the expected structure for the Twitch and YouTube local configs.
The example templates are `twitch.local.sh.example` and `youtube.local.sh.example`.
The shared values are hard-coded in the scripts, except `DOWNLOAD_TARGET`, which can be overridden in each delegate config and falls back to `~/livestreams`. The wrapper computes `SESS_NAME` once per target, and the delegate scripts compute `DEF_FILE` themselves. If run directly, the delegate scripts also derive `SESS_NAME` from their target name.

Notes:

- `twitch.local.sh` holds the Twitch streamer order and URL mapping.
- `youtube.local.sh` holds the YouTube streamer order, quality mapping, and bgutil provider settings.
- `BGUTIL_PROVIDER_COMMIT` is optional. If it is unset or blank, the YouTube bootstrap fetches the current remote `HEAD` commit instead.
- `DOWNLOAD_TARGET` can be set in either delegate config if you want a non-default download directory.

## Systemd

The [`systemd/`](./systemd) directory contains unit and timer examples for starting the tmux livestream sessions automatically at boot.
The Twitch and YouTube services run the scripts in `--detach` mode, and the YouTube service can optionally depend on a WireGuard unit name from an environment file.

See [`systemd/README.md`](./systemd/README.md) for the full install and watchdog details.
