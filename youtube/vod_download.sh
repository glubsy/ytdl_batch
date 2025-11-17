#!/bin/bash

# This script downloads YouTube VODs and live chats using yt-dlp for each
# channel defined in the config file.
# NOTE: this assume the available version of yq is v3.x (not v4.x), the
# Python-based one.

set -euo pipefail

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Set up config file paths with XDG config directory priority
XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
XDG_CONFIG_FILE="$XDG_CONFIG_HOME/yt_download/vod_download.yaml"
SCRIPT_CONFIG_FILE="$SCRIPT_DIR/config/vod_download.yaml"

# Check for config file in XDG config directory first, then fallback to script directory
if [[ -f "$XDG_CONFIG_FILE" ]]; then
    CONFIG_FILE="$XDG_CONFIG_FILE"
    echo "Using config file from XDG config directory: $CONFIG_FILE"
elif [[ -f "$SCRIPT_CONFIG_FILE" ]]; then
    CONFIG_FILE="$SCRIPT_CONFIG_FILE"
    echo "Using config file from script directory: $CONFIG_FILE"
else
    echo "Error: Config file not found in either location:"
    echo "  XDG config: $XDG_CONFIG_FILE"
    echo "  Script dir: $SCRIPT_CONFIG_FILE"
    exit 1
fi

# Check if yq is installed
if ! command -v yq &> /dev/null; then
    echo "Error: yq command not found. Please install yq."
    exit 1
fi

# Load global settings from the first document
echo "Loading global settings..."
COOKIES_PATH=$(yq -r 'select(.cookies_path) | .cookies_path' "$CONFIG_FILE")
PO_TOKEN_PATH=$(yq -r 'select(.po_token_path) | .po_token_path' "$CONFIG_FILE")

# Expand tilde in paths
COOKIES_PATH="${COOKIES_PATH/#\~/$HOME}"
PO_TOKEN_PATH="${PO_TOKEN_PATH/#\~/$HOME}"

echo "Cookies path: $COOKIES_PATH"
echo "PO Token path: $PO_TOKEN_PATH"

# Verify required files exist
if [[ ! -f "$COOKIES_PATH" ]]; then
    echo "Warning: Cookies file not found at $COOKIES_PATH"
fi

if [[ ! -f "$PO_TOKEN_PATH" ]]; then
    echo "Warning: PO Token file not found at $PO_TOKEN_PATH"
fi

download_channel() {
    local channel_name="$1"
    local download_path="$2"
    local archive_path="$3"
    local channel_id="$4"

    echo "============================================"
    echo "Processing channel: $channel_name"
    echo "Download path: $download_path"
    echo "Archive path: $archive_path"
    echo "Channel ID: $channel_id"
    echo "============================================"

    # Create download directory if it doesn't exist
    mkdir -p "$download_path"

    # Change to download directory
    cd "$download_path" || {
        echo "Error: Cannot change to download directory: $download_path"
        return 1
    }

    # Construct YouTube URL
    local youtube_url
    if [[ "$channel_id" == @* ]]; then
        # Handle format "@username"
        youtube_url="https://www.youtube.com/${channel_id}/streams"
    elif [[ "$channel_id" =~ ^UC[a-zA-Z0-9_-]{22}$ ]]; then
        # Handle format "UCxxxxxxxxxxxxxxxxxxxxxxx" (channel ID)
        youtube_url="https://www.youtube.com/channel/${channel_id}/streams"
    else
        # Assume it's a custom username or handle
        youtube_url="https://www.youtube.com/c/${channel_id}/streams"
    fi

    echo "Downloading from: $youtube_url"

    yt-dlp -v -o \
        '%(upload_date)s [%(uploader)s] %(title)s [%(height)s][%(id)s].%(ext)s' \
        --fragment-retries 10 \
        --postprocessor-args 'ffmpeg:-movflags faststart' \
        --cookies "$COOKIES_PATH" \
        --max-sleep-interval 120 \
        --min-sleep-interval 60 \
        --xattrs \
        --no-part \
        --abort-on-unavailable-fragments \
        --download-archive "$archive_path" \
        --playlist-reverse \
        --add-metadata \
        --embed-thumbnail \
        --write-subs \
        --sub-langs "live_chat" \
        -S "res:480,+codec:h264:m4a" \
        --extractor-args "youtube:player-client=web,default;po_token=web+$(cat "$PO_TOKEN_PATH" 2>/dev/null || echo '')" \
        --extractor-args "youtube:po_token=web.subs+$(cat "$PO_TOKEN_PATH" 2>/dev/null || echo '')" \
        "$youtube_url"

    echo "Completed processing channel: $channel_name"
    echo ""
}

# Get all channel names from the channels document (the one without cookies_path)
echo "Getting channel list..."
mapfile -t CHANNEL_NAMES < <(yq -r 'select(.cookies_path | not) | keys[]' "$CONFIG_FILE")

if [[ ${#CHANNEL_NAMES[@]} -eq 0 ]]; then
    echo "No channels found in config file."
    exit 0
fi

echo "Found ${#CHANNEL_NAMES[@]} channels to process:"
printf '%s\n' "${CHANNEL_NAMES[@]}"
echo ""

# Process each channel
for channel_name in "${CHANNEL_NAMES[@]}"; do
    # Get channel configuration
    download_path=$(yq -r "select(.cookies_path | not) | .[\"$channel_name\"].download_path" "$CONFIG_FILE")
    archive_path=$(yq -r "select(.cookies_path | not) | .[\"$channel_name\"].archive_path" "$CONFIG_FILE")
    channel_id=$(yq -r "select(.cookies_path | not) | .[\"$channel_name\"].channel_id" "$CONFIG_FILE")

    # Skip if any required field is missing or null
    if [[ "$download_path" == "null" || "$archive_path" == "null" || "$channel_id" == "null" ]]; then
        echo "Skipping channel $channel_name: missing required configuration"
        continue
    fi

    # Check if archive file exists and warn if not
    if [[ ! -f "$archive_path" ]]; then
        echo "Warning: Archive file does not exist for channel $channel_name: $archive_path"
        echo "Note: A new archive file will be created during the download process."
    fi

    # Download for this channel (with error handling)
    if ! download_channel "$channel_name" "$download_path" "$archive_path" "$channel_id"; then
        echo "Error processing channel: $channel_name"
        echo "Continuing with next channel..."
        echo ""
    fi
done

echo "All channels processed!"

