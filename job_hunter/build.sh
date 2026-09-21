#!/usr/bin/env bash
# Exit on error
set -o errexit

# 1. Install Backend Dependencies
pip install -r requirements.txt

# 2. Build Frontend
cd frontend
npm install
npm run build
cd ..
