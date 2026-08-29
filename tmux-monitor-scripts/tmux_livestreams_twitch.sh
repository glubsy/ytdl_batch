#!/bin/bash

DETACH=0
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/tmux_livestreams"
TARGET="twitch"

if [ "${1}" = "--detach" ]; then
	DETACH=1
fi

CONFIG_FILE="${CONFIG_DIR}/twitch.local.sh"

load_local_config() {
	# shellcheck disable=SC1090
	if [ -f "${CONFIG_FILE}" ]; then
		. "${CONFIG_FILE}"
	elif [ -f "${SCRIPT_DIR}/twitch.local.sh" ]; then
		CONFIG_FILE="${SCRIPT_DIR}/twitch.local.sh"
		# shellcheck disable=SC1090
		. "${CONFIG_FILE}"
	else
		return 1
	fi

	if ! declare -p TTV_STREAMER_INDEX >/dev/null 2>&1 || ! declare -p TTV_STREAMERS >/dev/null 2>&1; then
		echo "Error: sourced Twitch config file ${CONFIG_FILE} must define TTV_STREAMER_INDEX and TTV_STREAMERS"
		return 1
	fi

	if [ "${TMUX_LIVESTREAMS_DEBUG:-0}" = "1" ]; then
		echo "Debug: loaded ${CONFIG_FILE}" >&2
		declare -p TTV_STREAMER_INDEX TTV_STREAMERS >&2
	fi

	return 0
}

if ! load_local_config; then
	echo "Error: expected Twitch config file at ${CONFIG_FILE}"
	exit 1
fi

echo "Using Twitch config file: ${CONFIG_FILE}"

DOWNLOAD_TARGET="${DOWNLOAD_TARGET:-${HOME}/livestreams}"

if [ -z "${SESS_NAME:-}" ]; then
	SESS_NAME="${TARGET}_monitors"
fi

if [ -z "${DEF_FILE:-}" ]; then
	DEF_FILE="/tmp/tmux_${TARGET}_livestream_session_definition"
fi

# save_livestream.py path for Twitch usage (wrapper script around streamlink)
# https://github.com/mrwnwttk/livestream_scripts
SL_PATH="${SL_PATH}"
if [ -z "${SL_PATH}" ]; then
	SL_PATH="${HOME}/bin/save_livestream"
fi
# Assuming streamlink is installed in a python venv at ${HOME}/venv
if [ -d "${HOME}/venv" ] && [ -f "${HOME}/venv/bin/streamlink" ]; then
	SL_CMD="source ${HOME}/venv/bin/activate && python ${SL_PATH}"
else
	SL_CMD="python3 ${SL_PATH}"
fi

# Note twitch Oauth can either be passed as argument like this:
# send-keys "python3 ${SL_PATH} --author-name Prune "https://www.twitch.tv/vtuber_prune" \"--twitch-api-header Authorization=OAuth token_value\"" C-m
# or by creating ${HOME}/.config/streamlink/config.twitch (recommended) with
# twitch-api-header=Authorization=OAuth token_value

# Use the index array for order
TTV_DEF="#set-option remain-on-exit on\n"
len=${#TTV_STREAMER_INDEX[@]}
i=0
while [ $i -lt $len ]; do
	name1="${TTV_STREAMER_INDEX[$i]}"
	IFS='|' read -r dir1 author1 url1 disp1 <<< "${TTV_STREAMERS["$name1"]}"
	if [ $((i+1)) -lt $len ]; then
		name2="${TTV_STREAMER_INDEX[$((i+1))]}"
		IFS='|' read -r dir2 author2 url2 disp2 <<< "${TTV_STREAMERS["$name2"]}"
		TTV_DEF+=$'\n'
		TTV_DEF+="neww -n \"${name1}+${name2}\" -c \"${DOWNLOAD_TARGET}/${dir1}\"\n"
		TTV_DEF+="send-keys \"${SL_CMD} --author-name \"${author1}\" \"${url1}\"\" C-m\n"
		TTV_DEF+="split-window -v -c \"${DOWNLOAD_TARGET}/${dir2}\"\n"
		TTV_DEF+="send-keys \"${SL_CMD} --author-name \"${author2}\" \"${url2}\"\" C-m\n"
		i=$((i+2))
	else
		# Odd one out: single window
		TTV_DEF+=$'\n'
		TTV_DEF+="neww -n \"${name1}\" -c \"${DOWNLOAD_TARGET}/${dir1}\"\n"
		TTV_DEF+="send-keys \"${SL_CMD} --author-name \"${author1}\" \"${url1}\"\" C-m\n"
		i=$((i+1))
	fi
done

DEF=${TTV_DEF}

echo "Recreating ${SESS_NAME} definition file as \"${DEF_FILE}\"..."
printf "%b" "${DEF}" > "${DEF_FILE}"

if [ "${DETACH}" -eq 1 ]; then
	if tmux has-session -t "${SESS_NAME}" >/dev/null 2>&1; then
		echo "tmux session \"${SESS_NAME}\" already exists"
	else
		echo "Starting new tmux session \"${SESS_NAME}\""
		tmux new-session -d -s "${SESS_NAME}" -P "tmux source-file ${DEF_FILE}"
	fi
else
	tmux attach -t "${SESS_NAME}" ||
	echo "Starting new tmux session \"${SESS_NAME}\""; tmux new-session -s "${SESS_NAME}" -P "tmux source-file ${DEF_FILE}" ;
fi
