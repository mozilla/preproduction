# -*- makefile -*-

export PATH=$(shell pwd)/../sandbox/bin:/bin:/usr/bin

start:
	buildbot start .

restart:
	buildbot restart .

stop:
	buildbot stop .

reconfig:
	buildbot reconfig

check:
	buildbot checkconfig

log:
	if [ -e twistd.log ]; \
	then tail -F twistd.log; \
	else echo "Nothing to tail."; \
	fi
