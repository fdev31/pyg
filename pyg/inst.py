import re
import os
import sys
import site
import shutil
import urlparse
import ConfigParser
import pkg_resources

from pkgtools.pypi import PyPIJson
from pkgtools.pkg import WorkingSet, Installed
from pyg.web import WebManager
from pyg.req import Requirement
from pyg.locations import EASY_INSTALL, USER_SITE, BIN, PACKAGES_CACHE
from pyg.utils import TempDir, File, ext, is_installed
from pyg.types import Version, Archive, Egg, Bundle, ReqSet, PygError, InstallationError, \
                    AlreadyInstalled, Dir, args_manager
from pyg.parser.parser import init_parser
from pyg.log import logger


__all__ = ['Installer', 'Uninstaller', 'Updater']


class Installer(object):
    def __init__(self, req):
        if is_installed(req):
            if not args_manager['upgrade']:
                logger.info('{0} is already installed', req)
                raise AlreadyInstalled
            else:
                logger.info('{0} is already installed, upgrading...', req)
        self.req = req

    @ staticmethod
    def _install_deps(rs, name=None):
        if not rs:
            return
        if not args_manager['deps']:
            logger.info('Skipping dependencies for {0}', name)
            return
        logger.info('Installing dependencies...')
        for req in rs:
            logger.indent = 0
            logger.info('Installing {0}', req)
            logger.indent = 8
            try:
                Installer(req).install()
            except AlreadyInstalled:
                continue
        logger.indent = 0
        logger.info('Finished installing dependencies')

    def install(self):
        r = Requirement(self.req)
        try:
            r.install()
        except AlreadyInstalled:
            logger.info('{0} is already installed', r.name)
        except InstallationError as e:
            logger.error('E: {0}', e, exc=InstallationError)

        # Now let's install dependencies
        Installer._install_deps(r.reqset, r.name)
        logger.info('{0} installed successfully', r.name)

    @ staticmethod
    def from_req_file(filepath):
        path = os.path.abspath(filepath)
        not_installed = set()
        parser = init_parser()
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line.startswith('#'):
                    logger.debug('Comment found: {0}', line)
                    continue
                try:
                    logger.indent = 0
                    logger.info('Installing: {0}', line)
                    logger.indent = 8
                    parser.dispatch(argv=['install'] + line.split())
                except AlreadyInstalled:
                    continue
                except InstallationError:
                    not_installed.add(line)
                except SystemExit as e:
                    if e.code != 0:
                        logger.warn('W: {0} tried to raise SystemExit: skipping installation')
                    else:
                        logger.info('{0} tried to raise SystemExit, but the exit code was 0')
        if not_installed:
            logger.warn('These packages have not been installed:')
            logger.indent = 8
            for req in not_installed:
                logger.info(req)
            logger.indent = 0
            raise InstallationError

    @ staticmethod
    def from_file(filepath):
        e = ext(filepath)
        path = os.path.abspath(filepath)
        packname = os.path.basename(filepath).split('-')[0]
        reqset = ReqSet()

        if is_installed(packname) and not args_manager['upgrade']:
            logger.info('{0} is already installed', packname)
            raise AlreadyInstalled

        if e in ('.tar.gz', '.tar.bz2', '.zip'):
            installer = Archive(open(path), e, packname, reqset)
        elif e in ('.pybundle', '.pyb'):
            installer = Bundle(filepath, reqset)
        elif e == '.egg':
            installer = Egg(open(path), path, reqset)
        else:
            logger.fatal('E: Cannot install {0}', packname)
            raise InstallationError
        installer.install()
        Installer._install_deps(reqset, packname)
        logger.info('{0} installed successfully', packname)

    @ staticmethod
    def from_dir(path, name=None):
        name = name or os.path.basename(path)
        reqset = ReqSet()
        try:
            with TempDir() as tempdir:
                logger.info('Installing {0}', name)
                Dir(path, name, tempdir, reqset).install()
        except Exception as e:
            logger.fatal('E: {0}: cannot install the package', e, exc=InstallationError)
        else:
            if reqset:
                Installer._install_deps(reqset)
            logger.info('{0} installed successfully', name)

    @ staticmethod
    def from_url(url, packname=None):
        with TempDir() as t:
            packname = packname if packname is not None else urlparse.urlsplit(url).path.split('/')[-1]
            path = os.path.join(t, packname)
            logger.info('Installing {0}', packname)
            with open(path, 'w') as f:
                f.write(WebManager.request(url))
            Installer.from_file(path)


class Uninstaller(object):
    def __init__(self, packname, yes=False):
        self.name = packname
        self.yes = yes

    def uninstall(self):
        uninstall_re = re.compile(r'{0}(-(\d\.?)+(\-py\d\.\d)?\.(egg|egg\-info))?$'.format(self.name), re.I)
        uninstall_re2 = re.compile(r'{0}(?:(\.py|\.pyc))'.format(self.name), re.I)
        path_re = re.compile(r'\./{0}-[\d\w\.]+-py\d\.\d.egg'.format(self.name), re.I)
        path_re2 = re.compile(r'\.{0}'.format(self.name), re.I)

        to_del = set()
        try:
            dist = pkg_resources.get_distribution(self.name)
        except pkg_resources.DistributionNotFound:
            logger.debug('debug: dist not found: {0}', self.name)

            ## Create a fake distribution
            ## In Python2.6 we can only use site.USER_SITE
            class FakeDist(object):
                def __getattribute__(self, a):
                    if a == 'location':
                        return USER_SITE
                    return (lambda *a: False)
            dist = FakeDist()

        if sys.version_info[:2] < (2, 7):
            guesses = [os.path.dirname(dist.location)]
        else:
            guesses = site.getsitepackages() + [site.getusersitepackages()]
        for d in guesses:
            try:
                for file in os.listdir(d):
                    if uninstall_re.match(file) or uninstall_re2.match(file):
                        to_del.add(os.path.join(d, file))
            ## When os.listdir fails
            except OSError:
                continue

        ## Checking for package's scripts...
        if dist.has_metadata('scripts') and dist.metadata_isdir('scripts'):
            for s in dist.metadata_listdir('scripts'):
                to_del.add(os.path.join(BIN, script))

                ## If we are on Win we have to remove *.bat files too
                if sys.platform == 'win32':
                    to_del.add(os.path.join(BIN, script) + '.bat')

        ## Very important!
        ## We want to remove all files: even console scripts!
        if dist.has_metadata('entry_points.txt'):
            config = ConfigParser.ConfigParser()
            config.readfp(File(dist.get_metadata_lines('entry_points.txt')))
            if config.has_section('console_scripts'):
                for name, value in config.items('console_scripts'):
                    n = os.path.join(BIN, name)
                    if not os.path.exists(n) and n.startswith('/usr/bin'): ## Searches in the local path
                        n = os.path.join('/usr/local/bin', name)
                    to_del.add(n)
                    if sys.platform == 'win32':
                        to_del.add(n + '.exe')
                        to_del.add(n + '.exe.manifest')
                        to_del.add(n + '-script.py')
        if not to_del:
            logger.warn('{0}: did not find any file to delete', self.name)
            raise PygError
        logger.info('Uninstalling {0}', self.name)
        logger.indent += 8
        for d in to_del:
            logger.info(d)
        logger.indent -= 8
        while True:
            if self.yes:
                u = 'y'
            else:
                u = raw_input('Proceed? (y/[n]) ').lower()
            if u in ('n', ''):
                logger.info('{0} has not been uninstalled', self.name)
                break
            elif u == 'y':
                for d in to_del:
                    try:
                        shutil.rmtree(d)
                    except OSError: ## It is not a directory
                        try:
                            os.remove(d)
                        except OSError:
                            logger.error('E: Cannot delete: {0}', d)
                    logger.info('Deleting: {0}', d)
                logger.info('Removing egg path from easy_install.pth...')
                with open(EASY_INSTALL) as f:
                    lines = f.readlines()
                with open(EASY_INSTALL, 'w') as f:
                    for line in lines:
                        if path_re.match(line) or path_re2.match(line):
                            continue
                        f.write(line)
                logger.info('{0} uninstalled succesfully', self.name)
                break


class Updater(object):
    def __init__(self):
        if not PACKAGES_CACHE or not os.path.exists(PACKAGES_CACHE) or not args_manager['use_cache']:
            open(PACKAGES_CACHE, 'w').close()
            logger.info('Cache file not found: $HOME/.pyg/installed_packages.txt')
            self.working_set = list(WorkingSet(onerror=self._pkgutil_onerror, debug=logger.debug))
        else:
            logger.info('Reading cache...')
            with open(PACKAGES_CACHE, 'r') as f:
                self.working_set = []
                for line in f:
                    line = line.strip()
                    package, path = line.split()
                    try:
                        dist = Installed(package)
                    except ValueError:
                        dist = Installed(os.path.basename(path))
                    self.working_set.append((package, (path, dist))
                                            )
        logger.info('{0} packages loaded', len(self.working_set))

    def _pkgutil_onerror(self, pkgname):
        logger.debug('Error while importing {0}', pkgname)

    def upgrade(self, package_name, json, version):
        ## FIXME: Do we have to remove the package old version?
        #logger.info('Removing {0} old version', package_name)
        #logger.indent += 8
        #Uninstaller(package_name, True).uninstall()
        #logger.indent = 0
        args_manager['upgrade'] = True
        logger.info('Upgrading {0} to {1}', package_name, version)
        logger.indent += 8
        for release in json['urls']:
            logger.info('Installing {0}...', release['filename'])
            logger.indent += 4
            try:
                Installer.from_url(release['url'])
                break
            except Exception as e:
                logger.error('E: An error occurred while installing {0}: {1}', package_name, e)
                logger.info('Trying another file...')
                logger.indent -= 4
        else:
            logger.fatal('E: Did not find any release on PyPI for {0}', package_name)
        logger.indent = 0

    def update(self):
        logger.info('Searching for updates')
        if PACKAGES_CACHE:
            with open(PACKAGES_CACHE, 'w') as f:
                for package, data in self.working_set:
                    f.write('{0} {1}\n'.format(package, data[0]))
        for package, data in self.working_set:
            path, dist = data
            try:
                json = PyPIJson(package).retrieve()
                new_version = Version(json['info']['version'])
            except Exception as e:
                logger.error('E: Failed to fetch data for {0}', package, exc=PygError)
            if Version(dist.version) >= new_version:
                continue

            logger.info('A new release is avaiable for {0}: {1!s} (old {2})', package, new_version, dist.version)
            while True:
                if args_manager['yes']:
                    u = 'y'
                else:
                    u = raw_input('Do you want to upgrade? (y/[n]) ').lower()
                if u in ('n', ''):
                    logger.info('{0} has not been upgraded', package)
                    break
                elif u == 'y':
                    self.upgrade(package, json, new_version)
                    break
        logger.info('Updating finished successfully')
