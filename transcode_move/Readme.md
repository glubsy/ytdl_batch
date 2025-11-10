
# Setup

* make script executable
* place service and timer files into ~/.config/systemd/user
* have the expected .mount unit active as specified in the systemd service file
  For example in /etc/fstab:
  user@ovh:/home/user/livestreams/	/remote/twitch-monitor	fuse.sshfs	x-systemd.automount,_netdev,user,idmap=user,reconnect,compression=no,cache=no,transform_symlinks,allow_other 0 0
* systemctl --user enable --now transcode_ts.service
* systemctl --user enable --now transcode_ts.timer

Place config file in $HOME/.config/transcode_ts.config or set TS_CONFIG env var
