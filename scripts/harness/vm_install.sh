#!/usr/bin/env bash
# The bank host, set up from the laptop: `just vm install` pipes this to the VM after its
# local.env. As the login, root only for the package line: uv, just and gh under ~/.local/bin,
# the ark clone on `live`, the fleet clone, and the tick as a systemd user timer that outlives
# a logout. Idempotent. `gh auth login` there is the owner's, once (docs/ops/runbook.md).
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
mkdir -p ~/.local/bin ~/GitHub ~/.config/systemd/user

command -v uv > /dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh -s -- -q
command -v just > /dev/null ||
    curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/.local/bin
if ! command -v gh > /dev/null; then
    v=$(curl -sI https://github.com/cli/cli/releases/latest | sed -n 's#^location:.*/v\([0-9.]*\).*#\1#ip')
    name="gh_${v}_linux_$(dpkg --print-architecture)"
    curl -sL "https://github.com/cli/cli/releases/download/v$v/$name.tar.gz" |
        tar -xz -C ~/.local/bin --strip-components=2 "$name/bin/gh"
fi
dpkg -s p7zip-full pigz > /dev/null 2>&1 || sudo apt-get install -y -qq p7zip-full pigz

[ -d ~/ark/.git ] || git clone -q -b live https://github.com/i-staykov/proj-internet-digital-ark ~/ark
git -C ~/ark pull -q --ff-only
[ -f ~/ark-local.env ] && mv ~/ark-local.env ~/ark/local.env
if gh auth status > /dev/null 2>&1; then
    gh auth setup-git
    [ -d ~/GitHub/ark-fleet/.git ] || gh repo clone i-staykov/ark-fleet ~/GitHub/ark-fleet -- -q
else
    echo "gh: not logged in; the tick drains nothing and pushes nothing until 'gh auth login'"
fi
(cd ~/ark && uv sync -q && mkdir -p data/logs)

cp ~/ark/scripts/harness/ark-sync.service ~/ark/scripts/harness/ark-sync.timer ~/.config/systemd/user/
systemctl --user daemon-reload
loginctl enable-linger 2> /dev/null || sudo loginctl enable-linger "$(id -un)"
systemctl --user enable --now ark-sync.timer
systemctl --user list-timers ark-sync.timer --no-pager --no-legend
