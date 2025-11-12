# Twitch VOD Rename Tool

A Python tool to automatically rename Twitch video files based on metadata fetched from the Twitch API. The tool matches local video files with their corresponding Twitch VODs and updates filenames with proper titles and video IDs.

## Setup

### 1. Environment Variables

Set up your Twitch API credentials as environment variables:

```bash
export TWITCH_CLIENT_ID="your_client_id_here"
export TWITCH_CLIENT_SECRET="your_client_secret_here"
```

**How to get Twitch API credentials:**
1. Go to [Twitch Developer Console](https://dev.twitch.tv/console)
2. Create a new application
3. Copy the Client ID and generate a Client Secret

### 2. Configuration File

Create a configuration file in one of these locations:

**Primary location:** `~/.config/twitch_vods/config.yaml`  
**Fallback location:** `twitch/config/config.yaml` (in the project directory)

**Configuration format:**
```yaml
# Each entry represents a single Twitch channel
ChannelName:
  directory_name: "local_directory_name"  # Where video files are stored
  author_name: ["author1", "author2"]     # Author names in filenames
  channel_id: "twitch_channel_id"         # Twitch channel ID
```

### 3. Dependencies

Install required Python packages:
```bash
pip install requests PyYAML
```

## Usage

### Basic Commands

**Preview changes (dry-run mode):**
```bash
python -m twitch.rename_vods --directory /path/to/videos
```

**Apply changes:**
```bash
python -m twitch.rename_vods --directory /path/to/videos --apply
```

**Verbose output:**
```bash
python -m twitch.rename_vods --directory /path/to/videos --verbose
```

**Clear token cache:**
```bash
python -m twitch.rename_vods --clear-cache
```

### Command Line Options

- `--apply`: Actually rename files (default: dry-run mode)
- `--directory, -d`: Directory to scan for video files (default: current directory)
- `--verbose, -v`: Enable verbose logging
- `--clear-cache`: Clear cached access token and exit

### Batch Processing

Use the included bash script to process multiple directories:

```bash
./batch_rename_vods.sh /path/to/base/directory --apply
```

This will process each subdirectory in the base directory.

## File Naming Convention

The tool expects video files with this naming pattern:
```
YYYYMMDD HH-MM-SS [Author] Title [quality][video_id].ext
```

**Example:**
```
20241024 14-29-04 [fun streamer] Stream Title [best][1234567890].mp4
```

## How It Works

1. **File Discovery**: Scans directory for `.mp4` and `.ts` video files
2. **Author Extraction**: Extracts author names from filenames using `[Author]` pattern
3. **Channel Mapping**: Maps authors to Twitch channel IDs using the configuration file
4. **API Fetching**: Retrieves VOD metadata from Twitch API for each channel
5. **Video Matching**: Matches files to VODs by:
   - Exact video ID match (highest priority)
   - Date proximity (fallback method)
6. **Filename Generation**: Updates filenames with up-to-date titles and video IDs

## Troubleshooting

**"No channel IDs identified"**: Check that your directory name or author names match the configuration file.

**"Failed to get access token"**: Verify your `TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET` environment variables.

**"No videos found for channel"**: The channel might have no archived videos or the channel ID is incorrect.

## Notes

- The tool runs in **dry-run mode** by default - use `--apply` to actually rename files
- Access tokens are cached (in `/tmp`) for ~60 days to improve performance
- Files with video IDs starting with 'v' are automatically skipped; we assume they were downloaded with ytdlp and do not need further renaming
- Files with video IDs that already match what we found from the API are skipped; we assume they were already renamed once and do not need further update