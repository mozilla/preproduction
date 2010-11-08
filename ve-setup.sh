#!/bin/sh

mkdir -p sandbox
cd sandbox
rm -rf bin lib include
unset CC
unset CXX
export PIP_DOWNLOAD_CACHE=$PWD/cache
mkdir -p $PIP_DOWNLOAD_CACHE
VE_VER=1.4.9
wget -O- http://pypi.python.org/packages/source/v/virtualenv/virtualenv-${VE_VER}.tar.gz | tar -xz  virtualenv-${VE_VER}/virtualenv.py || exit 1

PYTHON=/tools/python/bin/python
PYTHON=python
$PYTHON virtualenv-${VE_VER}/virtualenv.py --distribute --no-site-packages . || exit 1
rm -rf virtualenv-${VE_VER}
PYTHON=$PWD/bin/python
PATH=$PWD/bin:$PATH
$PYTHON -c 'import json' 2>/dev/null ||                     $PYTHON -c 'import  simplejson' ||                     ./bin/pip install simplejson || exit 1
$PYTHON -c 'import sqlite3, sys; assert sys.version_info >= (2,6)' 2>/dev/null                     || $PYTHON -c 'import pysqlite2.dbapi2' ||                     ./bin/pip install pysqlite || exit 1;
./bin/pip install Twisted || exit 1;
./bin/pip install jinja2 || exit 1;
./bin/pip install mock || exit 1;
./bin/pip install coverage || exit 1;
./bin/pip install nose || exit 1;
./bin/pip install pylint || exit 1;
./bin/pip install sqlalchemy || exit 1;
./bin/pip install argparse || exit 1;
./bin/pip install django || exit 1;
./bin/pip install pycrypto || exit 1;
./bin/pip install pyasn1 || exit 1;
./bin/pip install mysql-python || exit 1;
./bin/pip install mercurial || exit 1;
./bin/pip install pyopenssl==0.10 || exit 1;
hg clone http://hg.mozilla.org/build/buildbot
(cd buildbot/master; $PYTHON setup.py develop install) || exit 1;
(cd buildbot/slave; $PYTHON setup.py develop install) || exit 1;
rm -rf buildbot
