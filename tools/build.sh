#!/bin/bash

python -m tools.compile_models  openapi/swagger.json lightkube/
python -m tools.compile  openapi/swagger.json lightkube/
