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
    local tab="${5:-}"  # Optional tab parameter, empty by default

    echo "============================================"
    echo "Processing channel: $channel_name"
    echo "Download path: $download_path"
    echo "Archive path: $archive_path"
    echo "Channel ID: $channel_id"
    if [[ -n "$tab" ]]; then
        echo "Tab: $tab"
    fi
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
    local tab_suffix=""
    if [[ -n "$tab" ]]; then
        tab_suffix="/${tab}"
    fi

    if [[ "$channel_id" == @* ]]; then
        # Handle format "@username"
        youtube_url="https://www.youtube.com/${channel_id}${tab_suffix}"
    elif [[ "$channel_id" =~ ^UC[a-zA-Z0-9_-]{22}$ ]]; then
        # Handle format "UCxxxxxxxxxxxxxxxxxxxxxxx" (channel ID)
        youtube_url="https://www.youtube.com/channel/${channel_id}${tab_suffix}"
    else
        # Assume it's a custom username or handle
        youtube_url="https://www.youtube.com/c/${channel_id}${tab_suffix}"
    fi

    echo "Downloading from: $youtube_url"

    # Capture yt-dlp output to check for rate limiting errors
    local temp_output
    temp_output=$(mktemp)

    # Build yt-dlp command with conditional arguments
    local ytdlp_args=(
        -v
        -o '%(upload_date)s [%(uploader)s] %(title)s [%(height)s][%(id)s].%(ext)s'
        --fragment-retries 10
        --postprocessor-args 'ffmpeg:-movflags faststart'
        --max-sleep-interval 120
        --min-sleep-interval 60
        --xattrs
        --no-part
        --abort-on-unavailable-fragments
        --download-archive "$archive_path"
        --playlist-reverse
        --add-metadata
        --embed-thumbnail
        --write-subs
        --sub-langs "live_chat"
        --remote-components ejs:github
        --match-filter '!is_live'
        -S "res:480,+codec:h264:m4a"
    )

    # Add cookies argument only if the file exists
    if [[ -f "$COOKIES_PATH" ]]; then
        ytdlp_args+=(--cookies "$COOKIES_PATH")
    fi

    # Add extractor-args with PO token only if the file exists
    if [[ -f "$PO_TOKEN_PATH" ]]; then
        ytdlp_args+=(--extractor-args "youtube:player-client=web,default;po_token=web+$(cat "$PO_TOKEN_PATH")")
        ytdlp_args+=(--extractor-args "youtube:po_token=web.subs+$(cat "$PO_TOKEN_PATH")")
    fi

    ytdlp_args+=("$youtube_url")

    yt-dlp "${ytdlp_args[@]}" 2>&1 | tee "$temp_output"

    local exit_code=${PIPESTATUS[0]}

    # Check for rate limiting errors (429 or "too many requests")
    if grep -qi -E "(too many requests)" "$temp_output"; then
        echo ""
        echo "⚠️  ERROR: Rate limiting detected for channel: $channel_name"
        echo "⚠️  YouTube is throttling requests (HTTP 429 or 'Too Many Requests')"
        echo "⚠️  Exiting script to avoid further rate limiting"
        echo ""
        # Clean up temp file before exiting
        rm -f "$temp_output"
        exit 1
    fi

    # Clean up temp file
    rm -f "$temp_output"

    if [[ $exit_code -ne 0 ]]; then
        echo "yt-dlp exited with code: $exit_code"
        return $exit_code
    fi

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

    # Get tabs array if specified, otherwise use empty array (will use base channel URL)
    tabs_json=$(yq -r "select(.cookies_path | not) | .[\"$channel_name\"].tabs // null" "$CONFIG_FILE")
    if [[ "$tabs_json" == "null" ]]; then
        tabs=("")  # Empty string means no tab suffix
    else
        mapfile -t tabs < <(echo "$tabs_json" | yq -r '.[]' 2>/dev/null)
    fi

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

    # Download for each tab specified
    for tab in "${tabs[@]}"; do
        # Download for this channel tab (with error handling)
        if ! download_channel "$channel_name" "$download_path" "$archive_path" "$channel_id" "$tab"; then
            echo "Error processing channel: $channel_name (tab: $tab)"
            echo "Continuing with next tab/channel..."
            echo ""
        fi
    done
done

echo "All channels processed!"

