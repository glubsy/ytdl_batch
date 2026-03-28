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

MAX_TIME_DIFF=8  	# minutes
TS_EXT="ts"  		# file extension to look for
VERBOSE=true  		# Set to true to log files that are not ready for processing

RED="\u001b[31m"
GREEN="\u001b[32m"
YELLOW="\u001b[33;1m"
MAGENTA="\u001b[35;1m"
RESET="\u001b[0m"

# Return the block-device id (st_dev) for a path, walking up to an existing
# parent if the path does not exist yet.
get_block_device_id_for_path() {
	local p="$1"
	while [[ ! -e "$p" ]]; do
		# Reached root and still not found
		if [[ "$p" == "/" ]]; then
			break
		fi
		p="${p:h}"
		[[ -z "$p" ]] && p="/"
	done
	stat --print '%d' "$p" 2>/dev/null
}

# Returns 0 if a running ffmpeg process is writing to one of the destination
# block devices, 1 otherwise.
is_ffmpeg_writing_to_destination_device() {
	local -A dest_devices=()
	local device_id=""
	local pid=""
	local fd_path=""
	local fd_num=""
	local fd_flags=""
	local fd_target=""
	local fd_device=""
	local write_mode=0

	for _orig dest in "${(@kv)destinations}"; do
		device_id="$(get_block_device_id_for_path "$dest")"
		if [[ -n "$device_id" ]]; then
			dest_devices["$device_id"]=1
		fi
	done

	# No destination devices resolved means no possible conflict to gate on.
	[[ ${#dest_devices[@]} -eq 0 ]] && return 1

	for pid in ${(f)"$(pgrep -x ffmpeg 2>/dev/null)"}; do
		[[ -z "$pid" ]] && continue
		for fd_path in /proc/${pid}/fd/*(N); do
			fd_num="${fd_path:t}"
			fd_flags="$(awk '/^flags:/ {print $2}' /proc/${pid}/fdinfo/${fd_num} 2>/dev/null)"
			[[ -z "$fd_flags" ]] && continue

			# Linux fd flags are octal; low two bits indicate access mode:
			# 0=read-only, 1=write-only, 2=read-write.
			write_mode=$((8#${fd_flags} & 3))
			(( write_mode == 0 )) && continue

			fd_target="$(readlink -f "$fd_path" 2>/dev/null)"
			[[ -z "$fd_target" || ! -e "$fd_target" ]] && continue

			fd_device="$(stat --print '%d' "$fd_target" 2>/dev/null)"
			if [[ -n "$fd_device" && -n "${dest_devices[$fd_device]}" ]]; then
				return 0
			fi
		done
	done

	return 1
}

# Wait only if ffmpeg is writing to the same destination block device.
wait_for_ffmpeg_device_conflicts() {
	echo "Checking for ffmpeg writes on destination block device(s)..."
	while is_ffmpeg_writing_to_destination_device; do
		echo "Conflicting ffmpeg write detected, waiting 5 minutes..."
		sleep 300  # Wait 5 minutes
	done
	echo "No conflicting ffmpeg writes detected, proceeding with transcoding"
}

# Get file stats and check if ready to be processed
# Sets: file_mtime_seconds, file_size_bytes, file_diff_sec, file_now_seconds
# Returns 0 (true) if ready, 1 (false) if not
# Logs reason if file is not ready (when global VERBOSE is true)
get_file_stats_and_check_ready() {
	local f="$1"
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
		if [[ "$VERBOSE" == "true" ]]; then
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
	if [[ "$VERBOSE" == "true" ]]; then
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

# Only wait for conflicting ffmpeg writes if we actually have files to process
if [[ "$has_files_to_process" == "true" ]]; then
	wait_for_ffmpeg_device_conflicts
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
		if ! get_file_stats_and_check_ready "$f"; then
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
