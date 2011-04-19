#!/bin/sh
# Example usage $0 /full/path/to/base/dir

BASEDIR=$1
VIRTUALENV=$(ls /tools/python/bin/virtualenv 2>/dev/null || which virtualenv)
PYTHON=$(ls /tools/python/bin/python 2>/dev/null || which python)
HG=$(ls /tools/python/bin/hg 2>/dev/null || which hg)

unset CC
unset CXX
export PIP_DOWNLOAD_CACHE=$BASEDIR/cache
mkdir -p $PIP_DOWNLOAD_CACHE

rm -rf $BASEDIR/buildbot
rm -rf $BASEDIR/buildbotcustom
rm -rf $BASEDIR/tools
rm -rf $BASEDIR/buildbot-configs
make \
    BASEDIR=$BASEDIR \
    VIRTUALENV=$VIRTUALENV \
    PYTHON=$PYTHON \
    HG=$HG \
    MASTER_NAME=fake \
    BUILDBOT_BRANCH=production-0.8 \
    BUILDBOTCUSTOM_BRANCH=default \
    BUILDBOTCONFIGS_BRANCH=default \
    USER=$USER \
    PIP_FLAGS="-r preproduction-pip.txt" \
    INSTALL_BUILDBOT_SLAVE=1 \
    -f Makefile.setup virtualenv deps install-buildbot
