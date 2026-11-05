#!/usr/bin/env bash
# The bank host, set up from the laptop: `just vm install` pipes this to the VM after its
# local.env. As the login, `sudo -n` only for packages, the fleet user and linger: tools under
# ~/.local/bin, both clones, the walk lane, the tick as a user timer that fires once the store
# is there, and ARK_FLEET_USER. Idempotent; `gh auth login` is the owner's (docs/ops/runbook.md).
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
mkdir -p ~/.local/bin ~/GitHub ~/.config/systemd/user
root() { echo "REFUSED: sudo asks a password; as root first: $1" >&2; exit 1; }

command -v uv > /dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh -s -- -q
command -v just > /dev/null ||
    curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/.local/bin
# The agent's Claude CLI, its own binary under ~/.local/bin; no Node.
command -v claude > /dev/null || curl -fsSL https://claude.ai/install.sh | bash > /dev/null
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
    rclone authorize "drive" '{"scope":"drive"}'
then here, with the JSON it prints
    rclone config create gdrive drive scope=drive config_is_local=false config_token='<json>'
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
(cd ~/ark && uv sync -q && mkdir -p data/logs && just hooks > /dev/null && just walk install)

cp ~/ark/scripts/harness/ark-sync.service ~/ark/scripts/harness/ark-sync.timer \
    ~/ark/scripts/harness/ark-agent.service ~/ark/scripts/harness/ark-agent.timer ~/.config/systemd/user/
systemctl --user daemon-reload
[ "$(loginctl show-user "$(id -un)" -p Linger --value 2> /dev/null)" = yes ] ||
    loginctl enable-linger 2> /dev/null || sudo -n loginctl enable-linger "$(id -un)" ||
    root "loginctl enable-linger $(id -un)"
systemctl --user enable --now ark-sync.timer
# The agent runs once its token file is there: the owner writes ~/.config/ark/agent.env, one line,
# CLAUDE_CODE_OAUTH_TOKEN=<the token>, mode 600; the unit's condition is that file.
[ -f ~/.config/ark/agent.env ] || echo "no agent token: write ~/.config/ark/agent.env (mode 600), the timer waits on it"
mkdir -p ~/ark-agent
# The alerts' label, once; the agent's parked items and the triage file under it.
gh label create vm-alert -R i-staykov/ark-fleet --color D93F0B --description "the VM's agent asks for a reader" > /dev/null 2>&1 || true
systemctl --user enable --now ark-agent.timer
systemctl --user list-timers ark-sync.timer ark-agent.timer --no-pager --no-legend

# The fleet user reads output/fleet_snapshot and output/journal_acks.tsv by path and nothing
# else of this clone, and new files follow umask 077; `just vm install` then runs ark-fleet's
# installer as that user, the runner token on its stdin.
fleet=$(sed -n 's/^ARK_FLEET_USER=//p' ~/ark/local.env | tr -d "\"'")
[ -n "$fleet" ] || { echo "no ARK_FLEET_USER in local.env, so no fleet here"; exit 0; }
id -u "$fleet" > /dev/null 2>&1 || sudo -n useradd -m -s /bin/bash "$fleet" ||
    root "useradd -m -s /bin/bash $fleet"
[ "$(loginctl show-user "$fleet" -p Linger --value 2> /dev/null)" = yes ] ||
    sudo -n loginctl enable-linger "$fleet" || root "loginctl enable-linger $fleet"
mkdir -p ~/ark/output ~/ark/data && chmod o+x ~ ~/GitHub ~/ark ~/ark/output && chmod 600 ~/ark/local.env
find ~/ark -mindepth 1 -maxdepth 1 ! -name output -exec chmod o-rwx {} +
find ~/ark/output -mindepth 1 -maxdepth 1 ! -name fleet_snapshot ! -name journal_acks.tsv -exec chmod o-rwx {} +
grep -qx 'umask 077' ~/.profile 2> /dev/null || echo 'umask 077' >> ~/.profile
