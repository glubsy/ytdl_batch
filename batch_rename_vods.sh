#!/bin/bash

# Script to run Twitch VOD renaming on multiple directories
# Usage: ./batch_rename_vods.sh [base_directory] [options]
#
# Examples:
#   ./batch_rename_vods.sh /tmp/streamers
#   ./batch_rename_vods.sh /tmp/streamers --apply
#   ./batch_rename_vods.sh /tmp/streamers --verbose

# Note: Not using 'set -e' to allow graceful error handling per directory

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print colored output
print_color() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 <base_directory> [options]"
    echo ""
    echo "This script runs the Twitch VOD renaming tool on each subdirectory"
    echo "found in the specified base directory."
    echo ""
    echo "Arguments:"
    echo "  base_directory    Directory containing streamer folders (e.g., /tmp/streamers)"
    echo ""
    echo "Options (passed to rename_vods.py):"
    echo "  --apply          Actually apply the filename changes (default: dry-run mode)"
    echo "  --verbose        Enable verbose logging"
    echo ""
    echo "Examples:"
    echo "  $0 /tmp/streamers"
    echo "  $0 /tmp/streamers --apply"
    echo "  $0 /tmp/streamers --verbose --apply"
    echo ""
    echo "Note: The script expects the rename_vods.py to be located in the 'twitch' subdirectory"
    echo "      relative to where this script is located."
}

# Check if at least one argument is provided
if [ $# -lt 1 ]; then
    print_color "$RED" "Error: Base directory not specified"
    echo ""
    show_usage
    exit 1
fi

# Get the base directory and remaining arguments
BASE_DIR="$1"
shift  # Remove first argument, keep the rest as options for rename_vods.py
RENAME_OPTIONS="$@"

# Check if base directory exists
if [ ! -d "$BASE_DIR" ]; then
    print_color "$RED" "Error: Directory '$BASE_DIR' does not exist"
    exit 1
fi

# Get the script directory to locate rename_vods.py
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RENAME_SCRIPT="$SCRIPT_DIR/twitch/rename_vods.py"

# Check if rename_vods.py exists
if [ ! -f "$RENAME_SCRIPT" ]; then
    print_color "$RED" "Error: rename_vods.py not found at: $RENAME_SCRIPT"
    print_color "$YELLOW" "Make sure this script is in the same directory as the 'twitch' folder"
    exit 1
fi

process_directory() {
    local dir="$1"
    local dir_name=$(basename "$dir")
    
    print_color "$BLUE" "========================================="
    print_color "$CYAN" "Processing directory: $dir_name"
    print_color "$BLUE" "========================================="
    
    # Check if directory contains video files
    video_count=$(find "$dir" -maxdepth 1 -name "*.mp4" -o -name "*.ts" | wc -l)
    
    if [ "$video_count" -eq 0 ]; then
        print_color "$YELLOW" "No video files found in $dir_name, skipping..."
        return 0  # Explicitly return success for skipped directories
    fi
    
    print_color "$GREEN" "Found $video_count video files in $dir_name"

    echo ""
    # Run the rename script and handle exit codes gracefully
    python3 "$RENAME_SCRIPT" --directory "$dir" $RENAME_OPTIONS
    exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        print_color "$GREEN" "✅ Successfully processed $dir_name"
        return 0
    else
        print_color "$RED" "❌ Failed to process $dir_name (exit code: $exit_code)"
        return 1
    fi
    
    echo ""
}

# Main execution
print_color "$GREEN" "🚀 Starting batch VOD renaming process"
print_color "$CYAN" "Base directory: $BASE_DIR"
print_color "$CYAN" "Options: ${RENAME_OPTIONS:-'(none - dry run mode)'}"
echo ""

# Count total directories
total_dirs=$(find "$BASE_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l)

if [ "$total_dirs" -eq 0 ]; then
    print_color "$YELLOW" "No subdirectories found in $BASE_DIR"
    exit 0
fi

print_color "$CYAN" "Found $total_dirs directories to process"
echo ""

# Process each directory
processed=0
failed=0

for dir in "$BASE_DIR"/*; do
    if [ -d "$dir" ]; then
        echo "About to process: $(basename "$dir")"
        
        if process_directory "$dir"; then
            processed=$((processed + 1))
        else
            failed=$((failed + 1))
            print_color "$RED" "Failed processing: $(basename "$dir")"
        fi

        echo "Processed directories: $processed / $total_dirs"

        # Add a separator between directories for readability
        if [ $((processed + failed)) -lt $total_dirs ]; then
            echo ""
            echo "Continuing to next directory..."
            echo ""
        fi
    fi
done
 
print_color "$BLUE" "========================================="
print_color "$GREEN" "📊 BATCH PROCESSING SUMMARY"
print_color "$BLUE" "========================================="
print_color "$GREEN" "Total directories: $total_dirs"
print_color "$GREEN" "Successfully processed: $processed"

if [ $failed -gt 0 ]; then
    print_color "$RED" "Failed: $failed"
fi

if [ "$processed" -eq "$total_dirs" ]; then
    print_color "$GREEN" "🎉 All directories processed successfully!"
else
    print_color "$YELLOW" "⚠️  Some directories had issues. Check the output above."
fi

# Final reminder about dry-run mode
if [[ "$RENAME_OPTIONS" != *"--apply"* ]]; then
    echo ""
    print_color "$YELLOW" "💡 This was a DRY RUN. To actually apply changes, add --apply flag:"
    print_color "$CYAN" "   $0 $BASE_DIR $RENAME_OPTIONS --apply"
fi

echo ""