import math
import yaml
import logging
import os
import tempfile
from datetime import datetime

import functools


DISABLED = False
BASE_DIR = os.path.join(tempfile.gettempdir(), __name__)
FORCE_RELOAD = 'cache_force'

log = logging.getLogger(__name__)
print 'caching to %s' % BASE_DIR
log.info('caching to %s' % BASE_DIR)

# Track functions that are known to have a cache
SEEN = []


class ForbiddenFilePath(Exception):
    pass


def _cache_dir(func):
    return os.path.join(BASE_DIR, func.__module__, func.__name__)


def cache_file(func, args):
    extras = "None"
    if args:
        extras = "-".join([str(a) for a in args])

    path = _cache_dir(func)

    mkdirs(path)

    return os.path.join(path, extras)


def clear(func):
    path = _cache_dir(func)

    if not os.path.exists(path):
        return

    for f in os.listdir(path):
        os.remove(os.path.join(path, f))


def clear_all(files=None, dry_run=True):
    path = os.path.abspath(BASE_DIR)
    path_len = len(path) + 1

    if not files and not dry_run:
        raise Exception('Must provide the file list to confirm.')

    if not files:
        files = []
        for root, _dirs, _files in os.walk(path, topdown=False):
            for name in _files:
                filepath = os.path.abspath(os.path.join(root, name))

                files.append(filepath[path_len:])

    if dry_run:
        return files
    else:
        return _remove_files(files)


def _remove_files(files=None):
    path = os.path.abspath(BASE_DIR)

    if not files:
        return []

    if not os.path.exists(path):
        return []

    removed = []
    to_remove = []

    for filename in files:
        filepath = os.path.abspath(os.path.join(path, filename))

        print "joined '%s' and '%s' to be '%s'" % (filename, path, filepath)

        if not filepath.startswith(path):
            raise ForbiddenFilePath(filepath)

        if not os.path.exists(filepath):
            continue

        to_remove.append(filepath)

    log.debug('removing from cache: %s' % removed)
    for filepath in to_remove:
        os.remove(filepath)
        removed.append(filepath)

    log.info("removed files from cache: %s" % to_remove)

    return removed


def is_expired(path, expiresAfter):
    if not os.path.exists(path):
        return False

    now = datetime.now()
    then = datetime.fromtimestamp(os.path.getmtime(path))

    since = math.floor((now - then).total_seconds())
    ttl = expiresAfter * 60

    if since > ttl:
        return True

    return False


def cache(expiresAfter=5):
    expiresAfter = math.floor(expiresAfter)

    def decorator(f):
        @functools.wraps(f)
        def f_cache(*args, **kwargs):
            # don't even hit the cache if it's disabled
            if DISABLED:
                return f(*args, **kwargs)

            if f not in SEEN:
                SEEN.append(f)

            # try and get the cache force from the keywords of the call
            force = False

            if FORCE_RELOAD in kwargs:
                force = kwargs[FORCE_RELOAD]
                del kwargs[FORCE_RELOAD]

            return function_cache(f, expiresAfter, force, *args, **kwargs)

        return f_cache
    return decorator


def function_cache(func, expiresAfter, force, *args, **kwargs):
    mkdirs(BASE_DIR)

    path = cache_file(func, args)
    isExpired = is_expired(path, expiresAfter)
    cacheExists = os.path.exists(path)

    try:
        if force or isExpired or not cacheExists:
            raise Exception('Forcing a reload')

        # always try and load from cache
        with open(path, 'r') as f:
            log.debug("cache hit for %s" % func.__name__)

            return yaml.load(f)
    except:
        log.debug("cache miss for %s (is expired: %s, forced: %s)" %
                  (func.__name__, isExpired, force))

        results = func(*args, **kwargs)

        with open(path, 'w') as f:
            f.write(yaml.dump(results, default_flow_style=False))

        return results


def mkdirs(path, raiseError=False):
    try:
        if not os.path.exists(path):
            os.makedirs(path)
    except Exception as e:
        log.error('unable to create temp directory: %s' % str(e))
        if raiseError:
            raise
