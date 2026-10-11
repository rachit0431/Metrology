#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# Remove any stale/partial local package directory
if [ -d ".python_packages" ]; then
    rm -rf .python_packages
fi

# Ensure target dist-packages directory exists and is on PYTHONPATH
TARGET_SITE="/usr/local/lib/python3.10/dist-packages"
mkdir -p "$TARGET_SITE"
export PYTHONPATH="${TARGET_SITE}:${PYTHONPATH:-}"

# Ensure python symlink is available
ln -sf /usr/bin/python3 /usr/local/bin/python 2>/dev/null || true

# Fast self-heal Python dependencies on container cold start (<0.3s via local vendor archive)
if ! python3 -c "import django, rest_framework, whitenoise, dotenv, segno" >/dev/null 2>&1; then
    if [ -f ".python_vendor.tar.gz" ]; then
        tar -xzf .python_vendor.tar.gz -C "$TARGET_SITE"
    else
        if ! python3 -m pip --version >/dev/null 2>&1; then
            curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
            python3 /tmp/get-pip.py --no-setuptools --no-wheel --root-user-action=ignore
        fi
        python3 -m pip install --root-user-action=ignore -r requirements.txt
    fi
fi

# Run Django development server on port 3000 for Preview immediately
exec python3 manage.py runserver 0.0.0.0:3000 --noreload
