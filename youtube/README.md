# YouTube VOD Downloader

A bash script that downloads YouTube VODs and live chats using yt-dlp for multiple channels defined in a YAML configuration file.

## Prerequisites

- `yt-dlp` - YouTube downloader
- `yq` v3.x - YAML processor (Python-based, not Go version)
- `bash` - Shell interpreter

### Install Dependencies

```bash
# Install yt-dlp
pip install yt-dlp

# Install yq (Python version)
pip install yq
```

## Configuration

### Config File Location

The script looks for `vod_download.yaml` in this order:
1. `~/.config/yt_download/vod_download.yaml` (XDG standard)
2. `./config/vod_download.yaml` (script directory)

### Config File Structure

The YAML file contains two documents separated by `---`:

```yaml
# Global settings
cookies_path : "~/youtube_cookies.txt"
po_token_path : "~/youtube_po_token.txt"

---

# Channel configurations
ChannelName:
  weight: 100  # optional, higher weights are processed first
  download_path: "/path/to/download/directory"
  archive_path: "/path/to/archive.txt"
  channel_id: "@username"  # or "UCxxxxxxxxxxxxxxxxxxxxxxx"
```

If `weight` is omitted, the script uses `0`.

### Setup Steps

1. **Copy config template:**
   ```bash
   mkdir -p ~/.config/ytdlp_download
   cp config/vod_download.yaml ~/.config/ytdlp_download/
   ```

2. **Edit configuration:**
   ```bash
   nano ~/.config/ytdlp_download/vod_download.yaml
   ```

3. **Set up authentication files:**
   - Export cookies from browser to `cookies_path`
   - Obtain PO token and save to `po_token_path`

4. **Create download directories:**
   ```bash
   # Ensure all download_path directories exist
   mkdir -p /path/to/your/download/directories
   ```

## Usage

```bash
# Make executable (if needed)
chmod +x vod_download.sh

# Run the script
./vod_download.sh
```

## Features

- **Multiple channels**: Process all channels defined in config
- **Weighted ordering**: Higher-priority channels run first via per-channel `weight`
- **Archive support**: Prevents re-downloading existing videos
- **Live chat**: Downloads live chat as subtitles
- **Error handling**: Continues with other channels if one fails
- **XDG compliance**: Uses standard Linux config directories
- **Flexible URLs**: Supports @username, channel IDs, and custom URLs

## Output

Videos are saved with format:
```
YYYYMMDD [Channel Name] Video Title [Height][Video ID].ext
```

## Troubleshooting

- **"yq command not found"**: Install yq v3.x (`pip install yq`)
- **"Config file not found"**: Check file exists in expected locations
- **Authentication errors**: Verify cookies and PO token files exist and are valid
- **Download failures**: Check network connection and YouTube availability

## Notes

- Script requires yq v3.x (Python-based), not v4.x (Go-based)
- PO token helps with YouTube's anti-bot measures
- Fresh cookies may be needed periodically
