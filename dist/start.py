#!/usr/bin/env python
import sys
import subprocess
import pathlib
import venv
import socket


APP_MODULE = 'asset_meta_manager'


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


if __name__ == '__main__':
    script_dir = pathlib.Path(__file__).resolve().parent
    venv_dir = script_dir / 'venv'
    wheel_dir = script_dir

    port = find_free_port()
    server_proc = subprocess.Popen([
        sys.executable,
        "-m", "http.server",
        str(port),
        "--directory", str(wheel_dir)
    ])

    index_url = f"http://localhost:{port}/"
   
    # python -m venv <venv_dir>
    builder = venv.EnvBuilder(with_pip=True)
    builder.create(str(venv_dir))
    context = builder.ensure_directories(str(venv_dir))
    venv_python = context.env_exe

    # pip install <APP_PACKAGE> --find-links <index_url>
    subprocess.check_call(
        [
            venv_python,
            '-m',
            'pip',
            'install',
            APP_MODULE.replace('_', '-'),
            '--find-links',
            index_url
        ]
    )

    server_proc.terminate()

    # python -m <APP_MODULE> <args>
    subprocess.check_call(
        [venv_python, '-m', APP_MODULE] + sys.argv[1:]
    )
