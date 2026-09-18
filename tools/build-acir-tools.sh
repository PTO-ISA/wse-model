#!/usr/bin/env bash
# Build the native ACIR tools from a pyCircuit checkout.
#
# The `agentic_circuit` frontend lowers any model that uses `@ac.rule` or
# `@ac.module` through three native binaries. They are not shipped as wheels, so
# a developer (and the opt-in `acir` CI job) must build them once:
#
#   acir-opt              ACIR passes, including the rule-lowering pipeline
#   acir-queue-plan       QueueGraph planning
#   acir-queue-cxxgen     gfsim / PYC C++ generation
#   acir-cxxgen           ACIR C++ generation
#
# Usage:
#   tools/build-acir-tools.sh [PYCIRCUIT_ROOT]
#
# Environment:
#   PYCIRCUIT_ROOT   pyCircuit checkout (default: ../pyCircuit)
#   LLVM_DIR         LLVM CMake package dir (default: auto-detected)
#   MLIR_DIR         MLIR CMake package dir (default: auto-detected)
#   BUILD_JOBS       parallelism (default: the host CPU count)
#
# On success it prints the exports needed to run the ACIR tests.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYCIRCUIT_ROOT="${1:-${PYCIRCUIT_ROOT:-${REPO_ROOT}/../pyCircuit}}"
BUILD_JOBS="${BUILD_JOBS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)}"

if [[ ! -d "${PYCIRCUIT_ROOT}/compiler/acir" ]]; then
    echo "error: ${PYCIRCUIT_ROOT} does not look like a pyCircuit checkout" >&2
    echo "       clone it first: git clone https://github.com/PTO-ISA/pyCircuit.git ${PYCIRCUIT_ROOT}" >&2
    exit 1
fi

PYCIRCUIT_ROOT="$(cd "${PYCIRCUIT_ROOT}" && pwd)"

# Locate LLVM/MLIR 22.1.8 unless the caller already pointed at it.
if [[ -z "${LLVM_DIR:-}" || -z "${MLIR_DIR:-}" ]]; then
    for prefix in \
        /opt/homebrew/opt/llvm@22 \
        /opt/homebrew/opt/llvm \
        /usr/lib/llvm-22 \
        /usr/local/opt/llvm@22; do
        if [[ -f "${prefix}/lib/cmake/mlir/MLIRConfig.cmake" ]]; then
            export LLVM_DIR="${prefix}/lib/cmake/llvm"
            export MLIR_DIR="${prefix}/lib/cmake/mlir"
            break
        fi
    done
fi

if [[ -z "${LLVM_DIR:-}" || -z "${MLIR_DIR:-}" ]]; then
    echo "error: LLVM/MLIR 22.1.8 not found." >&2
    echo "       Set LLVM_DIR and MLIR_DIR, or install LLVM 22 (brew install llvm@22)." >&2
    exit 1
fi

echo "==> pyCircuit      : ${PYCIRCUIT_ROOT}"
echo "==> LLVM_DIR       : ${LLVM_DIR}"
echo "==> MLIR_DIR       : ${MLIR_DIR}"
echo "==> build dir      : ${PYCIRCUIT_ROOT}/.pycircuit_out/toolchain/build"

cd "${PYCIRCUIT_ROOT}"
cmake --preset release -DPYC_BUILD_AGENTIC_CIRCUIT=ON
cmake --build .pycircuit_out/toolchain/build \
    --target acir-opt acir-queue-plan acir-queue-cxxgen acir-cxxgen \
    -j "${BUILD_JOBS}"

BIN_DIR="${PYCIRCUIT_ROOT}/.pycircuit_out/toolchain/build/bin"
for tool in acir-opt acir-queue-plan acir-queue-cxxgen acir-cxxgen; do
    if [[ ! -x "${BIN_DIR}/${tool}" ]]; then
        echo "error: ${BIN_DIR}/${tool} was not produced" >&2
        exit 1
    fi
done

cat <<EOF

Native ACIR tools built.

Export these before running the ACIR layer tests:

  export ACIR_OPT=${BIN_DIR}/acir-opt
  export ACIR_QUEUE_CXXGEN=${BIN_DIR}/acir-queue-cxxgen
  export ACIR_QUEUE_PLAN=${BIN_DIR}/acir-queue-plan
  export ACIR_CXXGEN=${BIN_DIR}/acir-cxxgen

Then:

  make acir
EOF
