"""Load login startup files, then report the directory at each Bash prompt."""
import ntpath
import tempfile
from pathlib import Path


INIT_SCRIPT = r'''# bashdock interactive startup, private to this shell.
# Follow Bash's login startup-file order, then install our prompt hook.
if [[ -r /etc/profile ]]; then source /etc/profile; fi
for __bashdock_profile in "$HOME/.bash_profile" "$HOME/.bash_login" "$HOME/.profile"; do
    if [[ -r "$__bashdock_profile" ]]; then
        source "$__bashdock_profile"
        break
    fi
done
unset __bashdock_profile
if [[ -n ${BASHDOCK_START_DIR-} ]]; then
    cd -- "$BASHDOCK_START_DIR"
    unset BASHDOCK_START_DIR
fi
# Keep this private session token after the one-time startup acknowledgement.
__bashdock_timing_session=${BASHDOCK_SESSION-}
__bashdock_command_file=${BASHDOCK_COMMAND_FILE-}
unset BASHDOCK_COMMAND_FILE
__bashdock_command_load() {
    __bashdock_command_previous=$?
    local __bashdock_payload
    [[ -n $__bashdock_command_file && -f $__bashdock_command_file ]] || return 1
    IFS= builtin read -r -d '' __bashdock_payload < "$__bashdock_command_file" || :
    __bashdock_command_id=${__bashdock_payload%%$'\n'*}
    __bashdock_command_body=${__bashdock_payload#*$'\n'}
    [[ $__bashdock_command_id =~ ^[a-f0-9]{32}$ ]] || return 1
    builtin printf '%s\n' "$__bashdock_command_body"
    builtin history -s -- "$__bashdock_command_body" 2>/dev/null || :
}
__bashdock_command_begin() {
    local __bashdock_previous=$2
    __bashdock_command_id=$1
    builtin printf '\033]777;bashdock-command;%s;%s;start;%s\007' \
        "$__bashdock_timing_session" "$__bashdock_command_id" "$EPOCHREALTIME"
    return "$__bashdock_previous"
}
__bashdock_command_finish() {
    local __bashdock_exit=$?
    if [[ -n ${__bashdock_command_id-} ]]; then
        builtin printf '\033]777;bashdock-command;%s;%s;done;%s;%s\007' \
            "$__bashdock_timing_session" "$__bashdock_command_id" "$__bashdock_exit" "$EPOCHREALTIME"
        unset __bashdock_command_id __bashdock_command_body __bashdock_command_previous
    fi
    return "$__bashdock_exit"
}
# Readline executes this binding's eval at shell scope, without putting its
# implementation in the input line or history. Only the literal button script
# is echoed and saved. Support both Emacs and vi keymaps.
if [[ -n $__bashdock_command_file ]]; then
    for __bashdock_keymap in emacs-standard vi-insert vi-command; do
        bind -m "$__bashdock_keymap" -x '"\C-x\C-b":if __bashdock_command_load; then __bashdock_command_begin "$__bashdock_command_id" "$__bashdock_command_previous"; builtin eval -- "$__bashdock_command_body"; __bashdock_command_finish; __bashdock_report_cwd; fi'
    done
    unset __bashdock_keymap
fi
# Capture the script's exit status before any user prompt hooks can alter it.
PROMPT_COMMAND=(__bashdock_command_finish "${PROMPT_COMMAND[@]}")
__bashdock_report_cwd() {
    local __bashdock_status=$?
    local __bashdock_path
    history -a 2>/dev/null || :
    __bashdock_path=$(cygpath -am -- "$PWD" 2>/dev/null) || __bashdock_path=$PWD
    printf '\033]777;bashdock-cwd;%s\007' "$__bashdock_path"
    if [[ -n ${BASHDOCK_SESSION-} ]]; then
        printf '\033]777;bashdock-ready;%s\007' "$BASHDOCK_SESSION"
        unset BASHDOCK_SESSION
    fi
    return "$__bashdock_status"
}
PROMPT_COMMAND+=(__bashdock_report_cwd)
'''


def create_init_file():
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                     prefix="bashdock-", suffix=".bash", delete=False) as stream:
        stream.write(INIT_SCRIPT)
        return Path(stream.name)


def valid_reported_directory(path):
    """Only accept absolute drive/UNC paths, never relative terminal payloads."""
    if not isinstance(path, str) or any(ord(ch) < 32 for ch in path):
        return False
    drive, tail = ntpath.splitdrive(path)
    return bool(drive and tail.startswith(("/", "\\")))


def command_file_for(init_file):
    return Path(init_file).with_suffix('.command')
