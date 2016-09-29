#!/bin/bash

set -euo pipefail # "strict mode"

# Change to the parent directory of the directory that contains this script.
cd $(dirname $(dirname $(readlink -m $0)))

# Pull from git.
git pull --rebase

# Run database migrations.
python3 manage.py migrate

# Fetch vendor resources.
./fetch-vendor-resources.sh

# Extract static assets.
python3 manage.py collectstatic --noinput

# Kick the uWSGI process to reload modules.
killall -HUP uwsgi_python3
