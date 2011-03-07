import sys
from .web import PyPI, WebManager
from .inst import Installer
from .utils import is_installed, link
from .freeze import freeze


def install_from_name(name):
    return Installer(name).install()

def install_func(args):
    if args.develop:
        raise NotImplementedError('not implemented yet')
    if args.file:
        return Installer.from_file(args.file)
    if args.bundle:
        return Installer.from_bundle(args.bundle)
    return install_from_name(args.packname)

def uninst_func(args):
    return Installer(args.packname, mode='uninst').uninstall()

def link_func(args):
    return link(args.path)

def freeze_func(args):
    return sys.stdout.write(freeze())

def list_func(args):
    res = []
    name = args.packname
    versions = PyPI().package_releases(name, True)
    if not versions:
        versions = map(str, sorted(WebManager.versions_from_html(name), reverse=True))
    for v in versions:
        if is_installed('{0}=={1}'.format(name, v)):
            res.append(v + '\tinstalled')
        else:
            res.append(v)
    return sys.stdout.write('\n'.join(res) + '\n')

def search_func(args):
    res = PyPI().search({'name': args.packname})
    return sys.stdout.write('\n'.join('{name}  {version} - {summary}'.format(**i) for i in \
                            sorted(res, key=lambda i: i['_pypi_ordering'], reverse=True)) + '\n')