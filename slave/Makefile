# -*- makefile -*-

export PATH=$(shell pwd)/../sandbox/bin:/bin:/usr/bin

start:
	buildslave start .

stop:
	buildslave stop .

log:
	if [ -e twistd.log ]; \
	then tail -F twistd.log; \
	else echo "Nothing to tail."; \
	fi
