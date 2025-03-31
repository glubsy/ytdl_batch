#!/bin/bash
# This script compares the files in a source directory with the files in multiple check directories.
# If a file in the source directory does not exist in any of the check directories, it is copied to a destination directory.
# Usage: ./rsync_compare_move.sh [--dry-run] <source_dir> <dest_dir> <check_dir1> [<check_dir2> ...] [--copy-path <specific_path>]
# Example: ./rsync_compare_move.sh [--dry-run] /path/to/source/ /path/to/destination/ /path/to/check1 /path/to/check2 --copy-path /specific/path
# 
# The --dry-run flag can be used to simulate the script without actually copying files.
# The --copy-path flag can be used to specify a specific path to copy the files to instead of the destination directory.
# The script uses rsync to compare the files in the source directory with the files in the check directories.
# If a file does not exist in any of the check directories, it is copied to the destination directory.
# If a file with the same base name but different extension exists in any of the check directories, it is considered a conflict and the file is not copied.
# The script prints a warning for each conflicting file and skips copying it.
# It also prints the files that are being copied and the destination directory they are being copied to.
# It can be used to compare and move files between directories, for example, to organize files or backup files to a specific location.

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
  echo "Usage: $0 [--dry-run] <source_dir> <dest_dir> <check_dir1> [<check_dir2> ...] [--copy-path <specific_path>]"
  exit 1
fi

# Shift the first two arguments to process the remaining as check directories
shift 2

# Check for the optional --copy-path parameter
COPY_PATH=""
CHECK_DIRS=()
while [[ $# -gt 0 ]]; do
  if [[ "$1" == "--copy-path" ]]; then
    COPY_PATH="$2"
    shift 2 # Remove the --copy-path argument and its value
  else
    CHECK_DIRS+=("$1")
    shift
  fi
done

# Ensure the copy path is valid if provided
if [[ -n "$COPY_PATH" && ! -d "$COPY_PATH" ]]; then
  echo "Error: The specified copy path '$COPY_PATH' is not a valid directory."
  exit 1
fi

# Initialize an array to store file names
file_list=()

# Only use rsync's output to get the list of files that are in DEST_DIR but not in SOURCE_DIR
RSYNC_COMMAND="rsync -vi -XrltDan --stats --info=progress2,stats2 $SOURCE_DIR $DEST_DIR"

OLD_IFS=$IFS
IFS=" "

# Read the output of the rsync command
while read -r line; do
  if [[ "$line" =~ ^">" ]]; then
    # Extract the filename from the rsync output
    filename=$(echo "$line" | awk '{sub(/^[^ ]+ +/, ""); print $0}')
    file_list+=("$filename")
  fi
done < <(eval "$RSYNC_COMMAND")

IFS=$OLD_IFS

# FIXME there might be an issue where the filename contains a parent directory
# such as for example: parent/filename.ext
# in this case, the script will not be able to find the file in the check directories

for file in "${file_list[@]}"; do
  # Filename without the extension
  base_name="${file%.*}"

  # Check if the file exists in any of the check directories
  file_exists=false
  existing_file_path=""
  conflicting_file=false
  conflicting_files=()
  for dir in "${CHECK_DIRS[@]}"; do
    # Check if the exact file exists in the directory or its subdirectories
    existing_path=$(find "$dir" -type f -name "$file" 2>/dev/null)
    if [[ -n "$existing_path" ]]; then
      file_exists=true
      existing_file_path="$existing_path"
      break
    fi

    # Check for conflicting files with the same base name but different extensions
    matches=$(find "$dir" -type f -name "$base_name.*" 2>/dev/null)
    if [[ -n "$matches" ]]; then
      conflicting_file=true
      conflicting_files+=("$matches")
    fi
  done

  # If the file exists, print its exact path and skip copying
  if [[ "$file_exists" == true ]]; then
    echo -e "Skipping as it already exists at:"
    echo -e "  $file -> $existing_file_path${RESET}"
    continue
  fi

  # If a conflicting file exists, print a warning and skip copying
  if [[ "$conflicting_file" == true ]]; then
    echo "${WARNING}This file appears to already exist with a different extension:${RESET}"
    for conflict in "${conflicting_files[@]}"; do
      echo "  $file -> $conflict"
    done
    continue
  fi

  # If the file does not exist in any directory, copy it to the target directory
  TARGET_DIR="$DEST_DIR"
  if [[ -n "$COPY_PATH" ]]; then
    TARGET_DIR="$COPY_PATH"
  fi

  echo -e "${GREEN}Copying $file to $TARGET_DIR${RESET}"
  if [[ "$DRY_RUN" == false ]]; then
    cp -vn --parents "$SOURCE_DIR/$file" "$TARGET_DIR/"
  fi
done