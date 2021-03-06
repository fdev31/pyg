import os
import sys
import site
import platform


def under_virtualenv():
    return hasattr(sys, 'real_prefix')

if hasattr(site, 'getsitepackages'):
    INSTALL_DIR = site.getsitepackages()[0]
    USER_SITE = site.getusersitepackages()
    ALL_SITE_PACKAGES = site.getsitepackages() + [USER_SITE]
else:
    # XXX: WORKAROUND for older python versions and some broken virtualenvs
    ## we have to guess site packages location...
    USER_SITE = site.USER_SITE
    INSTALL_DIR = None
    system = platform.system()
    if system == 'Linux':
        tmp = '{0}/local/lib/python{1}.{2}/'.format(sys.prefix, *sys.version_info[:2])
        d, s = os.path.join(tmp, 'dist-packages'), os.path.join(tmp, 'site-packages')
        if os.path.exists(d):
            INSTALL_DIR = d
        elif os.path.exists(s):
            INSTALL_DIR = s
    elif system == 'Windows':
        tmp = os.path.join(sys.prefix, 'site-packages')
        if os.path.exists(tmp):
            INSTALL_DIR = tmp
    if INSTALL_DIR is None:
        from distutils.sysconfig import get_python_lib
        INSTALL_DIR = get_python_lib(True)

    if under_virtualenv():
        ALL_SITE_PACKAGES = [INSTALL_DIR]
    else:
        ALL_SITE_PACKAGES = [INSTALL_DIR, USER_SITE]

    #try:
    #    INSTALL_DIR = sorted([p for p in sys.path if p.endswith('dist-packages')],
    #                        key=lambda i: 'local' in i, reverse=True)[0]
    #except IndexError:
    #    pass
    #if not INSTALL_DIR: ## Are we on Windows?
    #    try:
    #        INSTALL_DIR = sorted([p for p in sys.path if p.endswith('site-packages')],
    #                        key=lambda i: 'local' in i, reverse=True)[0]
    #    except IndexError:
    #        pass
    #if not INSTALL_DIR: ## We have to use /usr/lib/pythonx.y/dist-packages or something similar
    #    from distutils.sysconfig import get_python_lib
    #    INSTALL_DIR = get_python_lib()

## Under virtualenv USER_SITE is the same as INSTALL_DIR
if under_virtualenv():
    USER_SITE = INSTALL_DIR

EASY_INSTALL = os.path.join(INSTALL_DIR, 'easy-install.pth')
if not os.path.exists(EASY_INSTALL):
    d = os.path.dirname(EASY_INSTALL)
    try:
        if not os.path.exists(d):
            os.makedirs(d)
        open(EASY_INSTALL, 'w').close()
    ## We do not have root permissions...
    except IOError:
        ## So we do nothing!
        pass

PYG_LINKS = os.path.join(USER_SITE, 'pyg-links.pth')

if platform.system() == 'Windows':
    BIN = os.path.join(sys.prefix, 'Scripts')
    if not os.path.exists(BIN):
        BIN = os.path.join(sys.prefix, 'bin')
else:
    BIN = os.path.join(sys.prefix, 'bin')
    ## Forcing to use /usr/local/bin on standard Mac OS X
    if sys.platform[:6] == 'darwin' and sys.prefix[:16] == '/System/Library/':
        BIN = '/usr/local/bin'


## If we are running on a Unix system and we are in a SUDO session the `SUDO_UID`
## environment variable will be set. We can use that to get the user's home
## We also set to None all the variables that depend on HOME.

HOME = os.getenv('HOME')
PYG_HOME = None
CFG_FILES = [os.path.join(os.getcwd(), 'pyg.conf')]
_sudo_uid = os.getenv('SUDO_UID')
if _sudo_uid:
    import pwd
    _sudo_uid = int(_sudo_uid)
    HOME = pwd.getpwuid(_sudo_uid).pw_dir

## Here is Pyg's HOME directory
## If it does not exists we create it
if HOME is not None:
    PYG_HOME = os.path.join(HOME, '.pyg')
    if not os.path.exists(PYG_HOME):
        os.makedirs(PYG_HOME)

    ## PACKAGES_CACHE has been removed because with `pkg_resources.working_set` we
    ## don't need a cache
    CFG_FILES.extend([os.path.join(HOME, 'pyg.conf'),
                      os.path.join(PYG_HOME, 'pyg.conf')]
                    )
