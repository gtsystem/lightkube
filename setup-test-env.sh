#!/bin/bash

if [ -d "../lightkube-models" ]; then
  SOURCE_DIR=$(python -c "import os.path; print(os.path.realpath('../lightkube-models'))")
else
  SOURCE_DIR=$(python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
  pip install lightkube-models
fi
rm -f lightkube/models lightkube/resources
ln -s  $SOURCE_DIR/lightkube/models lightkube
ln -s  $SOURCE_DIR/lightkube/resources lightkube
