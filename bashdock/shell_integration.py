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
