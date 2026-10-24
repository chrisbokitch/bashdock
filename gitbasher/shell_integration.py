"""Load login startup files, then report the directory at each Bash prompt."""
import ntpath
import tempfile
from pathlib import Path


INIT_SCRIPT = r'''# gitbasher interactive startup, private to this shell.
# Follow Bash's login startup-file order, then install our prompt hook.
if [[ -r /etc/profile ]]; then source /etc/profile; fi
for __gitbasher_profile in "$HOME/.bash_profile" "$HOME/.bash_login" "$HOME/.profile"; do
    if [[ -r "$__gitbasher_profile" ]]; then
        source "$__gitbasher_profile"
        break
    fi
done
unset __gitbasher_profile
if [[ -n ${GITBASHER_START_DIR-} ]]; then
    cd -- "$GITBASHER_START_DIR"
    unset GITBASHER_START_DIR
fi
__gitbasher_report_cwd() {
    local __gitbasher_status=$?
    local __gitbasher_path
    history -a 2>/dev/null || :
    __gitbasher_path=$(cygpath -am -- "$PWD" 2>/dev/null) || __gitbasher_path=$PWD
    printf '\033]777;gitbasher-cwd;%s\007' "$__gitbasher_path"
    return "$__gitbasher_status"
}
PROMPT_COMMAND+=(__gitbasher_report_cwd)
'''


def create_init_file():
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                     prefix="gitbasher-", suffix=".bash", delete=False) as stream:
        stream.write(INIT_SCRIPT)
        return Path(stream.name)


def valid_reported_directory(path):
    """Only accept absolute drive/UNC paths, never relative terminal payloads."""
    if not isinstance(path, str) or any(ord(ch) < 32 for ch in path):
        return False
    drive, tail = ntpath.splitdrive(path)
    return bool(drive and tail.startswith(("/", "\\")))
