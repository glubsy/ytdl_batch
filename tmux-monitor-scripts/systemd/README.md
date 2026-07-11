# tmux livestream services

This directory holds systemd unit examples for starting the tmux livestream
sessions automatically after boot.

## How it is set up

- The Twitch unit starts after `network-online.target`.
- The YouTube unit also waits for a WireGuard service name that you set in an
  optional environment file.
- The scripts are started in `--detach` mode so systemd can launch them without
  attaching to tmux.

## Enable on boot

For a user named `user`, place the scripts in `~/opt/`, install the units under
`/etc/systemd/system/`, and then enable them:

```sh
sudo systemctl enable --now tmux-livestreams-twitch@user.service
sudo systemctl enable --now tmux-livestreams-youtube@user.service
```

The main service starts the tmux session once. You can enable the watchdog
later if you want the session to be recreated after an unexpected exit.

## YouTube WireGuard dependency

Set the WireGuard unit name in:

`/etc/default/tmux-livestreams-youtube@user`

The file would contain:

```ini
WG_SERVICE=wg-quick@airvpn_kajam.service
```

If you want a different VPN unit later, change only that value.

## Optional watchdog

If you want tmux sessions to come back after an unexpected exit, enable the
matching watchdog timer after the main service is already running:

```sh
sudo systemctl enable --now tmux-livestreams-twitch-watch@user.timer
sudo systemctl enable --now tmux-livestreams-youtube-watch@user.timer
```

The timer periodically re-runs the launcher in `--detach` mode, so it only
recreates the session if it is missing.

This means the watchdog is optional, not exclusive. A normal flow is:

1. Start the main service.
2. Confirm the tmux session is up.
3. Enable the watchdog timer if you want automatic recovery.

To stop the automatic recreation before exiting tmux manually, disable the
timer first:

```sh
sudo systemctl disable --now tmux-livestreams-twitch-watch@user.timer
sudo systemctl disable --now tmux-livestreams-youtube-watch@user.timer
```
