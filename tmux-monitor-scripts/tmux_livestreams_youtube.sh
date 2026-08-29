#!/bin/bash

DETACH=0
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/tmux_livestreams"
TARGET="youtube"

if [ "${1}" = "--detach" ]; then
	DETACH=1
fi

CONFIG_FILE="${CONFIG_DIR}/youtube.local.sh"

load_local_config() {
	# shellcheck disable=SC1090
	if [ -f "${CONFIG_FILE}" ]; then
		. "${CONFIG_FILE}"
		return 0
	fi

	# shellcheck disable=SC1090
	if [ -f "${SCRIPT_DIR}/youtube.local.sh" ]; then
		CONFIG_FILE="${SCRIPT_DIR}/youtube.local.sh"
		. "${CONFIG_FILE}"
		return 0
	fi

	return 1
}

if ! load_local_config; then
	echo "Error: expected YouTube config file at ${CONFIG_FILE}"
	exit 1
fi

echo "Using YouTube config file: ${CONFIG_FILE}"

DOWNLOAD_TARGET="${DOWNLOAD_TARGET:-${HOME}/livestreams}"

if [ -z "${SESS_NAME:-}" ]; then
	SESS_NAME="${TARGET}_monitor"
fi

if [ -z "${DEF_FILE:-}" ]; then
	DEF_FILE="/tmp/tmux_${TARGET}_livestream_session_definition"
fi

if [ -z "${BGUTIL_PROVIDER_DIR:-}" ] || [ -z "${LS_SAVER:-}" ]; then
	echo "Error: sourced YouTube config file ${CONFIG_FILE} must define BGUTIL_PROVIDER_DIR and LS_SAVER"
	exit 1
fi

if [ "${TMUX_LIVESTREAMS_DEBUG:-0}" = "1" ]; then
	echo "Debug: loaded ${CONFIG_FILE}" >&2
	declare -p YT_STREAMER_INDEX YT_STREAMERS >&2
fi

# Make sure to
# ln -s /path/to/${LS_SAVER}.py ${HOME}/bin/${LS_SAVER}; chmod +x ${HOME}/bin/${LS_SAVER}
# Might have to copy the symlink into ${HOME}/venv/bin/ too
LS_SAVER_CMD="source ${HOME}/venv/bin/activate && ${LS_SAVER} monitor"

build_youtube_cmd() {
	local qual="$1"
	local disp="$2"
	local q_disp

	printf -v q_disp '%q' "$disp"
	printf '%s -q %s -d -s %s' "$LS_SAVER_CMD" "$qual" "$q_disp"
}

validate_streamer_key() {
	case "$1" in
		*[[:space:]]*)
			echo "Error: streamer key "$1" in ${CONFIG_FILE} contains whitespace. Use an underscore-safe key and keep the display name in the value." >&2
			exit 1
			;;
	esac
}

ensure_bgutil_provider() {
	if [ ! -d "${HOME}/opt" ]; then
		mkdir -p "${HOME}/opt"
	fi

	if [ ! -d "${BGUTIL_PROVIDER_DIR}" ]; then
		git init "${BGUTIL_PROVIDER_DIR}"
		cd "${BGUTIL_PROVIDER_DIR}" || exit 1
		git remote add origin https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git
		if [ -n "${BGUTIL_PROVIDER_COMMIT:-}" ]; then
			git fetch --depth 1 origin "${BGUTIL_PROVIDER_COMMIT}"
		else
			git fetch --depth 1 origin HEAD
		fi
		git checkout FETCH_HEAD
		deno install --allow-scripts=npm:canvas --frozen
	else
		cd "${BGUTIL_PROVIDER_DIR}" || exit 1
	fi
}

ensure_latest_ytdlp() {
	if [ ! -d "${HOME}/venv" ] || [ ! -f "${HOME}/venv/bin/activate" ]; then
		return
	fi

	# shellcheck disable=SC1091
	source "${HOME}/venv/bin/activate"
	pip install --upgrade yt-dlp
	pip install --upgrade bgutil-ytdlp-pot-provider
	deactivate
}

start_bgutil_provider() {
	ensure_bgutil_provider

	if pgrep -f "bgutil-ytdlp-pot-provider/.*/src/main.ts" >/dev/null 2>&1; then
		return
	fi

	cd "${BGUTIL_PROVIDER_DIR}/server/node_modules" || exit 1
	deno run --allow-env --allow-net --allow-ffi=. --allow-read=. ../src/main.ts 2>&1 >/dev/null &
	# Uncomment to store logs in a file instead of discarding them:
	# >"${HOME}/.cache/bgutil-ytdlp-pot-provider.log" 2>&1 &
}

YT_DEF="#set-option remain-on-exit on\n"
len=${#YT_STREAMER_INDEX[@]}
i=0
while [ $i -lt $len ]; do
	name1="${YT_STREAMER_INDEX[$i]}"
	validate_streamer_key "$name1"
	IFS='|' read -r dir1 disp1 qual1 <<< "${YT_STREAMERS["$name1"]}"
	if [ $((i+1)) -lt $len ]; then
		name2="${YT_STREAMER_INDEX[$((i+1))]}"
		validate_streamer_key "$name2"
		IFS='|' read -r dir2 disp2 qual2 <<< "${YT_STREAMERS["$name2"]}"
		YT_DEF+=$'\n'
		YT_DEF+="neww -n \"${name1}+${name2}\" -c \"${DOWNLOAD_TARGET}/${dir1}\"\n"
		cmd1="$(build_youtube_cmd "$qual1" "$disp1")"
		YT_DEF+="send-keys \"${cmd1}\" C-m\n"
		YT_DEF+="split-window -v -c \"${DOWNLOAD_TARGET}/${dir2}\"\n"
		cmd2="$(build_youtube_cmd "$qual2" "$disp2")"
		YT_DEF+="send-keys \"${cmd2}\" C-m\n"
		i=$((i+2))
	else
		YT_DEF+=$'\n'
		YT_DEF+="neww -n \"${name1}\" -c \"${DOWNLOAD_TARGET}/${dir1}\"\n"
		cmd1="$(build_youtube_cmd "$qual1" "$disp1")"
		YT_DEF+="send-keys \"${cmd1}\" C-m\n"
		i=$((i+1))
	fi
done

DEF=${YT_DEF}

if [ "${TMUX_LIVESTREAMS_DEBUG:-0}" != "1" ]; then
	ensure_latest_ytdlp
	start_bgutil_provider
fi

echo "Recreating ${SESS_NAME} definition file as \"${DEF_FILE}\"..."
printf "%b" "${DEF}" > "${DEF_FILE}"

if [ "${TMUX_LIVESTREAMS_DEBUG:-0}" = "1" ]; then
	echo "Debug: generated definition file ${DEF_FILE}"
	cat "${DEF_FILE}"
	exit 0
fi

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
