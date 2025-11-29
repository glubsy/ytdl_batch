#!/bin/zsh


# Purpose: move .ts files from one location to a destination while transcoding them with ffmpeg.
# 0. load config file, setting location to scan, destinations depending on initial location of file 
# (need a default location if a change in the initial location was not anticipated)
# 1. list files with .ts extension
# 2. check their mtime, has to be > 10 minutes from now
# 3. execute ffmpeg -i orig_file.ts -c copy dest_file.mp4
# 4. check that the destination file exists, report any error (eg. corrupt packet) detected by ffmpeg
# 5. remove original file, or copy it over in case of error (to avoid letting data pile up and fill up storage device)
# 6. trigger download subs script in dest dir
# This script should be executed every 30 minutes by systemd timer, but only one instance of the script should be allowed to run
#
#

config_file="${TS_CONFIG:="${HOME}/.config/transcode_ts.config"}"

if [[ ! -e "${config_file}" ]]; then
	echo "Missing config file ${config_file}"

	# Load config variables, assuming it is located in the same directory as this script
	config_file="${0%/*}/transcode_ts.config"
	if [[ ! -e "${config_file}" ]]; then
		echo "Missing config file ${config_file}"
		exit 1
	fi
fi
source "${config_file}"

MAX_TIME_DIFF=10  # minutes
TS_EXT="ts"  # file extension to look for

RED="\u001b[31m"
GREEN="\u001b[32m"
YELLOW="\u001b[33;1m"
MAGENTA="\u001b[35;1m"
RESET="\u001b[0m"

# Wait for ytdlp processes to finish before starting transcoding
wait_for_ytdlp_to_finish() {
    echo "Checking for running ytdlp processes..."
    while pgrep -x ytdlp > /dev/null || pgrep -x yt-dlp > /dev/null; do
        echo "ytdlp is running, waiting 5 minutes before checking again..."
        sleep 300  # Wait 5 minutes
    done
    echo "No ytdlp processes detected, proceeding with transcoding"
}

# Get file stats and check if ready to be processed
# Sets: file_mtime_seconds, file_size_bytes, file_diff_sec, file_now_seconds
# Returns 0 (true) if ready, 1 (false) if not
# Logs reason if file is not ready (when $2 is "verbose")
get_file_stats_and_check_ready() {
	local f="$1"
	local verbose="$2"
	file_now_seconds=$(date +%s)
	# Get mtime in seconds + size
	local stat_data=$(stat --print '%Z %s' "$f" 2>/dev/null)
	
	if [[ -z "$stat_data" ]]; then
		return 1
	fi
	
	# Split string on whitespace and convert to array
	stat_data=(${(@s: :)stat_data})
	file_mtime_seconds=${stat_data[@]:0:1}  # same as ${stat_data[1]}
	file_size_bytes=${stat_data[@]:1:2}     # same as ${stat_data[2]}
	file_diff_sec=$((${file_now_seconds} - ${file_mtime_seconds}))
	
	# File must be larger than 1000 bytes
	if [[ ${file_size_bytes} -le 1000 ]]; then
		if [[ "$verbose" == "verbose" ]]; then
			echo "${YELLOW}$(basename "$f") is ${file_size_bytes}" \
			     "bytes, too small. Ignoring...${RESET}"
		fi
		return 1
	fi
	
	# File must not have been modified in the last MAX_TIME_DIFF minutes
	if [[ ${file_diff_sec} -ge $((${MAX_TIME_DIFF} * 60)) ]]; then
		return 0
	fi
	
	# File is still being written to
	if [[ "$verbose" == "verbose" ]]; then
		echo "${MAGENTA}$(basename "$f") is probably still being" \
		     "written to. Last changed ${file_diff_sec} seconds" \
		     "ago.${RESET}"
	fi
	return 1
}

# First pass: check if there are any files to process
has_files_to_process=false
for orig dest in "${(@kv)destinations}"; do
	if [[ ! -d "${orig}" ]]; then
		continue
	fi
	
	for f in ${orig}/*.${TS_EXT}(N); do
		if get_file_stats_and_check_ready "$f"; then
			has_files_to_process=true
			break 2  # Break out of both loops
		fi
	done
done

# Only wait for ytdlp if we actually have files to process
if [[ "$has_files_to_process" == "true" ]]; then
	wait_for_ytdlp_to_finish
else
	echo "No files ready to process. Exiting."
	exit 0
fi

# Scan for ts files and transcode them into destination
for orig dest in "${(@kv)destinations}"; do
	if [[ ! -d "${orig}" ]]; then
		echo "${YELLOW}$orig does not exist. Skipping.${RESET}"
		continue
	fi

	# echo "Scanning for files to move from $orig -> $dest"

	# (N) glob qualifier equivalent to "setopt null_glob"
	# to avoid getting a (blocking) error if no file is found
	for f in ${orig}/*.${TS_EXT}(N); do
		filename="$(basename $f)"
		
		# Check if file is ready for processing
		# (also populates file_* variables and logs if not ready)
		if ! get_file_stats_and_check_ready "$f" "verbose"; then
			continue
		fi
		
		# File is ready - use the already-fetched stats for logging
		echo "${filename} was modified $((${file_diff_sec}/60))" \
		     "minutes ago (more than ${MAX_TIME_DIFF} minutes ago)."
		
		dest_filename="${filename%.ts}.mp4"
		echo "Transcoding to: $dest/$dest_filename"

		ffmpeg -hide_banner -y -nostats -ignore_unknown -i "${f}" -c copy "${dest}/${dest_filename}"
		ffmpeg_exit=$?

		if [[ ${ffmpeg_exit} -eq 0 ]] && [[ -f "$dest/$dest_filename" ]]; then
			echo "${GREEN}Transcoded $f to" \
			     "$dest/$dest_filename.${RESET}";
			echo "Removing $f from source..."
			rm $f
		else
			echo "${YELLOW}ffmpeg's exit code was ${ffmpeg_exit}." \
			     "Trying to move source file instead of" \
			     "transcoding...${RESET}"
			mkdir -p "$dest"
			mv "$f" "$dest/$filename"
			if [[ $? -eq 0 ]]; then
				echo "${YELLOW}Moved $f to $dest/$filename" \
				     "instead of transcoding!${RESET}"
			else
				echo "${RED}Something went wrong trying to move" \
				     "${f} to ${dest}/${filename}." \
				     "Please investigate!${RESET}"
			fi
		fi
	done
done
