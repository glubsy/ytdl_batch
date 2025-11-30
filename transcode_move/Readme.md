# Transcode TS Script

This script transcodes remote TS files into locally stored MP4 files.

## Setup

### 1. Make the script available in PATH

```bash
# Create a symlink in your local bin directory
mkdir -p ~/.local/bin
ln -sf "$(pwd)/transcode_ts.sh" ~/.local/bin/transcode_ts.sh
chmod +x "$(pwd)/transcode_ts.sh"

# Ensure ~/.local/bin is in your PATH (add to ~/.zshrc or ~/.bashrc if needed)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
```

### 2. Configure the remote mount

Have the expected `.mount` unit active as specified in the systemd service file.

For example in `/etc/fstab`:
```
user@ovh:/home/user/livestreams/	/remote/twitch-monitor	fuse.sshfs	x-systemd.automount,_netdev,user,idmap=user,reconnect,compression=no,cache=no,transform_symlinks,allow_other 0 0
```

### 3. Install systemd user service

```bash
# Create user systemd directory (if it doesn't exist)
mkdir -p ~/.config/systemd/user/

# Place service and timer files
cp systemd/transcode_ts.service ~/.config/systemd/user/
cp systemd/transcode_ts.timer ~/.config/systemd/user/

# Reload systemd daemon
systemctl --user daemon-reload

# Enable and start the service and timer
systemctl --user enable --now transcode_ts.service
systemctl --user enable --now transcode_ts.timer

# Enable lingering (to allow user services to run when not logged in)
loginctl enable-linger $USER
```

### 4. Configuration

Place config file in `$HOME/.config/transcode_ts.config` or set `TS_CONFIG` env var.
