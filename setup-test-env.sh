#!/bin/bash

# This script wouldn't be required if models and resources move into a proper 'lightkube_models' package and are not
# symlinked into the source tree

if [ -d "../lightkube-models" ]; then
  SOURCE_DIR=$(python -c "import os.path; print(os.path.realpath('../lightkube-models'))")
else
  SOURCE_DIR=$(python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
  uv pip install lightkube-models
fi
rm -f lightkube/models lightkube/resources
ln -s  $SOURCE_DIR/lightkube/models lightkube
ln -s  $SOURCE_DIR/lightkube/resources lightkube
