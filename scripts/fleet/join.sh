#!/usr/bin/env bash
# Join a cloud VM to the long runner lane (docs/ops/runbook.md, Runner lanes): GitHub's
# actions-runner for this machine's architecture, pinned by checksum, registered to the public
# repository with the token passed as the only argument and labelled ark-lane, as a systemd
# service that is back after a reboot; and the walker's needs, git, curl, tar, jq and a Python
# 3.12 by uv (the walker is stdlib only; the system python3 stays). Idempotent: each step is
# skipped where its result is present. Prints nothing secret: never -x, the argument never
# echoed, the runner named by the machine id, not the hostname, since names print in public logs.
#
# On the laptop (the token is an admin's, one hour of life):
#     gh api -X POST repos/i-staykov/proj-internet-digital-ark/actions/runners/registration-token -q .token
#     ssh VM bash -s -- TOKEN < scripts/fleet/join.sh
set -eu

REPO=https://github.com/i-staykov/proj-internet-digital-ark
RUNNER=2.338.2
UV=0.13.7
PY=3.12
declare -A SHA=(
  [arm64]=670adb2f268fe21dcbb58b3db0e0aa9d5b3bddfe2c651481336e561ff86de945
  [x64]=baebf204307bac6193480852732f0aba2ae97b6c5597c244f4d5558390147c40
)

[ $# -eq 1 ] || { echo "usage: join.sh TOKEN" >&2; exit 2; }
case "$(uname -m)" in
  aarch64) ARCH=arm64 ;;
  x86_64) ARCH=x64 ;;
  *) echo "unsupported machine: $(uname -m)" >&2; exit 1 ;;
esac
export PATH="$HOME/.local/bin:$PATH"

need=""
for p in git curl tar jq; do command -v "$p" >/dev/null || need="$need $p"; done
if [ -n "$need" ]; then
  sudo apt-get update -q >/dev/null || true
  # shellcheck disable=SC2086  # the missing packages, split on purpose
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q $need >/dev/null
fi

if [ ! -x "$HOME/.local/bin/uv" ]; then
  curl -LsSf "https://astral.sh/uv/$UV/install.sh" | env UV_NO_MODIFY_PATH=1 sh >/dev/null
fi
uv python install "$PY" --default >/dev/null 2>&1

mkdir -p "$HOME/actions-runner"
cd "$HOME/actions-runner"
if [ "$(cat .runner_version 2>/dev/null)" != "$RUNNER" ]; then
  [ -f .service ] && sudo ./svc.sh stop >/dev/null
  tarball="actions-runner-linux-$ARCH-$RUNNER.tar.gz"
  curl -fsSLo "$tarball" "https://github.com/actions/runner/releases/download/v$RUNNER/$tarball"
  echo "${SHA[$ARCH]}  $tarball" | sha256sum -c - >/dev/null
  tar xzf "$tarball" && rm "$tarball"
  sudo ./bin/installdependencies.sh >/dev/null
  echo "$RUNNER" > .runner_version
fi
if [ ! -f .runner ]; then
  ./config.sh --unattended --url "$REPO" --token "$1" --labels ark-lane --replace \
    --name "ark-lane-$(head -c 8 /etc/machine-id)" >/dev/null
fi
echo "$PATH" > .path  # the job's PATH: uv's python3 first
if ! sudo ./svc.sh status 2>/dev/null | grep -q "active (running)"; then
  [ -f .service ] || sudo ./svc.sh install >/dev/null
  sudo ./svc.sh start >/dev/null
fi
state=$(sudo ./svc.sh status | grep -o "active ([a-z]*)" | head -1)
echo "arch $ARCH, runner $RUNNER, $(python3 --version), service ${state:-unknown}"
