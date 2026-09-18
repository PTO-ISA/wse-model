#!/usr/bin/env bash
# Bootstrap a development environment for wse-model.
#
# The `agentic-circuit` frontend is distributed from the PTO-ISA/pyCircuit
# checkout and is not published on PyPI, so it cannot be pulled in by a plain
# `pip install -e .`. This script installs the model package, the development
# extras, and both pyCircuit Python distributions from a local checkout.
#
# Usage:
#   tools/bootstrap-dev.sh [--pycircuit-root PATH] [--venv PATH] [--no-venv]
#
# Environment:
#   PYCIRCUIT_ROOT  pyCircuit checkout (default: ../pyCircuit)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYCIRCUIT_ROOT="${PYCIRCUIT_ROOT:-${REPO_ROOT}/../pyCircuit}"
VENV_PATH="${REPO_ROOT}/.venv"
CREATE_VENV=1
PYTHON_BIN="${PYTHON:-python3}"

usage() {
    sed -n '2,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --pycircuit-root)
            PYCIRCUIT_ROOT="$2"
            shift 2
            ;;
        --venv)
            VENV_PATH="$2"
            shift 2
            ;;
        --no-venv)
            CREATE_VENV=0
            shift
            ;;
        --python)
            PYTHON_BIN="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "error: unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ ! -d "${PYCIRCUIT_ROOT}" ]]; then
    echo "error: pyCircuit checkout not found at ${PYCIRCUIT_ROOT}" >&2
    echo "       clone it first: git clone https://github.com/PTO-ISA/pyCircuit.git ${PYCIRCUIT_ROOT}" >&2
    exit 1
fi

for component in python/semantic-core python/agentic-circuit; do
    if [[ ! -d "${PYCIRCUIT_ROOT}/${component}" ]]; then
        echo "error: ${PYCIRCUIT_ROOT}/${component} is missing" >&2
        exit 1
    fi
done

if [[ "${CREATE_VENV}" -eq 1 ]]; then
    if [[ ! -d "${VENV_PATH}" ]]; then
        echo "==> creating virtual environment at ${VENV_PATH}"
        "${PYTHON_BIN}" -m venv "${VENV_PATH}"
    fi
    # shellcheck disable=SC1091
    source "${VENV_PATH}/bin/activate"
    PYTHON_BIN="python"
fi

echo "==> upgrading pip"
"${PYTHON_BIN}" -m pip install --quiet --upgrade pip

echo "==> installing pycircuit-semantic-core from ${PYCIRCUIT_ROOT}"
"${PYTHON_BIN}" -m pip install --quiet -e "${PYCIRCUIT_ROOT}/python/semantic-core"

echo "==> installing agentic-circuit from ${PYCIRCUIT_ROOT}"
"${PYTHON_BIN}" -m pip install --quiet -e "${PYCIRCUIT_ROOT}/python/agentic-circuit"

echo "==> installing wse-model with development extras"
"${PYTHON_BIN}" -m pip install --quiet -e "${REPO_ROOT}[dev]"

echo "==> verifying imports"
"${PYTHON_BIN}" - <<'PY'
import agentic_circuit
import pycircuit_semantic_core
import wse_model

print(f"agentic_circuit           {agentic_circuit.__file__}")
print(f"pycircuit_semantic_core   {pycircuit_semantic_core.__file__}")
print(f"wse_model                 {wse_model.__file__}")
PY

PYCIRCUIT_REV="$(git -C "${PYCIRCUIT_ROOT}" rev-parse HEAD 2>/dev/null || echo unknown)"
cat <<EOF

Bootstrap complete.

  pyCircuit revision : ${PYCIRCUIT_REV}

Next steps:
  make check
  wse-model topology show
EOF
