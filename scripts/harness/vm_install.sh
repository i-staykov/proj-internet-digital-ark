#!/usr/bin/env bash
# The bank host, set up from the laptop: `just vm install` pipes this to the VM after its
# local.env. As the login, `sudo -n` only for packages and linger: tools under ~/.local/bin,
# both clones, the walk lane and the tick as a user timer that fires once the store is there.
# Idempotent; the gh token comes by `just vm token gh` (docs/ops/runbook.md).
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
# The tick reboots for unattended-upgrades (scheduled_sync.sh) through `sudo -n /usr/sbin/reboot`;
# root's step for each half that does not hold. sudo skips a sudoers.d name with a dot, so the
# line is checked before it counts.
sudo -n -l /usr/sbin/reboot > /dev/null 2>&1 || cat << STEP
reboot: sudo asks a password. As root, once:
    echo '$(id -un) ALL=(root) NOPASSWD: /usr/sbin/reboot ""' > /etc/sudoers.d/ark.new && chmod 440 /etc/sudoers.d/ark.new && visudo -cqf /etc/sudoers.d/ark.new && mv /etc/sudoers.d/ark.new /etc/sudoers.d/ark-reboot
STEP
apt=$(apt-config dump 2> /dev/null || true)
grep -q '^APT::Periodic::Unattended-Upgrade "[1-9]' <<< "$apt" &&
    ! grep -qiE '^Unattended-Upgrade::Automatic-Reboot "(true|yes|on|1)"' <<< "$apt" || cat << 'STEP'
unattended-upgrades: off, or rebooting by itself. As root, once, answering yes:
    apt-get install -y -qq unattended-upgrades && dpkg-reconfigure -plow unattended-upgrades && echo 'Unattended-Upgrade::Automatic-Reboot "false";' > /etc/apt/apt.conf.d/52ark
STEP
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
# His calculator over his largest year file outgrows the RAM (docs/lore/laws.md, Harness), so
# the tick's intake (drive_intake.sh) waits on swap. Root's one step, printed until it holds.
[ "$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo)" -ge 16000000 ] || cat << 'STEP'
swap: under 16 GiB. As root, once:
    fallocate -l 16G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile && echo '/swapfile none swap sw 0 0' >> /etc/fstab
STEP

[ -d ~/ark/.git ] || git clone -q -b live https://github.com/i-staykov/proj-internet-digital-ark ~/ark
git -C ~/ark pull -q --ff-only
# Every commit the clone makes goes public: it names the tick, never a login or a machine.
git -C ~/ark config user.name ark-tick && git -C ~/ark config user.email ark-tick@invalid
[ -f ~/ark-local.env ] && mv ~/ark-local.env ~/ark/local.env
if gh auth status > /dev/null 2>&1; then
    gh auth setup-git
    [ -d ~/GitHub/ark-fleet/.git ] || gh repo clone i-staykov/ark-fleet ~/GitHub/ark-fleet -- -q
else
    echo "gh: not logged in; the tick drains nothing and pushes nothing until 'just vm token gh'"
fi
(cd ~/ark && uv sync -q && mkdir -p data/logs && just hooks > /dev/null && just walk install)

cp ~/ark/scripts/harness/ark-sync.service ~/ark/scripts/harness/ark-sync.timer \
    ~/ark/scripts/harness/ark-agent.service ~/ark/scripts/harness/ark-agent.timer ~/.config/systemd/user/
systemctl --user daemon-reload
[ "$(loginctl show-user "$(id -un)" -p Linger --value 2> /dev/null)" = yes ] ||
    loginctl enable-linger 2> /dev/null || sudo -n loginctl enable-linger "$(id -un)" ||
    root "loginctl enable-linger $(id -un)"
systemctl --user enable --now ark-sync.timer
# The agent runs once its token file is there: `just vm token claude` writes ~/.config/ark/agent.env,
# one line, CLAUDE_CODE_OAUTH_TOKEN=<the token>, mode 600; the unit's condition is that file.
[ -f ~/.config/ark/agent.env ] || echo "no agent token: 'just vm token claude' from the laptop, the timer waits on it"
# The agent's profile: its deny list and the rails hook, the login's own Claude settings.
mkdir -p ~/.claude && cp ~/ark/agent/settings.json ~/.claude/settings.json
mkdir -p ~/ark-agent
# The alerts' label, once; the agent's parked items and the triage file under it. The hold's
# label, which the tick reads (scripts/harness/hold.sh).
gh label create vm-alert -R i-staykov/ark-fleet --color D93F0B --description "the VM's agent asks for a reader" > /dev/null 2>&1 || true
gh label create hold -R i-staykov/ark-fleet --color 000000 --description "just hold, through the tick" > /dev/null 2>&1 || true
systemctl --user enable --now ark-agent.timer
systemctl --user enable --now ark-agent.timer
systemctl --user list-timers ark-sync.timer ark-agent.timer --no-pager --no-legend
chmod 600 ~/ark/local.env
