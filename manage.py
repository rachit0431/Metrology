#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import importlib
import os
import socket
import subprocess
import sys

TARGET_SITE = '/usr/local/lib/python3.10/dist-packages'
os.makedirs(TARGET_SITE, exist_ok=True)
if TARGET_SITE not in sys.path:
    sys.path.insert(0, TARGET_SITE)


def _is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def _resolve_runserver_args(argv):
    """
    If running inside the cloud preview container where port 8000 is reserved
    by control-plane-api, automatically fall back to port 3000 (or 8001) so
    'python manage.py runserver 0.0.0.0:8000' succeeds without port conflict.
    """
    if len(argv) >= 2 and argv[1] == 'runserver' and os.path.exists('/app/control-plane-api/control-plane-api'):
        has_addr = any(not arg.startswith('-') for arg in argv[2:])
        if not has_addr and _is_port_in_use(8000):
            target_port = 3000 if not _is_port_in_use(3000) else 8001
            argv.append(f'0.0.0.0:{target_port}')
        else:
            for i in range(2, len(argv)):
                arg = argv[i]
                if arg in ('8000', '0.0.0.0:8000', '127.0.0.1:8000', 'localhost:8000') and _is_port_in_use(8000):
                    target_port = 3000 if not _is_port_in_use(3000) else 8001
                    host_part = arg.split(':')[0] if ':' in arg else '0.0.0.0'
                    argv[i] = f'{host_part}:{target_port}'
    return argv


def _ensure_dependencies():
    """Automatically unpack vendor archive or bootstrap pip if container cold-started."""
    os.makedirs(TARGET_SITE, exist_ok=True)
    if TARGET_SITE not in sys.path:
        sys.path.insert(0, TARGET_SITE)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    vendor_tar = os.path.join(base_dir, '.python_vendor.tar.gz')
    req_file = os.path.join(base_dir, 'requirements.txt')
    if os.path.exists(vendor_tar):
        subprocess.run(
            ['tar', '-xzf', vendor_tar, '-C', TARGET_SITE],
            check=False,
        )
    else:
        subprocess.run(
            ['bash', '-c', (
                'if ! python3 -m pip --version >/dev/null 2>&1; then '
                'curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py && '
                'python3 /tmp/get-pip.py --no-setuptools --no-wheel --root-user-action=ignore; fi && '
                f'python3 -m pip install --root-user-action=ignore -r "{req_file}"'
            )],
            check=False,
        )
    importlib.invalidate_caches()


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    if not os.path.exists(os.path.join(TARGET_SITE, 'django')):
        _ensure_dependencies()
    try:
        import django
        import rest_framework
        import whitenoise
        import dotenv
        import segno
        from django.core.management import execute_from_command_line
    except ImportError:
        _ensure_dependencies()
        from django.core.management import execute_from_command_line
    execute_from_command_line(_resolve_runserver_args(sys.argv))


if __name__ == '__main__':
    main()
