#!/bin/bash

set -euo pipefail

# This script wouldn't be required if models and resources move into a proper 'lightkube_models' package and are not
# symlinked into the source tree

if [ -d "../lightkube-models" ]; then
  echo "Found 'lightkube-models' locally."
  SOURCE_DIR=$(uv run python -c "import os.path; print(os.path.realpath('../lightkube-models'))")
else
  echo "Did not find 'lightkube-models' locally, will install them from upstream..."
  SOURCE_DIR=$(uv run python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
  uv pip install lightkube-models
fi
echo "Source dir of 'lightkube-models' is ${SOURCE_DIR}, will link that into the source tree."
rm -f lightkube/models lightkube/resources
ln -s  $SOURCE_DIR/lightkube/models lightkube
ln -s  $SOURCE_DIR/lightkube/resources lightkube
