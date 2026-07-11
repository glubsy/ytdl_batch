#!/bin/bash

O="${0##*/}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DETACH=0
SESS_NAME=""

if [ "${2}" = "--detach" ]; then
	DETACH=1
fi

case "${1}" in
	twitch|youtube)
		SESS_NAME="${1}_monitors"
		if [ "${DETACH}" -eq 1 ] && tmux has-session -t "${SESS_NAME}" >/dev/null 2>&1; then
			echo "tmux session \"${SESS_NAME}\" already exists"
			exit 0
		fi

		export SESS_NAME

		if [ "${DETACH}" -eq 1 ]; then
			exec bash "${SCRIPT_DIR}/tmux_livestreams_${1}.sh" --detach
		fi
		exec bash "${SCRIPT_DIR}/tmux_livestreams_${1}.sh"
		;;
	*)
		echo "Usage: ${O} [twitch|youtube] [--detach]"
		exit 0
		;;
esac
