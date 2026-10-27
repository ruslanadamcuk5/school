#!/bin/bash
set -e
cd "$HOME/edu-math"
echo "--- unzip ---"
command -v unzip
STAMP=$(date +%F-%H%M)
tar czf "$HOME/edu-math-backup-$STAMP.tgz" --exclude=./data --exclude=./__pycache__ .
echo "BACKUP_OK $HOME/edu-math-backup-$STAMP.tgz"
unzip -o -q "$HOME/edu-math-deploy.zip" -d "$HOME/edu-math"
echo "UNZIP_OK"
source "$HOME/.virtualenvs/edu-math/bin/activate"
pip install -q -r requirements.txt
echo "PIP_OK"
python -c 'import app; print("IMPORT_OK")'
