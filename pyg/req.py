import operator
import cStringIO

from hashlib import md5

from pyg.utils import PYTHON_VERSION, ext, right_egg
from pyg.web import ReqManager, LinkFinder, request
from pyg.types import Version, Egg, Archive, ReqSet, InstallationError
from pyg.log import logger


__all__ = ['Requirement']


class Requirement(object):

    OPMAP = {'==': operator.eq,
             '>=': operator.ge,
             '>': operator.gt,
             '<=': operator.le,
             '<': operator.lt,
             '!=': lambda a,b: a != b,
              None: lambda a,b: True, ##FIXME: does None really work?
             }

    def __init__(self, req):
        self.req = req
        self.reqset = ReqSet()
        self.split()

    def __repr__(self):
        return 'Requirement({0})'.format(self.req)

    def __str__(self):
        return str(self.req)

    def split(self):
        for c in ('==', '>=', '>', '<=', '<'):
            if c in self.req:
                self.name, self.op, self.version = map(str.strip, self.req.partition(c))
                self.version = Version(self.version)
                break
        else:
            self.name = self.req.split()[0]
            self.version = None
            self.op = None

    @ staticmethod
    def find_version(s):
        v = []
        for c in s:
            if c.isdigit() or c == '.':
                v.append(c)
            else:
                break
        return Version(''.join(v).strip('.')) ## FIXME do we really need .strip() ?

    def match(self, v):
        return self.OPMAP[self.op](v, self.version)

    #def best_match(self, reqs):
    #    matched = {}
    #    for r in reqs:
    #        parts = r.split('-')
    #        version = Requirement.find_version('-'.join(parts[1:]))
    #        if self.version is None or self.match(version):
    #            matched[version] = r
    #    if len(matched) == 0:
    #        return None
    #    elif len(matched) == 1:
    #        return matched[matched.keys()[0]]
    #    ## The highest version possible
    #    return matched[max(matched)] ## OR matched[sorted(matched.keys(), reverse=True)[0]]?

    def _download_and_install(self, url, filename, packname, hash=None):
        logger.info('Downloading {0}', self.name)
        fobj = cStringIO.StringIO(request(url))
        if hash is not None:
            logger.info('Checking md5 sum')
            if md5(fobj.getvalue()).hexdigest() != hash:
                logger.fatal('Error: {0} appears to be corrupted', self.name)
                return
        e = ext(filename)
        if e in ('.tar.gz', '.tar.bz2', '.zip'):
            installer = Archive(fobj, e, packname, self.reqset)
        elif e == '.egg':
            installer = Egg(fobj, filename, self.reqset, packname)
        else:
            logger.error('Error: unknown filetype: {0}', e, exc=InstallationError)

        ## There is no need to catch exceptions now, this will be done by `pyg.inst.Installer.install`
        installer.install()
        self.success = True

    def install(self):
        logger.info('Looking for {0} releases on PyPI', self.name)
        p = ReqManager(self)
        self.success = False
        for pext in ('.tar.gz', '.tar.bz2', '.zip', '.egg'):
            for v, name, hash, url in p.files()[pext]:
                if pext == '.egg' and not right_egg(name):
                    continue
                if ext(name) not in ('.tar.gz', '.tar.bz2', '.zip', '.egg'):
                    continue
                logger.info('Best match: {0}=={1}', self.name, v)
                try:
                    self._download_and_install(url, name, p.name, hash)
                except InstallationError:
                    continue
                if not self.version:
                    self.version = v
                break
            if self.success:
                break
        if not self.success:
            logger.warn('Warning: did not find files on PyPI for {0}', self.name)
            logger.info('Looking for links on PyPI')
            try:
                link_finder = LinkFinder(self.name)
                links = link_finder.find()
            except Exception as e:
                raise InstallationError(str(e))
            for url in link_finder.find():
                filename = url.split('/')[-1]
                logger.info('Found: {0}', filename)
                try:
                    self._download_and_install(url, filename, self.name)
                except Exception as e:
                    logger.error('Error: {0}', e)
                    continue
                break
            if not self.success:
                raise InstallationError('Fatal: cannot install {0}'.format(self.name))
