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

# Load config variables, assuming it is located in the same directory as this script
config_file="${0%/*}/transcode_ts.config"
if [[ ! -e "${config_file}" ]]; then
	echo "Missing config file ${config_file}"
	exit 1
fi
source "${config_file}"

MAX_TIME_DIFF=10  # minutes
TS_EXT="ts"  # file extension to look for

RED="\u001b[31m"
GREEN="\u001b[32m"
YELLOW="\u001b[33;1m"
MAGENTA="\u001b[35;1m"
RESET="\u001b[0m"

# Scan for ts files and transcode them into destination
for orig dest in "${(@kv)destinations}"; do
	if [[ ! -d "${orig}" ]]; then
		echo "${YELLOW}$orig does not exist. Skipping.${RESET}"
		continue
	fi

	echo "Scanning for files to move from $orig -> $dest"

	# (N) glob qualifier equivalent to "setopt null_glob" to avoid getting a (blocking) error if no file is found
	for f in ${orig}/*.${TS_EXT}(N); do
		filename="$(basename $f)"
		echo "Found ${TS_EXT} file: $filename";

		# Have to make sure the file is not being written to currently
		
		now_seconds=$(date +%s)
		# Get ctime in seconds + size
		stat_data=$(stat --print '%Z %s' "$f")
		# Split string on whitespace and convert to array
		stat_data=(${(@s: :)stat_data})
		mtime_seconds=${stat_data[@]:0:1}  # same as ${stat_data[1]}, note that echo ${(t)mtime_seconds} returns scalar OwO
		size_bytes=${stat_data[@]:1:2}     # same as ${stat_data[2]}

		if [[ ${size_bytes} -le 1000 ]]; then
			echo "${YELLOW}$filename is ${size_bytes} bytes, too small to be a valid media file. Ignoring...${RESET}"
			continue
		fi

		# If file has not been modified in the last 10 minutes, 
		# we suppose the livestream is over and it is now safe to move the file
		diff_sec=$((${now_seconds} - ${mtime_seconds}))
		if [[ ${diff_sec} -ge $((${MAX_TIME_DIFF} * 60)) ]]; then
			echo "${filename} was modified $((${diff_sec}/60)) minutes ago (more than ${MAX_TIME_DIFF} minutes ago)."
			#echo "DEBUG stat\n$(stat ${f})"
			
			dest_filename="${filename%.ts}.mp4"
			echo "Will transcode to: $dest/$dest_filename"
			
			echo "Running: ffmpeg -i $f -c copy $dest/$dest_filename"
			ffmpeg -i "${f}" -c copy "${dest}/${dest_filename}"
			# DEBUG
			#ffprobe $f

			if [[ $? -eq 0 ]] && [[ ! -e "$dest/$dest_filename" ]]; then
				echo "${GREEN}Transcoded $f to $dest/$dest_filename.${RESET}";
				echo "Removing $f from source..."
				echo "rm $f"
			else
				echo "${YELLOW}ffmpeg encountered an error. Trying to move source file instead of transcoding...${RESET}"
				mkdir -p "$dest"
				mv "$f" "$dest/$filename)"
			        if [[ $? -eq 0 ]]; then
					echo "${YELLOW}Moved $f to $dest/$filename instead of transcoding!${RESET}"
				else
					echo "${RED}Something went wrong trying to move ${f} to ${dest}/${filename}. Please investigate!${RESET}"
				fi
			fi
		else
			echo "${MAGENTA}$filename is probably still being written to. Last changed ${diff_sec} seconds ago.${RESET}"
			#echo "DEBUG stat:\n$(stat "${f}")."
		fi
	done
done
