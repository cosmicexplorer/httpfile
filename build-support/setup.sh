#!/bin/bash

set -euxo pipefail

mkdir -pv .git/hooks
ln -sfv "$(pwd)"/build-support/pre-commit .git/hooks/pre-commit

echo >&2 'Pre-commit hook linked!'
