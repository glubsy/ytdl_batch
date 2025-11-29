#!/usr/bin/env bash

# Script to download Twitch videos for defined channels using tsp and yt-dlp
# Each channel has an output path, channel name, and author name

set -euo pipefail

# Base storage path for all channels
BASE_STORAGE="/storage/vtubers_raw_04/vtubers_dump"

# Define channels as associative arrays. The author_name is used for the output filename.
# Format: channel_name|output_path|author_name

declare -a CHANNELS=(
    "kana|${BASE_STORAGE}/kamiko_kana|Kamiko Kana"
    "nokko|${BASE_STORAGE}/nokko|Nokko"
    "sobuuo|${BASE_STORAGE}/sobuuo|sobuuo"
    # Add more channels here in the same format:
    # "twitch_username|${BASE_STORAGE}/subfolder|Display Name"
)

# Archive file path
ARCHIVE_FILE="${HOME}/archive.txt"

# Wait for ffmpeg processes to finish before starting downloads
wait_for_ffmpeg_to_finish() {
    echo "Checking for running ffmpeg processes..."
    while pgrep -x ffmpeg > /dev/null; do
        echo "ffmpeg is running, waiting 5 minutes before checking again..."
        sleep 300  # Wait 5 minutes
    done
    echo "No ffmpeg processes detected, proceeding with downloads"
}

# Function to scan existing files and update archive
scan_and_update_archive() {
    local output_path="$1"
    local author_name="$2"

    echo "Scanning existing files in: ${output_path}"

    # Find all files matching the pattern with Twitch IDs [vXXXXXX]
    # Extract video IDs and add them to archive if not already present
    local count=0
    while IFS= read -r -d '' file; do
        # Extract Twitch ID using regex pattern [vDIGITS]
        if [[ $(basename "$file") =~ \[(v[0-9]+)\] ]]; then
            local video_id="${BASH_REMATCH[1]}"
            local archive_entry="twitchvod ${video_id}"

            # Check if this ID is already in the archive
            # grep returns non-zero when no match is found, which is expected
            if grep -qF "${archive_entry}" "${ARCHIVE_FILE}" 2>/dev/null; then
                # Already in archive, skip
                :
            else
                # Not in archive, add it
                echo "${archive_entry}" >> "${ARCHIVE_FILE}"
                echo "  Added to archive: ${video_id} from $(basename "$file")"
                ((count++))
            fi
        fi
    done < <(find "${output_path}" -type f \( -name "*.mp4" -o -name "*.mkv" -o -name "*.webm" -o -name "*.ts" \) -print0 2>/dev/null)

    if [[ ${count} -gt 0 ]]; then
        echo "  Total new entries added to archive: ${count}"
    else
        echo "  No new entries to add (all existing files already in archive)"
    fi
    echo ""
}

# Function to process a single channel
process_channel() {
    local output_path="$1"
    local channel_name="$2"
    local author_name="$3"

    echo "Processing channel: ${author_name} (channel name \"${channel_name}\")"
    echo "Output path: ${output_path}"

    # Check if output directory exists, create if not
    if [[ ! -d "${output_path}" ]]; then
        echo "Creating directory: ${output_path}"
        mkdir -p "${output_path}"
    fi

    # Scan existing files and update archive before downloading
    scan_and_update_archive "${output_path}" "${author_name}"

    # Change to output directory
    cd "${output_path}"

    # Run tsp with ytdlp
    # Skip live streams using --match-filter to only download VODs
    tsp ytdlp \
        -o "%(upload_date)s [${author_name}] %(title)s (no bgm) [%(height)s][%(id)s].%(ext)s" \
        --fragment-retries 50 \
        --download-archive "${ARCHIVE_FILE}" \
        --match-filter "!is_live" \
        "https://www.twitch.tv/videos/${channel_name}"

    echo "Queued download for ${author_name}"
    echo "---"
}

main() {
    echo "Starting Twitch download script"
    echo "================================"

    # Wait for any ffmpeg processes to finish before starting
    wait_for_ffmpeg_to_finish

    # Process each channel
    for channel_entry in "${CHANNELS[@]}"; do
        # Split the entry by pipe character
        IFS='|' read -r channel_name output_path author_name <<< "${channel_entry}"

        process_channel "${output_path}" "${channel_name}" "${author_name}"
    done

    echo "All channels queued for download"
    echo "Use 'tsp' to check the task spooler queue"
}

main "$@"
