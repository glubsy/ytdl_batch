# Twitch Download Script

This script downloads Twitch videos for configured channels using `yt-dlp` and `tsp` (task spooler).

## Configuration

Edit `twitch_download.sh` and modify the following:

1. **BASE_STORAGE**: Set the base storage path for all downloads
2. **CHANNELS array**: Add your channels in the format:
   ```bash
   "channel_name|output_path|author_name"
   ```

### Example Channel Configuration
```bash
declare -a CHANNELS=(
    "kana|${BASE_STORAGE}/kamiko_kana/twitch|Kamiko Kana"
    "other|${BASE_STORAGE}/other_channel/twitch|Other Channel"
)
```

## Features

- **Archive Scanning**: Before downloading, the script scans existing files in each channel's output directory and adds their Twitch video IDs to the archive file. This prevents re-downloading videos you already have locally.
- **Live Stream Filtering**: Automatically skips currently live streams and only downloads completed VODs.
- **Task Queuing**: Uses task spooler to queue downloads, allowing multiple channels to be processed sequentially.
- **Download Archive**: Maintains a persistent archive of downloaded video IDs to avoid duplicates.

## Manual Usage

```bash
chmod +x twitch_download.sh
./twitch_download.sh

# Check task spooler queue
tsp

# Check task spooler output
tsp -c <task_id>
```

## Systemd User Service Installation

The systemd service runs as a user service and is scheduled to run once daily via a timer.

### Installation Steps

1. **Make the script available in PATH:**
   ```bash
   # Create a symlink in your local bin directory
   mkdir -p ~/.local/bin
   ln -sf "$(pwd)/twitch_download.sh" ~/.local/bin/twitch_download.sh
   chmod +x "$(pwd)/twitch_download.sh"
   
   # Ensure ~/.local/bin is in your PATH (add to ~/.zshrc or ~/.bashrc if needed)
   echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
   ```

2. **Create user systemd directory (if it doesn't exist):**
   ```bash
   mkdir -p ~/.config/systemd/user/
   ```

3. **Copy the systemd service files:**
   ```bash
   cp systemd/twitch_download.service ~/.config/systemd/user/
   cp systemd/twitch_download.timer ~/.config/systemd/user/
   ```

4. **Update transcode_ts.service** (if not already done):
   ```bash
   cp ../transcode_move/systemd/transcode_ts.service ~/.config/systemd/user/
   ```

5. **Reload systemd user daemon:**
   ```bash
   systemctl --user daemon-reload
   ```

6. **Enable and start the timer:**
   ```bash
   systemctl --user enable twitch_download.timer
   systemctl --user start twitch_download.timer
   ```

7. **Enable lingering** (to allow user services to run when not logged in):
   ```bash
   loginctl enable-linger $USER
   ```

### Service Operation

- The service runs automatically once per day (at 11:00 AM)
- Can also be triggered manually: `systemctl --user start twitch_download.service`
- Check timer status: `systemctl --user status twitch_download.timer`
- Check service status: `systemctl --user status twitch_download.service`
- View logs: `journalctl --user -u twitch_download.service`
- List all user timers: `systemctl --user list-timers`
- Check when the timer will run next: `systemctl --user list-timers twitch_download.timer`

## Requirements

- `yt-dlp`: For downloading videos
- `tsp` (task spooler): For queuing downloads
- Proper mount access to storage paths

## Output Format

Downloaded files are named using this template:
```
%(upload_date)s [Author Name] %(title)s (no bgm) [%(height)s][%(id)s].%(ext)s
```

Example: `20231129 [Kamiko Kana] Stream Title (no bgm) [1080][v12345678].mp4`

Note: The `[vXXXXXXXX]` pattern in the filename is the Twitch video ID, which is used by the archive scanning feature.

## Archive Management

The script uses `~/archive.txt` to track downloaded videos and avoid duplicates.

### How it works:
1. **Pre-download scan**: Before downloading, the script scans existing video files (mp4, mkv, webm, ts) in each channel's output directory.
2. **ID extraction**: Extracts Twitch video IDs from filenames matching the pattern `[vDIGITS]`.
3. **Archive update**: Adds extracted IDs to `~/archive.txt` if not already present.
4. **Skip downloads**: yt-dlp automatically skips any videos with IDs already in the archive.

This ensures that videos already present in your storage won't be re-downloaded, even if they weren't previously tracked in the archive file.
