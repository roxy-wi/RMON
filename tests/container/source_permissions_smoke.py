"""Verify built source trees are readable under each application's runtime identity."""
import os
import subprocess


PROBE = '''
import os
import sys
from pathlib import Path

def fail(error):
    raise error

count = 0
for directory, _, files in os.walk(sys.argv[1], onerror=fail):
    assert os.access(directory, os.R_OK | os.X_OK), directory
    for name in files:
        path = Path(directory) / name
        with path.open('rb') as stream:
            stream.read(1)
        count += 1
assert count > 0
print('Readable source files:', count)
'''


def main():
    for component, user, executable, directory in (
        ('WEB', '33:33', '/opt/rmon-venv/bin/python', '/var/www/rmon'),
        ('SERVER', '10001:10001', 'python', '/opt/rmon-server'),
        ('AGENT', '10001:10001', 'python', '/var/www/rmon/app/tools/rmon-agent'),
    ):
        image = os.getenv(f'RMON_TEST_{component}_IMAGE', f'rmon-{component.lower()}:test')
        result = subprocess.run(['docker', 'run', '--rm', '--user', user, '--entrypoint', executable,
                                 image, '-c', PROBE, directory], text=True, capture_output=True, timeout=60)
        if result.returncode:
            raise AssertionError(f'{component} source access failed: {result.stderr}')
        print(component + ': ' + result.stdout.strip(), flush=True)


if __name__ == '__main__':
    main()
