
# Setup

* make script executable
* place service and timer files into ~/.config/systemd/user
* systemctl --user enable --now transcode_ts.service

Place config file in $HOME/.config/transcode_ts.config or set TS_CONFIG env var
