"""
This module scans directories recursively to find Twich recordings (video files)
and renames them based on their metadata fetched from Twitch API.

- The video Id is updated from the VODS (if it still exists on Twitch).
- The title is updated from the VODS (if it still exists on Twitch).
- TODO: the thumbnail is downloaded (for later embedding in the video file).
"""

try:
    # Try relative import first (when run as module)
    from twitch.fetch_vods import (
        fetch_videos, get_access_token, clear_token_cache, CLIENT_ID, CLIENT_SECRET
    )
except ImportError:
    # Try absolute import (when run as script)
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from twitch.fetch_vods import (
        fetch_videos, get_access_token, clear_token_cache, CLIENT_ID, CLIENT_SECRET
    )
from pathlib import Path
import yaml
import logging
import re
from datetime import datetime
import os
import argparse

# ANSI color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

class ColoredFormatter(logging.Formatter):
    """Custom formatter to add colors to log messages based on level."""

    COLORS = {
        logging.ERROR: Colors.RED,
        logging.WARNING: Colors.YELLOW,
        logging.INFO: '',  # No color for info
        logging.DEBUG: '',  # No color for debug
    }

    def format(self, record):
        # Get the color for this log level
        color = self.COLORS.get(record.levelno, '')

        # Format the message normally first
        message = super().format(record)

        if color:
            message = f"{color}{message}{Colors.RESET}"

        return message

# Set up logger with colored formatter
log = logging.getLogger("rename")

# Create handler and apply colored formatter
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
handler.setFormatter(ColoredFormatter())

# Clear any existing handlers and add our colored handler
log.handlers.clear()
log.addHandler(handler)

# Prevent propagation to root logger to avoid duplicate messages
log.propagate = False


config_path = Path("~/.config/twitch_vods/config.yaml").expanduser()
try:
    with open(config_path, "r") as f:
        CONFIG: dict[str, str | list[str]] = yaml.safe_load(f)
except FileNotFoundError:
    # Fallback to local config file for development/testing
    local_config_path = Path(__file__).parent / "config" / "config.yaml"
    with open(local_config_path, "r") as f:
        CONFIG: dict[str, str | list[str]] = yaml.safe_load(f)


# Color utility functions
def color_print(message: str, color: str = "GREEN") -> None:
    """Print message with color. Defaults to green."""
    color_code = getattr(Colors, color, Colors.GREEN)
    print(f"{color_code}{message}{Colors.RESET}")


def collect_files(path: Path) -> list[Path]:
    """Collect all video files from the given directory path."""
    video_files: list[Path] = []
    for ext in ('*.mp4', '*.ts'):
        video_files.extend(path.rglob(ext))
    return video_files


def extract_video_id(filename: str) -> str | None:
    """Extract the Twitch video Id from the filename using known patterns."""
    patterns = [
        r'.*\[.*\]\[([^\]]+)\].*',  # Any non-empty content between the last brackets
    ]

    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            video_id = match.group(1).strip()
            # Return None if the video ID is empty after stripping
            return video_id if video_id else None
    return None


def index_on_video_id(videos: list[dict]) -> dict[str, dict]:
    """Create an index of videos based on their video Ids."""
    index = {}
    for video in videos:
        video_id = video.get('id')
        if not video_id:
            continue
        index[video_id] = video
    return index


def identify_authors_from_files(video_files: list[Path]) -> set[str]:
    """
    Identify unique authors from the list of video files based on filename patterns.
    The filenames are expected to contain the author/channel name inside the first
    set of [] brackets.
    """
    authors = set()
    for video_file in video_files:
        name_parts = video_file.stem.split(']')
        if name_parts and '[' in name_parts[0]:
            author = name_parts[0].split('[')[-1].strip()
            authors.add(author)
    return authors


def identify_authors_from_directory(directory: Path, config: dict) -> set[str]:
    """
    Identify unique channel IDs from the current directory's name.
    The directory names are expected to match the 'directory_name' field in the config.
    Returns the channel IDs to fetch videos for.
    """
    channel_ids = set()
    current_dir = directory.resolve()
    current_dir_name = current_dir.name
    for entry_name, details in config.items():
        if not isinstance(details, dict):
            continue
        dir_name = details.get('directory_name', "")
        if dir_name not in current_dir_name:
            continue
        channel_id = details.get('channel_id')
        if channel_id:
            channel_ids.add(channel_id)
    if not channel_ids:
        raise ValueError(
            "No channel IDs identified from directory name. "
            "Please configure it in config.yaml")
    return channel_ids


def extract_date_from_filename(filename: str) -> datetime | None:
    """Extract date from filename patterns like '20251024 14-29-04' or '20251024'."""
    patterns = [
        r'^(\d{8})\s+(\d{2})-(\d{2})-(\d{2})(?:\s|$|\[)',  # YYYYMMDD HH-MM-SS followed by space, end, or [
        r'^(\d{8})(?:\s|$|\[)',  # YYYYMMDD only followed by space, end, or [
    ]

    for pattern in patterns:
        match = re.match(pattern, filename)
        if match:
            if len(match.groups()) >= 4:
                # Full datetime - validate time components first
                hour, minute, second = match.group(2), match.group(3), match.group(4)
                if int(hour) >= 24 or int(minute) >= 60 or int(second) >= 60:
                    continue  # Invalid time components

                date_str = match.group(1)
                time_str = f"{hour}:{minute}:{second}"
                try:
                    return datetime.strptime(f"{date_str} {time_str}", "%Y%m%d %H:%M:%S")
                except ValueError:
                    continue
            else:
                # Date only
                date_str = match.group(1)
                try:
                    return datetime.strptime(date_str, "%Y%m%d")
                except ValueError:
                    continue


def sanitize_filename(title: str) -> str:
    """Sanitize video title for use in filename."""
    # Remove or replace invalid filename characters
    invalid_chars = '<>:"/\\|*'
    for char in invalid_chars:
        title = title.replace(char, '_')
    # Remove extra whitespace and limit length
    title = ' '.join(title.split())
    return title[:160]


def apply_title_overrides(title: str, title_overrides: list[str]) -> str:
    """
    Apply title overrides to remove specified substrings or regex patterns from title.

    Args:
        title: The original title string
        title_overrides: List of strings to remove. If a string contains {{ }} pattern,
                        the content inside is treated as a regex pattern.

    Returns:
        Title with specified overrides removed and leading whitespace cleaned
    """
    if not title_overrides:
        return title

    result = title

    for override in title_overrides:
        if '{{' in override and '}}' in override:
            # Build a regex pattern where {{ }} parts are treated as regex
            # and everything else is treated as literal text
            # Example: "- A test (day {{ \\d+ }})" becomes "- A test \(day \d+\)"
            try:
                # Split the override into parts, escaping literal parts and keeping regex parts
                pattern_parts = []
                current_pos = 0

                # Find all {{ }} matches
                regex_matches = list(re.finditer(r'\{\{\s*(.*?)\s*\}\}', override))

                for match in regex_matches:
                    # Add literal text before the {{ }} as escaped
                    literal_text = override[current_pos:match.start()]
                    if literal_text:
                        pattern_parts.append(re.escape(literal_text))

                    # Add the regex pattern inside {{ }} without escaping
                    regex_content = match.group(1)
                    pattern_parts.append(regex_content)

                    current_pos = match.end()

                # Add any remaining literal text after the last {{ }}
                remaining_text = override[current_pos:]
                if remaining_text:
                    pattern_parts.append(re.escape(remaining_text))

                # Combine all parts into final regex pattern
                final_pattern = ''.join(pattern_parts)
                result = re.sub(final_pattern, '', result, flags=re.IGNORECASE)

            except re.error as exc:
                log.warning(
                    "Invalid regex pattern in title override '%s': %s",
                    override, exc)
                continue
        else:
            # Simple substring removal (case-insensitive)
            result = re.sub(re.escape(override), '', result, flags=re.IGNORECASE)

    # Clean up leading/trailing whitespace and multiple spaces
    result = ' '.join(result.split())
    return result


def parse_duration_to_seconds(duration_str: str) -> int:
    """
    Parse Twitch duration format to seconds.
    Examples: "10s" -> 10, "4m40s" -> 280, "2h46m14s" -> 9974

    Args:
        duration_str: Duration string in format like "1h23m45s", "5m30s", "45s"

    Returns:
        Total duration in seconds
    """
    import re

    total_seconds = 0

    # Extract hours
    hours_match = re.search(r'(\d+)h', duration_str)
    if hours_match:
        total_seconds += int(hours_match.group(1)) * 3600

    # Extract minutes
    minutes_match = re.search(r'(\d+)m', duration_str)
    if minutes_match:
        total_seconds += int(minutes_match.group(1)) * 60

    # Extract seconds
    seconds_match = re.search(r'(\d+)s', duration_str)
    if seconds_match:
        total_seconds += int(seconds_match.group(1))

    return total_seconds


def find_matching_video(file_path: Path, videos: list[dict]) -> dict | None:
    """
    Find the best matching video from API data.
    First attempts to match by stream_id extracted from filename.
    If file already has a video ID but no match is found, returns None to avoid false matches.
    Only falls back to date-based matching for files without video IDs.
    Filters out videos shorter than 10 seconds to avoid stub VODs.
    Returns the video dict if found, None otherwise.
    """
    # First, try to match by stream_id from filename
    file_video_id = extract_video_id(file_path.name)
    if file_video_id:
        # Try to find a video with matching stream_id
        for video in videos:
            stream_id = video.get('stream_id')
            if stream_id and str(stream_id) == file_video_id:
                log.info(
                    "Found exact stream_id match for \"%s\": [%s] \"%s\" (stream_id: %s)",
                    file_path.name, video['id'], video['title'], stream_id
                )
                return video
        
        # If file has a video ID but we couldn't match it, skip date-based matching
        # This prevents false matches when the original VOD has been deleted
        log.info(
            "File has video ID [%s] but no matching VOD found in API - skipping to avoid false match: %s",
            file_video_id, file_path.name
        )
        return None

    # Only fall back to date-based matching if file doesn't have a video ID
    log.debug("No video ID in filename, using date-based matching for: %s", file_path.name)

    file_date = extract_date_from_filename(file_path.name)
    if not file_date:
        log.error("Could not extract date from filename: %s", file_path.name)
        return

    # Filter out very short videos (less than 10 seconds)
    # These are typically stub VODs or test streams
    filtered_videos = []
    for video in videos:
        duration_str = video.get('duration', '0s')
        duration_seconds = parse_duration_to_seconds(duration_str)
        if duration_seconds >= 10:
            filtered_videos.append(video)
        else:
            log.debug(
                "Filtering out short VOD (<%ds): [%s] %s (%s)",
                10, video['id'], video['title'], duration_str
            )

    if len(filtered_videos) < len(videos):
        log.debug(
            "Filtered out %d short VODs (<%ds), %d remaining",
            len(videos) - len(filtered_videos), 10, len(filtered_videos)
        )

    best_match = None
    min_time_diff = float('inf')

    for video in filtered_videos:
        try:
            # Parse Twitch API date format (ISO 8601)
            video_date = datetime.fromisoformat(video['created_at'].replace('Z', '+00:00'))
            # Convert to naive datetime for comparison (assuming local timezone)
            video_date = video_date.replace(tzinfo=None)

            time_diff = abs((file_date - video_date).total_seconds())

            # Check if video started before or after the file timestamp
            # Negative means video started before file (which is expected)
            time_offset = (video_date - file_date).total_seconds()

            log.debug(
                "  Checking VOD [%s] %s (created: %s, time_diff: %.1f seconds, offset: %+.1fs)",
                video['id'], video.get('duration', 'N/A'),
                video['created_at'], time_diff, time_offset
            )

            # Consider it a match if within 5 minutes (300 seconds) for better accuracy
            # This prevents matching files to VODs that are too far apart
            max_time_diff_seconds = 5 * 60  # 5 minutes
            if time_diff < max_time_diff_seconds:
                # Prefer VODs that started before the file timestamp
                # When time differences are very close (within 2 minutes),
                # prefer the one that started earlier
                is_better_match = False

                if best_match is None:
                    # First match
                    is_better_match = True
                else:
                    # Check if both matches are very close (within 30 seconds)
                    # Only then prefer the earlier VOD
                    if abs(time_diff - min_time_diff) < 30:
                        # Get offset of current best match
                        best_offset = (datetime.fromisoformat(
                            best_match['created_at'].replace('Z', '+00:00')
                        ).replace(tzinfo=None) - file_date).total_seconds()

                        # When close, prefer VOD that started before file (negative offset)
                        if time_offset < best_offset:
                            is_better_match = True
                            log.debug(
                                "    -> Preferring earlier VOD (offset %+.1fs vs %+.1fs, time_diff %.1fs vs %.1fs)",
                                time_offset, best_offset, time_diff, min_time_diff
                            )
                        else:
                            log.debug(
                                "    -> Keeping current best (offset %+.1fs is not earlier than %+.1fs)",
                                time_offset, best_offset
                            )
                    elif time_diff < min_time_diff:
                        # Time difference is significant (>2 min), pick closer one
                        is_better_match = True

                if is_better_match:
                    min_time_diff = time_diff
                    best_match = video
                    log.debug(
                        "    -> New best match! time_diff: %.1f seconds (%.2f minutes), offset: %+.1fs",
                        time_diff, time_diff/60, time_offset
                    )

        except (ValueError, KeyError) as exc:
            log.error(
                "Could not parse video date: %s - %s",
                video.get('created_at', 'N/A'), exc)
            continue

    if best_match:
        log.info(
            "Found match for \"%s\": [%s] \"%s\" (time diff: %.2f hours)",
            file_path.name, best_match['id'], best_match['title'], min_time_diff/3600)
    else:
        log.info("No matching video found for \"%s\"", file_path.name)

    return best_match


def generate_new_filename(file_path: Path, video: dict, channel_config: dict | None = None) -> str:
    """
    Generate new filename with updated title and video ID.
    Preserves the original date/time prefix and file extension.
    Applies title overrides if configured for the channel.

    Args:
        file_path: Path to the original video file
        video: Video metadata from Twitch API
        channel_config: Configuration for the specific channel (optional)
    """
    original_name = file_path.name

    # Extract date/time prefix - try both formats
    date_patterns = [
        r'^(\d{8}\s+\d{2}-\d{2}-\d{2})(?:\s|$|\[)',  # YYYYMMDD HH-MM-SS
        r'^(\d{8})(?:\s|$|\[)'  # YYYYMMDD only
    ]

    date_prefix = ""
    for pattern in date_patterns:
        date_match = re.match(pattern, original_name)
        if date_match:
            date_prefix = date_match.group(1)
            break

    # Extract author from original filename
    author_match = re.search(r'\[([^\]]+)\]', original_name)
    author = author_match.group(1) if author_match else "Unknown"

    clean_title = sanitize_filename(video['title'])

    # Apply title overrides if configured for this channel
    if channel_config and (title_overrides := channel_config.get('title_overrides')):
        clean_title = apply_title_overrides(clean_title, title_overrides)

    video_id = video['id']

    extension = file_path.suffix

    new_name = f"{date_prefix} [{author}] {clean_title} [best][{video_id}]{extension}"
    return new_name


def extract_author_from_filename(filename: str) -> str | None:
    """
    Extract the author name from a video filename.
    Expected format: "YYYYMMDD HH-MM-SS [Author Name] title [best][video_id].ext"

    Args:
        filename: The video filename to extract author from

    Returns:
        The author name if found, None otherwise
    """
    # Look for the first occurrence of [author_name]
    import re
    match = re.search(r'\[([^\]]+)\]', filename)
    if match:
        return match.group(1).strip()


def get_channel_id_for_author(author: str, config: dict) -> str | None:
    """
    Get the channel ID for a given author name from the config.

    Args:
        author: The author name to look up
        config: The configuration dictionary

    Returns:
        The channel ID if found, None otherwise
    """
    for streamer_config in config.values():
        if not isinstance(streamer_config, dict):
            continue

        author_names = streamer_config.get('author_name', [])
        channel_id = streamer_config.get('channel_id')

        # Check if the author matches any of the configured author names
        if author in author_names:
            return channel_id

        # Also check if author directly matches the channel ID
        if author == channel_id:
            return channel_id


def update_filenames(
    video_files: list[Path],
    videos_by_channel: dict[str, list[dict]],
    dry_run: bool = True
) -> None:
    """
    Update filenames based on Twitch API data.
    Matches files to videos by date proximity and updates title and video ID.
    Now matches files to videos from the correct channel only.

    Args:
        video_files: List of video file paths to process
        videos_by_channel: Dictionary mapping channel IDs to their video lists
        dry_run: If True, only show what would be renamed without actually renaming
    """
    mode_text = "DRY RUN - " if dry_run else ""
    total_videos = sum(len(video_list) for video_list in videos_by_channel.values())
    log.info(
        "%sProcessing %d video files based on %d API videos",
        mode_text, len(video_files), total_videos
    )

    updated_count = 0
    skipped_v_count = 0
    skipped_matching_id_count = 0
    skipped_no_channel_count = 0

    for file_path in video_files:
        log.debug("Processing file: %s", file_path.name)

        # Check if file has a video ID that starts with "v" and skip it
        current_video_id = extract_video_id(file_path.name)
        if current_video_id and current_video_id.startswith('v'):
            log.debug("Skipping file with video ID starting with 'v': %s", file_path.name)
            skipped_v_count += 1
            continue

        # Extract author from filename and match to specific channel
        author = extract_author_from_filename(file_path.name)
        if not author:
            log.warning("Could not extract author from filename: %s", file_path.name)
            skipped_no_channel_count += 1
            continue

        channel_id = get_channel_id_for_author(author, CONFIG)
        if not channel_id:
            log.warning(
                "No channel ID found for author '%s' in file: %s",
                author, file_path.name
            )
            skipped_no_channel_count += 1
            continue

        # Get videos for this specific channel
        channel_videos = videos_by_channel.get(channel_id, [])
        if not channel_videos:
            log.warning(
                "No videos found for channel '%s' (author: '%s') in file: %s",
                channel_id, author, file_path.name
            )
            skipped_no_channel_count += 1
            continue

        # log.debug(
        #     "Using %d videos from channel '%s' for author '%s'",
        #     len(channel_videos), channel_id, author
        # )

        # Check if the current video ID already matches one from the API for this channel
        matching_api_video = None
        for video in channel_videos:
            if video.get('id') == current_video_id:
                log.debug(
                    "Skipping file with video ID already matching API in channel '%s': %s",
                    channel_id, file_path.name)
                skipped_matching_id_count += 1
                matching_api_video = video
                break

        if matching_api_video:
            continue

        # No matching video ID found in API, proceed with renaming
        matching_video = find_matching_video(file_path, channel_videos)
        if not matching_video:
            continue

        # Get channel configuration for title overrides
        channel_config = None
        for config_name, config_details in CONFIG.items():
            if isinstance(config_details, dict) \
                    and config_details.get('channel_id') == channel_id:
                channel_config = config_details
                break

        # Generate new filename
        new_filename = generate_new_filename(file_path, matching_video, channel_config)
        new_path = file_path.parent / new_filename

        # Skip if filename wouldn't change
        if file_path.name == new_filename:
            color_print(f"Filename already up to date: {file_path.name}", "CYAN")
            continue

        color_print(f"RENAMING: {file_path.name}", "GREEN")
        color_print(f"      TO: {new_filename}", "GREEN")

        # Check if target filename already exists
        if new_path.exists() and not dry_run:
            log.warning(
                "Target filename already exists, skipping: %s", new_filename)
            continue

        if not dry_run:
            try:
                os.rename(file_path, new_path)
                updated_count += 1
            except OSError as exc:
                log.error(f"Failed to rename {file_path.name}: {exc}")

    action_text = "Would update" if dry_run else "Successfully updated"
    color_print(f"{action_text} {updated_count} filenames", "GREEN")
    if skipped_v_count > 0:
        color_print(
            f"Skipped {skipped_v_count} files with video IDs starting with 'v'", "YELLOW")
    if skipped_matching_id_count > 0:
        color_print(
            f"Skipped {skipped_matching_id_count} files with video IDs already matching API", "CYAN")
    if skipped_no_channel_count > 0:
        color_print(
            f"Skipped {skipped_no_channel_count} files with no matching channel configuration", "YELLOW")


def main():
    parser = argparse.ArgumentParser(
        description="Update Twitch video filenames based on API data",
        epilog="By default, this script runs in dry-run mode. Use --apply to actually rename files."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually apply the filename changes (default: dry-run mode)"
    )
    parser.add_argument(
        "--directory", "-d",
        type=Path,
        default=Path("."),
        help="Directory to scan for video files (default: current directory)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear the cached access token and exit"
    )
    args = parser.parse_args()

    # Handle token cache clearing
    if args.clear_cache:
        clear_token_cache()
        return

    if args.verbose:
        log.setLevel(logging.DEBUG)
        # Don't modify root logger to avoid interference with our colored logging

    if args.apply:
        color_print("🔥 LIVE MODE: Files will be actually renamed!", "RED")
    else:
        color_print("🚫 DRY RUN MODE: No files will be renamed. Use --apply to apply changes.", "YELLOW")

    try:
        access_token = get_access_token(CLIENT_ID, CLIENT_SECRET)
    except Exception as exc:
        log.error("Failed to get access token: %s", exc)
        log.error("Please check your TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET environment variables")
        return

    # Collect all files from the specified directory:
    video_files = collect_files(args.directory)
    if not video_files:
        log.warning("No video files found in %s", args.directory)
        return

    color_print(f"Found {len(video_files)} video files in {args.directory}", "GREEN")

    try:
        channel_ids = identify_authors_from_directory(args.directory, config=CONFIG)
    except ValueError as exc:
        log.error(exc)
        return

    if not channel_ids:
        log.warning("No matching channels found in config for current directory")
        log.debug("Available channels in config:")
        for author, details in CONFIG.items():
            if isinstance(details, dict):
                log.debug("  - %s: %s", author, details.get('channel_id', []))
        return


    videos_by_channel = {}
    for channel_id in channel_ids:
        log.info("Fetching videos for author/channel: %s", channel_id)
        try:
            videos = fetch_videos(channel_id, access_token)
        except Exception as exc:
            log.error("Failed to fetch videos for %s: %s", channel_id, exc)
            continue

        if not videos:
            log.warning("No videos found for channel %s.", channel_id)
            continue
        log.info("Fetched %d videos from channel '%s'", len(videos), channel_id)
        videos_by_channel[channel_id] = videos

        # Only show first few videos to avoid spam
        if args.verbose:
            for video in videos:
                log.debug(
                    "Id: %s Created: %s, Title: \"%s\", Duration: %s",
                    video['id'], video['created_at'], video['title'], video['duration']
                )

    if not videos_by_channel:
        log.warning("No videos fetched from any channel")
        return

    # Update filenames based on API data, matching files to videos from correct channels
    update_filenames(video_files, videos_by_channel, dry_run=not args.apply)

    if not args.apply:
        color_print("\n💡 To apply these changes, run the script again with --apply flag", "CYAN")


if __name__ == "__main__":
    main()