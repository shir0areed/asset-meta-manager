#!/usr/bin/env python
import sys
import subprocess
import pathlib
import venv
import os


APP_MODULE = 'src.asset_meta_manager.main'


if __name__ == '__main__':
    app_dir = pathlib.Path(__file__).resolve().parent
    venv_dir = app_dir / 'venv'
    os.chdir(app_dir)

    # python -m venv .venv
    builder = venv.EnvBuilder(with_pip=True)
    builder.create(str(venv_dir))
    context = builder.ensure_directories(str(venv_dir))
    venv_python = context.env_exe

    # pip install -r requirements.txt
    subprocess.check_call(
        [venv_python, '-m', 'pip', 'install', '-e', str(app_dir)],
    )

    # python main.py <args>
    subprocess.check_call(
        [venv_python, '-m', APP_MODULE] + sys.argv[1:]
    )