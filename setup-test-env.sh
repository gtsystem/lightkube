#!/bin/bash

set -euo pipefail

# This script wouldn't be required if models and resources move into a proper 'lightkube_models' package and are not
# symlinked into the source tree

if [ -d "../lightkube-models" ]; then
  echo "Found 'lightkube-models' locally. Will use that as source root."
  SOURCE_DIR=$(realpath "../lightkube-models")
else
  echo "Did not find 'lightkube-models' locally. Will use the venv's site packages folder as source root."
  SOURCE_DIR=$(uv run --no-project python -c 'import site; print(site.getsitepackages()[0])')
  if ! uv pip show lightkube-models > /dev/null; then
    echo "Package 'lightkube-models' isn't installed, will install upstream version."
    uv pip install lightkube-models
  else
    echo "Package 'lightkube-models' is installed."
  fi
fi
echo "Source dir of 'lightkube-models' is ${SOURCE_DIR}, will link that into the source tree."
rm -f lightkube/models lightkube/resources
ln -s  $SOURCE_DIR/lightkube/models lightkube
ln -s  $SOURCE_DIR/lightkube/resources lightkube
