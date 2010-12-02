import re
import textwrap
from buildbot.process.factory import BuildFactory
from buildbot.steps.python_twisted import RemovePYCs
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
    veCommand = textwrap.dedent("""
                unset CC
                unset CXX
                VE_VER=1.4.9
                export PIP_DOWNLOAD_CACHE=$PWD/cache
                mkdir -p $PIP_DOWNLOAD_CACHE
                wget -O- http://pypi.python.org/packages/source/v/virtualenv/virtualenv-${VE_VER}.tar.gz \
                    | tar -xz  virtualenv-${VE_VER}/virtualenv.py || exit 1

                PYTHON=/tools/python/bin/python
                $PYTHON virtualenv-${VE_VER}/virtualenv.py --distribute --no-site-packages . || exit 1
                rm -rf virtualenv-${VE_VER}
                PYTHON=$PWD/bin/python
                PATH=$PWD/bin:$PATH
                $PYTHON -c 'import json' 2>/dev/null || \
                    $PYTHON -c 'import  simplejson' || \
                    ./bin/pip install simplejson || exit 1
                $PYTHON -c 'import sqlite3, sys; assert sys.version_info >= (2,6)' 2>/dev/null \
                    || $PYTHON -c 'import pysqlite2.dbapi2' || \
                    ./bin/pip install pysqlite || exit 1;
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
                ./bin/pip install pyopenssl==0.10 || exit 1;
                hg clone http://hg.mozilla.org/build/buildbot
                (cd buildbot/master; $PYTHON setup.py develop install) || exit 1;
                (cd buildbot/slave; $PYTHON setup.py develop install) || exit 1;
                rm -rf buildbot
                """)

    def __init__(self, hgHost, **kwargs):
        self.parent_class = BuildFactory
        self.parent_class.__init__(self, **kwargs)
        self.hgHost = hgHost
        self.addStep(SetProperty(name='set_topdir',
                                 command=['pwd'],
                                 property='topdir',
                                 workdir='.',
                    ))
        self.addStep(RemovePYCs(workdir="."))

    def update_repo(self, repo, branch):
        workdir = repo.split("/")[-1]
        repourl = 'http://%s/%s' % (self.hgHost, repo)
        self.addStep(
            ShellCommand(name='%s_update' % workdir,
                         command=['bash', '-c',
                                  'if test -d %(workdir)s; then hg -R %(workdir)s pull; \
                                     else hg clone --noupdate %(repourl)s %(workdir)s; fi && \
                                   hg -R %(workdir)s up -C --rev %(branch)s' % locals()],
                         timeout=3*60,
                         descriptionDone="%s source" % workdir,
                         workdir='.',
                    ))
        self.addStep(
            SetProperty(name='set_%s_revision' % workdir,
                        command=['hg', 'identify', '-i'],
                        property='%s_revision' % workdir,
                        workdir=workdir,
                    ))
        if repo == 'build/tools':
            self.addStep(
                ShellCommand(
                    name='sync_tools_repo',
                    timeout=3*60,
                    workdir='tools',
                    command='hg push -e "ssh -i ~cltbld/.ssh/ffxbld_dsa -l prepr-ffxbld" ssh://hg.mozilla.org/users/prepr-ffxbld/tools'
                ))

    def setup_virtualenv(self, workdir='sandbox'):
        self.addStep(
            ShellCommand(name='rm_old_sandbox',
                         command=['rm', '-rf', 'bin', 'lib', 'include'],
                         workdir=workdir,
                    ))
        self.addStep(
            ShellCommand(
                name='setup_sandbox',
                command=self.veCommand,
                workdir=workdir,
                haltOnFailure=True,
        ))

    def test_masters(self):
        self.addStep(ShellCommand(name='test_masters',
                                  command=['./test-masters.sh', '-8'],
                                  env = {
                                      'PYTHONPATH':
                                      WithProperties('%(topdir)s:%(topdir)s/tools/lib/python'),
                                      'PATH': WithProperties('%(topdir)s/sandbox/bin:/bin:/usr/bin'),
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
        # TODO: move pylintrc to tools
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
                            env = {'PYTHONPATH':
                                   WithProperties('%(topdir)s:%(topdir)s/tools/lib/python')},
                            flunkOnFailure=False,
                            name='tools_scripts_pylint',
                            project='tools_scripts',
                    ))

    def tools_run_tests(self):
        self.addStep(ShellCommand(
            workdir='tools/release/signing',
            command=['python', 'tests.py'],
            flunkOnFailure=False,
            name='release_signing_tests',
        ))
        self.addStep(ShellCommand(
            workdir='tools/lib/python',
            env={'PYTHONPATH': WithProperties('%(topdir)s/tools/lib/python')},
            name='run_lib_nosetests',
            command=['nosetests'],
        ))
        self.addStep(ShellCommand(
            workdir='tools/clobberer',
            flunkOnFailure=False,
            name='run_clobbberer_test',
            command=['python', 'test_clobberer.py',
                     'http://preproduction-master.build.mozilla.org/~cltbld/index.php',
                     '/home/cltbld/public_html/db/clobberer.db'],
        ))

    def run_on_master(self, master_dir, cmd):
        self.addStep(MasterShellCommand(name='master_cmd',
                                        command='bash --login -c \'cd "%s" && %s\'' % (master_dir,
                                                                   cmd)
                    ))

    def coverage(self, project):
        self.addStep(
            ShellCommand(name='rm_old_coverage_%s' % project,
                         command=['rm', '-f', '.coverage'],
                         workdir=project,
                    ))
        self.addStep(
            ShellCommand(name='generate_coverage_%s' % project,
                         command=['../sandbox/bin/coverage', 'run',  '--branch',
                                  '--source=.',
                                  WithProperties('--omit="%(topdir)s/sandbox/*,/usr/*,/tools/*,*/test/*"'),
                                  '../sandbox/bin/nosetests'],
                         workdir=project,
                         flunkOnFailure=False,
                    ))
        self.addStep(
            ShellCommand(name='rm_old_coverage_html_%s' % project,
                         command=['rm', '-fr', '../html/%s' % project],
                         workdir=project,
                    ))
        self.addStep(
            ShellCommand(name='generate_coverage_html_%s' % project,
                         command=['../sandbox/bin/coverage', 'html',  '-d',
                                  '../html/%s' % project, '--ignore-errors'],
                         workdir=project,
                    ))
        self.addStep(
            ShellCommand(name='fix_permissions_%s' % project,
                         command=['chmod', 'u=rwX,g=rX,o=rX', '-R',
                                  'html/%s' % project],
                         workdir='.',
                    ))
        self.addStep(
            ShellCommand(name='upload_coverage_html_%s' % project,
                         command=['rsync', '-av', '--delete', '-e',
                                  'ssh -i ~/.ssh/id_rsa -l cltbld -o BatchMode=yes',
                                  'html/%s/' % project,
                                  'preproduction-stage.build.mozilla.org:/var/www/html/coverage/%s/' % project],
                         workdir='.',
                    ))
