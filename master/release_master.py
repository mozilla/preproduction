from buildbot.process.factory import BuildFactory
from buildbot.steps.shell import ShellCommand, SetProperty
from buildbot.process.properties import WithProperties

from util.hg import make_hg_url

class PPReleaseFactory(BuildFactory):

    def __init__(self, rmConfig, **kwargs):
        BuildFactory.__init__(self, **kwargs)

        self.addStep(SetProperty(
            name='set_topdir',
            command=['pwd'],
            property='topdir',
            workdir='.',
        ))
        self.addStep(ShellCommand(
            command=['rm', '-rvf', 'tools', 'buildbot-configs'],
            workdir='.',
        ))
        self.addStep(ShellCommand(
            command=['hg', 'clone',
                     make_hg_url(rmConfig['HG_HOST'], 'build/tools'),
                     'tools'],
            workdir='.',
            haltOnFailure=True,
        ))
        self.addStep(ShellCommand(
            command=[rmConfig['PYTHON'], 'scripts/preproduction/repo_setup.py', '-c',
                     'scripts/preproduction/repo_setup_config.py'],
            workdir='tools',
            haltOnFailure=True,
        ))
        self.addStep(SetProperty(
            property='previousSetupMakefile',
            command='ls %s/Makefile 2>/dev/null || exit 0' %
                rmConfig['releaseMasterDir'],
            flunkOnFailure=False,
            haltOnFailure=False,
            warnOnFailure=True,
        ))

        def previousSetupExists(step):
            return \
                step.build.getProperties().has_key('previousSetupMakefile') \
                and len(step.build.getProperty('previousSetupMakefile')) > 0

        self.addStep(ShellCommand(
            command=[rmConfig['PYTHON'],
                     'tools/buildfarm/maintenance/buildbot-wrangler.py',
                     'stop', '%s/master' % rmConfig['releaseMasterDir']],
            workdir=rmConfig['releaseMasterDir'],
            flunkOnFailure=False,
            doStepIf=previousSetupExists,
        ))
        self.addStep(ShellCommand(
            command=['rm', '-rvf', rmConfig['releaseMasterDir']],
            workdir='.',
            haltOnFailure=True,
        ))
        self.addStep(ShellCommand(
            command=['rm', '-rvf', 'buildbot-configs'],
            workdir='.',
            haltOnFailure=True,
        ))
        self.addStep(ShellCommand(
            command=['hg', 'clone',
                     make_hg_url(rmConfig['HG_HOST'],
                                 '%s/buildbot-configs' % rmConfig['HG_DIR']),
                     'buildbot-configs'],
            workdir='.',
            haltOnFailure=True,
        ))
        self.addStep(ShellCommand(
            command=['make', '-f', 'Makefile.setup',
                     'PYTHON=%s' % rmConfig['PYTHON'],
                     'VIRTUALENV=%s' % rmConfig['VIRTUALENV'],
                     'HG_DIR=%s' % rmConfig['HG_DIR'],
                     'MASTER_NAME=%s' % rmConfig['MASTER_NAME'],
                     'BASEDIR=%s' % rmConfig['releaseMasterDir'],
                     'BUILDBOTCUSTOM_BRANCH=%s' %
                        rmConfig['BUILDBOTCUSTOM_BRANCH'],
                     'BUILDBOTCONFIGS_BRANCH=%s' %
                        rmConfig['BUILDBOTCONFIGS_BRANCH'],
                     'virtualenv', 'deps', 'install-buildbot', 'master',
                     'master-makefile'],
            workdir='buildbot-configs',
            env={'PIP_DOWNLOAD_CACHE': WithProperties('%(topdir)s/cache'),
                 'CC': None,
                 'CXX': None
                },
            haltOnFailure=True,
        ))
        self.addStep(ShellCommand(
            command=['make', 'checkconfig'],
            workdir=rmConfig['releaseMasterDir'],
            haltOnFailure=True,
        ))
        self.addStep(ShellCommand(
            command=['touch', 'twistd.log'],
            workdir='%s/master' % rmConfig['releaseMasterDir'],
        ))
        self.addStep(ShellCommand(
            command=[
                'bash', '-c',
                'if [ -e ~/conf/passwords.py ]; then cp -fv ~/conf/passwords.py ./; fi'
            ],
            workdir='%s/master' % rmConfig['releaseMasterDir'],
        ))
        self.addStep(ShellCommand(
            command=[rmConfig['PYTHON'],
                     'tools/buildfarm/maintenance/buildbot-wrangler.py',
                     'start', '%s/master' % rmConfig['releaseMasterDir']],
            workdir=rmConfig['releaseMasterDir'],
        ))
        for release_config in rmConfig['releaseConfigs']:
            self.addStep(SetProperty(
                property='release_tag',
                command=[rmConfig['PYTHON'], '-c',
                         'execfile("%s"); \
                         print releaseConfig["baseTag"] + "_RELEASE"' %
                                                        release_config],
                workdir='%s/buildbot-configs' % rmConfig['releaseMasterDir'],
            ))
            self.addStep(SetProperty(
                property='release_branch',
                command=[rmConfig['PYTHON'], '-c',
                         'execfile("%s"); \
                         print releaseConfig["sourceRepositories"]["mozilla"]["path"]' %
                                                            release_config],
                workdir='%s/buildbot-configs' % rmConfig['releaseMasterDir'],
            ))

            self.addStep(ShellCommand(
                command=['buildbot', 'sendchange',
                         '--username', 'preproduction',
                         '--master', rmConfig['releaseMasterHostPort'],
                         '--branch', WithProperties('%(release_branch)s'),
                         '-p', 'products:firefox',
                         '-p',  WithProperties(
                             'script_repo_revision:%(release_tag)s'),
                         'release_build'],
                workdir='.',
            ))
