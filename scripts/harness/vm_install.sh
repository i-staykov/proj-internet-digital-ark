#!/usr/bin/env bash
# The bank host, set up from the laptop: `just vm install` pipes this to the VM after its
# local.env. As the login, `sudo -n` for the packages, the fleet user and linger only: uv,
# just and gh under ~/.local/bin, the ark clone on `live`, the fleet clone, its own walk lane,
# the tick as a systemd user timer that outlives a logout and fires only once the store is
# there, and the fleet as ARK_FLEET_USER, an ordinary user whose runners read this login's
# staged snapshot by path (ark-fleet README.md). Idempotent. `gh auth login` there is the
# owner's, once (docs/ops/runbook.md).
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
mkdir -p ~/.local/bin ~/GitHub ~/.config/systemd/user
root() { echo "REFUSED: sudo asks a password; as root first: $1" >&2; exit 1; }

command -v uv > /dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh -s -- -q
command -v just > /dev/null ||
    curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/.local/bin
if ! command -v gh > /dev/null; then
    v=$(curl -sI https://github.com/cli/cli/releases/latest | sed -n 's#^location:.*/v\([0-9.]*\).*#\1#ip')
    name="gh_${v}_linux_$(dpkg --print-architecture)"
    curl -sL "https://github.com/cli/cli/releases/download/v$v/$name.tar.gz" |
        tar -xz -C ~/.local/bin --strip-components=2 "$name/bin/gh"
fi
# pandoc builds the archive's Open Research Questions.docx.
dpkg -s p7zip-full pigz pandoc > /dev/null 2>&1 || sudo -n apt-get install -y -qq p7zip-full pigz pandoc ||
    root "apt-get install -y p7zip-full pigz pandoc"
# rclone from its own release, as gh above: a distribution's is too old for Drive's sha256. Its
# remote is the owner's, once, its token made on the laptop since the VM has no browser; the
# secret stays in ~/.config/rclone.
if ! command -v rclone > /dev/null; then
    zip=$(mktemp)
    curl -sL "https://downloads.rclone.org/rclone-current-linux-$(dpkg --print-architecture).zip" -o "$zip"
    7z e -y -o"$HOME/.local/bin" "$zip" '*/rclone' > /dev/null && chmod 755 ~/.local/bin/rclone
    rm -f "$zip"
fi
[ ! -f ~/.config/rclone/rclone.conf ] || chmod 600 ~/.config/rclone/rclone.conf
rclone listremotes 2> /dev/null | grep -qx gdrive: || cat << 'STEP'
no gdrive remote. The owner, once: on the laptop
    rclone authorize "drive" '{"scope":"drive.file"}'
then here, with the JSON it prints
    rclone config create gdrive drive scope=drive.file config_is_local=false config_token='<json>'
STEP

[ -d ~/ark/.git ] || git clone -q -b live https://github.com/i-staykov/proj-internet-digital-ark ~/ark
git -C ~/ark pull -q --ff-only
[ -f ~/ark-local.env ] && mv ~/ark-local.env ~/ark/local.env
if gh auth status > /dev/null 2>&1; then
    gh auth setup-git
    [ -d ~/GitHub/ark-fleet/.git ] || gh repo clone i-staykov/ark-fleet ~/GitHub/ark-fleet -- -q
else
    echo "gh: not logged in; the tick drains nothing and pushes nothing until 'gh auth login'"
fi
(cd ~/ark && uv sync -q && mkdir -p data/logs && just walk install)

cp ~/ark/scripts/harness/ark-sync.service ~/ark/scripts/harness/ark-sync.timer ~/.config/systemd/user/
systemctl --user daemon-reload
[ "$(loginctl show-user "$(id -un)" -p Linger --value 2> /dev/null)" = yes ] ||
    loginctl enable-linger 2> /dev/null || sudo -n loginctl enable-linger "$(id -un)" ||
    root "loginctl enable-linger $(id -un)"
systemctl --user enable --now ark-sync.timer
systemctl --user list-timers ark-sync.timer --no-pager --no-legend

# The fleet user: a home and linger, and this login's side of their meeting point. The
# legs traverse ~/ark to read output/ by path and nothing else of the clone: data/, private/
# and local.env are closed to them. `just vm install` then runs ark-fleet's own installer as
# that user, the runner token on its stdin.
fleet=$(sed -n 's/^ARK_FLEET_USER=//p' ~/ark/local.env | tr -d "\"'")
[ -n "$fleet" ] || { echo "no ARK_FLEET_USER in local.env, so no fleet here"; exit 0; }
id -u "$fleet" > /dev/null 2>&1 || sudo -n useradd -m -s /bin/bash "$fleet" ||
    root "useradd -m -s /bin/bash $fleet"
[ "$(loginctl show-user "$fleet" -p Linger --value 2> /dev/null)" = yes ] ||
    sudo -n loginctl enable-linger "$fleet" || root "loginctl enable-linger $fleet"
mkdir -p ~/ark/output ~/ark/data && chmod o+x ~ ~/GitHub ~/ark ~/ark/output
chmod 600 ~/ark/local.env && chmod 700 ~/ark/data && { [ ! -d ~/ark/private ] || chmod 700 ~/ark/private; }
