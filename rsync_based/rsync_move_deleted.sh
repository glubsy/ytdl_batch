#!/bin/bash
# When doing a rsync between a source and a destination, check that files that are
# marked for deletion do not actually exist in one of the check directories.
# If the file exists, and as to avoid deleting them with rsync only to recreate
# them afterwards in a different location on the same storage device, move them
# to the destination directory instead.
# This saves time and avoids unnecessary disk writes.
# If a file in the source directory does not exist in any of the check directories, it is move to the move-path directory.
# Usage: ./rsync_move_deleted.sh [--dry-run] <source_dir> <dest_dir> <check_dir1> [<check_dir2> ...] [--move-path <specific_path>]
# Example: ./rsync_move_deleted.sh [--dry-run] /path/to/source/ /path/to/destination/ /path/to/check1 /path/to/check2 --move-path /specific/path
#
# The --dry-run flag can be used to simulate the script without actually moving files.
# The --move-path flag can be used to specify a specific path to copy the files to instead of the destination directory.
# The script uses rsync to compare the files in the source directory with the files in the check directories.
# If a file is marked for deletion, it is checked if it exists in any of the check directories.
# If the file exists, it is moved to the destination directory (the --move-path parameter).

# ANSI color codes for highlighting the output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
MAGENTA='\033[0;35m'
RESET='\033[0m'

# Check if the first argument is --dry-run
DRY_RUN=false
if [[ "$1" == "--dry-run" ]]; then
  DRY_RUN=true
  shift # Remove the --dry-run argument
fi

# Assign the next two arguments as source and destination directories
SOURCE_DIR="$1"
DEST_DIR="$2"

# Ensure source and destination directories are provided
if [[ -z "$SOURCE_DIR" || -z "$DEST_DIR" ]]; then
  echo "Error: Source and destination directories must be specified."
  echo "Usage: $0 [--dry-run] <source_dir> <dest_dir> <check_dir1> [<check_dir2> ...] --move-path <specific_path>"
  exit 1
fi

# Shift the first two arguments to process the remaining as check directories
shift 2

# Check for the optional --move-path parameter
MOVE_PATH=""
CHECK_DIRS=()
while [[ $# -gt 0 ]]; do
  if [[ "$1" == "--move-path" ]]; then
    MOVE_PATH="$2"
    shift 2 # Remove the --move-path argument and its value
  else
    CHECK_DIRS+=("$1")
    shift
  fi
done

# Ensure the copy path is valid if provided
if [[ -n "$MOVE_PATH" && ! -d "$MOVE_PATH" ]]; then
  echo "Error: The specified move path '$MOVE_PATH' is not a valid directory."
  exit 1
fi

# Initialize an array to store file names
file_list=()

# Only use rsync's output to get the list of files that are in DEST_DIR but not in SOURCE_DIR
RSYNC_COMMAND="rsync -vi -XrltDan --delete --stats --info=progress2,stats2 $SOURCE_DIR $DEST_DIR"

OLD_IFS=$IFS
IFS=" "

# Read the output of the rsync command
while read -r line; do
  if [[ "$line" =~ ^"*deleting" ]]; then
    # Extract the filename from the rsync output
    filename=$(echo "$line" | awk '{sub(/^[^ ]+ +/, ""); print $0}')
    # Extract only the basename (filename without parent directories)
    basename=$(basename "$filename")
    file_list+=("$filename")
  fi
done < <(eval "$RSYNC_COMMAND")

IFS=$OLD_IFS

echo -e "Number of files marked for deletion: ${#file_list[@]}"

for file in "${file_list[@]}"; do
  # Filename without the extension
  base_name="${file%.*}"
  extension="${file##*.}" # Extract the file extension

  matches=$(find "${CHECK_DIRS[@]}" -type f -name "$base_name.*" 2>/dev/null)

  file_exists=false
  existing_file_path=""
  same_base_name=false
  same_base_names=()

  # Parse the results of find
  while IFS= read -r match; do
    # Extract the extension of the found file
    found_extension="${match##*.}"

    # Check if the found file has the same extension
    if [[ "$found_extension" == "$extension" ]]; then
      file_exists=true
      existing_file_path="$match"
      break
    fi

    # If the found file has a different extension, mark it as a conflict
    if [[ "$found_extension" != "$extension" ]]; then
      same_base_name=true
      same_base_names+=("$match")
    fi
  done <<< "$matches"

  if [[ -z "$matches" ]]; then
    continue
  elif [[ $file_exists == false && $same_base_name == true ]]; then
    echo -e "${YELLOW}Found similar base name but different extension:${RESET}"
    for same_base_name in "${same_base_names[@]}"; do
      echo "  $file -> $same_base_name"
    done
    continue
  fi

  # If the file exists, print its exact path and skip copying
  echo -e "Found exact filename in check dir:"
  echo -e "  $file -> ${matches[@]}"
  echo -e "${GREEN}Moving "$DEST_DIR$file" to $MOVE_PATH${RESET}"
  if [[ "$DRY_RUN" == false ]]; then
    mv -vn "$DEST_DIR$file" "$MOVE_PATH/"
  fi
done