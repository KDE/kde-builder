#!/bin/bash

docker build -t deps-runner .

docker run -it --rm -v $(pwd):/work deps-runner ./gen-deps.sh