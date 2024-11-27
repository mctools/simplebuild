import pathlib
import os
import stat

def chmod_x( path ):
    st = os.stat(path)
    os.chmod(path, st.st_mode | stat.S_IEXEC)

root = pathlib.Path(__file__).resolve().absolute().parent / 'autogen_dynpkgs'
mypkg = root / 'MyPkg'
if not mypkg.joinpath('pkg.info').exists():
    mypkg.mkdir(parents=True)
    mypkg.joinpath('pkg.info').write_text('package()\n')
    (mypkg/'scripts').mkdir()
    (mypkg/'scripts/testbla').write_text('#!/usr/bin/env python3\nprint("hello")\n')
    chmod_x(mypkg/'scripts/testbla')
