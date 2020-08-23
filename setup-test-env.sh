#!/bin/bash
SITE_PKG=$(python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')

pip install lightkube-models
rm -f lightkube/base lightkube/models lightkube/resources
ln -s  $SITE_PKG/lightkube/base lightkube
ln -s  $SITE_PKG/lightkube/models lightkube
ln -s  $SITE_PKG/lightkube/resources lightkube
