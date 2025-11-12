# Batch VOD Renaming Script

## Overview

The `batch_rename_vods.sh` script automates the process of running the Twitch VOD renaming tool across multiple streamer directories.

## Usage

```bash
./batch_rename_vods.sh <base_directory> [options]
```

## Examples

### 1. Dry Run (Default - No Changes Made)
```bash
# Process all directories in /tmp/streamers (dry run)
./batch_rename_vods.sh /tmp/streamers

# Same with verbose output
./batch_rename_vods.sh /tmp/streamers --verbose
```

### 2. Actually Apply Changes
```bash
# Apply changes to all directories
./batch_rename_vods.sh /tmp/streamers --apply

# Apply changes with verbose output
./batch_rename_vods.sh /tmp/streamers --verbose --apply
```

## Directory Structure Expected

The script expects a structure like:
```
/tmp/streamers/
├── streamer_1/
│   ├── 20241024 14-30-00 [Streamer Name] stream title [best][123456].mp4
│   └── 20241025 15-00-00 [Streamer Name] another stream [best][789012].mp4
├── streamer_2/
│   └── video files...
└── streamer_3/
    └── video files...
```

## What It Does

1. **Scans** the base directory for subdirectories
2. **Counts** video files (*.mp4, *.ts) in each subdirectory  
3. **Processes** each directory with the rename_vods.py script

## Output Example

```
🚀 Starting batch VOD renaming process
Base directory: /tmp/streamers
Options: --verbose

Found 3 directories to process

=========================================
Processing directory: kamiko_kana
=========================================
Found 25 video files in kamiko_kana

🚫 DRY RUN MODE: No files will be renamed. Use --apply to apply changes.
Found 25 video files in /tmp/streamers/streamer_1
...processing output...
✅ Successfully processed streamer_1

=========================================
📊 BATCH PROCESSING SUMMARY
=========================================
Total directories: 3
Successfully processed: 3

🎉 All directories processed successfully!

💡 This was a DRY RUN. To actually apply changes, add --apply flag:
   ./batch_rename_vods.sh /tmp/streamers --verbose --apply
```

## Requirements

- The script must be in the same directory as the `twitch/` folder
- Environment variables `TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET` must be set