import pkg_resources

from pyg.req import Requirement
from pyg.web import get_versions
from pyg.utils import is_installed


__all__ = ['freeze', 'list_releases']


def freeze():
    '''Freeze the current environment (i.e. all installed packages).'''

    packages = []
    for dist in pkg_resources.working_set:
        packages.append('{0.project_name}=={0.version}'.format(dist))
    return sorted(packages)

def list_releases(name):
    '''List all releases for the given requirement.'''

    name = name[:-1] + '_' if name.endswith('-') else name
    res = []
    for v in get_versions(Requirement(name)):
        v = str(v)
        if is_installed('{0}=={1}'.format(name, v)):
            res.append((v, True))
        else:
            res.append((v, False))
    return res