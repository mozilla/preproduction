import re
import textwrap
from buildbot.process.factory import BuildFactory
from buildbot.steps.shell import ShellCommand, SetProperty
from buildbot.process.properties import WithProperties
from buildbot.steps.python import PyLint
from buildbot.steps.master import MasterShellCommand
try:
    import cStringIO
    StringIO = cStringIO.StringIO
except ImportError:
    from StringIO import StringIO


class PyLintExtended(PyLint):

    def __init__(self, project='', **kwargs):
        self.parent_class = PyLint
        self.parent_class.__init__(self, **kwargs)
        self.project = project
        self.addFactoryArguments(project=project)

    def createSummary(self, log):
        self.parent_class.createSummary(self, log)
        key = 'pylint-%s' % self.project
        if not self.build.getProperties().has_key(key):
            self.setProperty(key, {})
        props = self.getProperty(key)
        for msg, fullmsg in self.MESSAGES.items():
            props[fullmsg] = self.getProperty('pylint-%s' % fullmsg)
        props['total'] = self.getProperty('pylint-total')

        score_re = re.compile(r'Your code has been rated at ([\d.]+)/([\d.]+) \(previous run: ([\d.]+)/([\d.]+)\)')
        for line in StringIO(log.getText()).readlines():
            m = score_re.match(line)
            if m:
                score, prevScore = m.groups()[0], m.groups()[2]
                props['score'] = float(score)
                props['prev-score'] = float(prevScore)

        self.setProperty(key, props)


class PPBuildFactory(BuildFactory):

    def __init__(self, hgHost, **kwargs):
        self.parent_class = BuildFactory
        self.parent_class.__init__(self, **kwargs)
        self.hgHost = hgHost
        self.addStep(SetProperty(
            name='set_topdir',
            command=['pwd'],
            property='topdir',
            workdir='.',
        ))
        self.addStep(ShellCommand(
            name='rm_pyc',
            command=['find', '.', '-name', '*.pyc', '-exec', 'rm', '-fv', '{}',
                     ';'],
            workdir=".",
        ))

    def update_repo(self, repo, branch='default'):
        workdir = repo.split("/")[-1]
        repourl = 'http://%s/%s' % (self.hgHost, repo)
        self.addStep(ShellCommand(
            name='%s_update' % workdir,
            command=['bash', '-c',
                     'if test -d %(workdir)s; then hg -R %(workdir)s pull; \
                     else hg clone --noupdate %(repourl)s %(workdir)s; fi && \
                     hg -R %(workdir)s up -C --rev %(branch)s' % locals()],
            timeout=3*60,
            descriptionDone="%s source" % workdir,
            workdir='.',
        ))
        self.addStep(SetProperty(
            name='set_%s_revision' % workdir,
            command=['hg', 'identify', '-i'],
            property='%s_revision' % workdir,
            workdir=workdir,
        ))

    def setup_virtualenv(self, workdir='%(topdir)s/sandbox'):
        self.addStep(ShellCommand(
            name='rm_hg_dirs',
            command=['rm', '-rf', 'tools', 'buildbot', 'buildbotcustom',
                     'buildbot-configs'],
            workdir=WithProperties(workdir),
        ))
        self.update_repo('build/buildbot-configs')
        self.addStep(ShellCommand(
            name='setup_sandbox',
            command=['make', '-f', 'Makefile.setup',
                     'PYTHON=python2.6',
                     'VIRTUALENV=virtualenv-2.6',
                     'MASTER_NAME=fake',
                     WithProperties('BASEDIR=%s' % workdir),
                     'BUILDBOTCUSTOM_BRANCH=default',
                     'BUILDBOTCONFIGS_BRANCH=default',
                     'PIP_FLAGS=-rpreproduction-pip.txt',
                     'virtualenv', 'deps', 'install-buildbot'],
            workdir='buildbot-configs',
            env={'PIP_DOWNLOAD_CACHE': WithProperties('%s/cache' % workdir),
                 'CC': None,
                 'CXX': None
                },
            haltOnFailure=True,
        ))

    def test_masters(self):
        self.addStep(ShellCommand(
            name='test_masters',
            command=[
                'python', 'setup-master.py', '--test', '--masters-json',
                WithProperties('%(topdir)s/tools/buildfarm/maintenance/production-masters.json'),
                '--error-logs',
            ],
            env={'PATH':
                 WithProperties('%(topdir)s/sandbox/bin:/bin:/usr/bin'),
                 'PYTHONPATH':
                 WithProperties('%(topdir)s:%(topdir)s/tools/lib/python:%(topdir)s/tools/lib/python/vendor'),
                },
            workdir="buildbot-configs",
        ))

    def bbc_pylint(self):
        self.addStep(PyLintExtended(
                            command=["sandbox/bin/pylint",
                                     '--rcfile=buildbotcustom/.pylintrc',
                                     'buildbotcustom'],
                            workdir='.',
                            flunkOnFailure=False,
                            name='buildbotcustom_pylint',
                            project='buildbotcustom',
        ))

    def tools_pylint(self):
        self.addStep(PyLintExtended(
            command='../../../sandbox/bin/pylint --rcfile=../../.pylintrc *',
            workdir='tools/lib/python',
            flunkOnFailure=False,
            name='tools_lib_pylint',
            project='tools_lib',
        ))
        self.addStep(PyLintExtended(
            command='find buildbot-helpers buildfarm \
                clobberer release stage \
                -name \'*.py\' -type f -print0 | \
                xargs -0 ../sandbox/bin/pylint \
                --rcfile=.pylintrc',
            workdir="tools",
            flunkOnFailure=False,
            name='tools_scripts_pylint',
            project='tools_scripts',
        ))

    def tools_run_tests(self):
        self.addStep(ShellCommand(
            workdir='tools/release/signing',
            command=['python', 'tests.py'],
            name='release_signing_tests',
        ))
        self.addStep(ShellCommand(
            workdir='tools/lib/python',
            name='tools_lib_nosetests',
            env={'PYTHONPATH': '.:vendor'},
            command=['nosetests'],
        ))
        self.addStep(ShellCommand(
            workdir='tools/clobberer',
            name='clobbberer_test',
            command=['python', 'test_clobberer.py',
                     'http://preproduction-master.srv.releng.scl3.mozilla.com/~cltbld/index.php',
                     '/home/cltbld/public_html/db/clobberer.db'],
        ))

    def bbc_run_tests(self):
        self.addStep(ShellCommand(
            workdir='buildbotcustom',
            command=['bash', '-c',
                     'exit=0; for f in test/*.py; do trial $f || exit=1; done; exit $exit'],
            env={'PYTHONPATH': WithProperties('%(topdir)s/tools/lib/python:%(topdir)s:%(topdir)s/tools/lib/python/vendor')},
            name='buildbotcustom_tests',
            flunkOnFailure=False,
        ))

    def config_tests(self):
        self.addStep(ShellCommand(
            workdir='buildbot-configs/mozilla',
            command=['bash', '-c',
                     'exit=0; for f in test/*.py; do trial $f || exit=1; done; exit $exit'],
            name='mozilla_config_tests',
        ))
        self.addStep(ShellCommand(
            workdir='buildbot-configs/mozilla-tests',
            command=['bash', '-c',
                     'exit=0; for f in test/*.py; do trial $f || exit=1; done; exit $exit'],
            name='mozilla-tests_config_tests',
        ))

    def run_on_master(self, master_dir, cmd):
        self.addStep(ShellCommand(
            name='master_cmd',
            command='bash --login -c \'cd "%s" && %s\'' % (master_dir, cmd),
            workdir=master_dir,
            flunkOnFailure=False,
            timeout=5*60,
        ))

    def coverage(self, project):
        self.addStep(ShellCommand(
            name='rm_old_coverage_%s' % project,
            command=['rm', '-f', '.coverage'],
            workdir=project,
        ))
        self.addStep(ShellCommand(
            name='generate_coverage_%s' % project,
            command=['../sandbox/bin/coverage', 'run',  '--branch',
                     '--source=.',
                     WithProperties('--omit="%(topdir)s/sandbox/*,/usr/*,/tools/*,*/test/*"'),
                     '../sandbox/bin/nosetests'],
            workdir=project,
            env={'PYTHONPATH': WithProperties('%(topdir)s/tools/lib/python:%(topdir)s/tools/lib/python/vendor')},
            flunkOnFailure=False,
        ))
        self.addStep(ShellCommand(
            name='rm_old_coverage_html_%s' % project,
            command=['rm', '-fr', '../html/%s' % project],
            workdir=project,
        ))
        self.addStep(ShellCommand(
            name='generate_coverage_html_%s' % project,
            command=['../sandbox/bin/coverage', 'html',  '-d',
                     '../html/%s' % project, '--ignore-errors'],
            workdir=project,
        ))
        self.addStep(ShellCommand(
            name='fix_permissions_%s' % project,
            command=['chmod', 'u=rwX,g=rX,o=rX', '-R',
                     'html/%s' % project],
            workdir='.',
        ))
        self.addStep(ShellCommand(
            name='upload_coverage_html_%s' % project,
            command=['rsync', '-av', '--delete', '-e',
                     'ssh -o IdentityFile=~/.ssh/id_rsa -l cltbld -o BatchMode=yes',
                     'html/%s/' % project,
                     'preproduction-stage.srv.releng.scl3.mozilla.com:/var/www/html/coverage/%s/' % project],
            workdir='.',
        ))
