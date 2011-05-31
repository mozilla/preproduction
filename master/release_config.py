rmConfig = {}

# TODO: enable multiple version when we can use locales per version
rmConfig['releaseConfigs'] = ['mozilla/release-firefox-mozilla-beta.py']
rmConfig['releaseMasterDir'] = '/builds/buildbot/release-master'
rmConfig['releaseMasterHostPort'] = 'localhost:9020'

rmConfig['HG_HOST'] = 'hg.mozilla.org'
rmConfig['PYTHON'] = '/tools/python/bin/python'
rmConfig['VIRTUALENV'] = '/tools/python/bin/virtualenv'
rmConfig['HG_DIR'] = 'users/prepr-ffxbld'
rmConfig['MASTER_NAME'] = 'preprod-release-master'
rmConfig['BUILDBOTCUSTOM_BRANCH'] = 'default'
rmConfig['BUILDBOTCONFIGS_BRANCH'] = 'default'
