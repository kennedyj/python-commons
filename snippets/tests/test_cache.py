from mock import Mock, patch, call
import unittest
import datetime
import re

from .. import cache

BASE_DIR = "/tmp/some/path"

PATTERN_MISSING = r'(/tmp/some/path|.*one)$'

BASE_NAME = '%s.tests.test_cache' % cache.__name__.split('.')[0]


def function_cache(func, expiresAfter, force, *args, **kwargs):
    return expiresAfter, force, args, kwargs


def mock_join(*args):
    return '/'.join(args)


def mock_abspath(path):
    return path.replace("//", "/")


def mock_exists(pattern=r'*'):
    def _exists(name):
        if re.match(pattern, name):
            return True

        return False

    return _exists


class TestCache(unittest.TestCase):
    def setUp(self):
        self.now = datetime.datetime.now()
        self.then = self.now - datetime.timedelta(days=1)

        cache.DISABLED = False
        cache.BASE_DIR = BASE_DIR

    def test_cache_dir(self):
        result = cache._cache_dir(self.test_cache_dir)
        expected = '%s/%s/test_cache_dir' % (BASE_DIR, BASE_NAME)

        self.assertEqual(result, expected)

    def test_cache_file(self):
        """ Should return the path for the functions cache file """
        result = cache.cache_file(self.test_cache_dir, ['one'])
        expected = '%s/%s/test_cache_dir/one' % (BASE_DIR, BASE_NAME)

        self.assertEqual(result, expected)

        """ Test without parameters """
        result = cache.cache_file(self.test_cache_dir, [])
        expected = '%s/%s/test_cache_dir/None' % (BASE_DIR, BASE_NAME)

        self.assertEqual(result, expected)

    @patch('os.path.join')
    @patch('os.remove')
    @patch('os.listdir')
    @patch('os.path.exists')
    @patch.object(cache, '_cache_dir')
    def test_clear(self, cache_dir, exists, listdir, remove, join):
        """ Test all cases of clearing cache files """

        """ Path doesn't exist """
        exists.return_value = False

        cache.clear(self.test_clear)
        cache_dir.assert_called_once_with(self.test_clear)

        exists.return_value = True

        """ Path exists, remove files """
        cache_dir.return_value = 'dir'
        listdir.return_value = ['one']
        join.return_value = 'dir/one'

        cache.clear(self.test_clear)

        join.assert_called_once_with('dir', 'one')
        remove.assert_called_once_with('dir/one')

    @patch('os.path.getmtime')
    @patch('os.path.exists')
    def test_is_expired(self, exists, getmtime):
        """ Test all cases of is_expired """

        """ Cache file doesn't exist """
        exists.return_value = False
        self.assertFalse(cache.is_expired('/test/path', 5))

        """ Cache file isn't expired """
        exists.return_value = True

        with patch.object(cache, 'datetime') as mock_datetime:
            mock_datetime.now.return_value = self.now
            mock_datetime.fromtimestamp.return_value = self.now

            self.assertFalse(cache.is_expired('/test/path', 5))

            """ Cache file is expired """
            mock_datetime.fromtimestamp.return_value = self.then

            self.assertTrue(cache.is_expired('/test/path', 5))

    @patch.object(cache, 'function_cache', function_cache)
    def test_cache(self):
        cache_mock = Mock()
        cache_test = Mock()

        @cache.cache()
        def cache_test(*args, **kwargs):
            cache_mock(*args, **kwargs)

        results = cache_test(1, one=1)
        expected = (5.0, False, (1,), {'one': 1})

        self.assertEqual(results, expected)

        """ Test performing a cache force """
        results = cache_test(1, one=1, cache_force=True)
        expected = (5.0, True, (1,), {'one': 1})

        self.assertEqual(results, expected)

    @patch.object(cache, 'function_cache')
    def test_cache_enabled(self, func_cache):
        cache.DISABLED = True

        @cache.cache()
        def cache_test():
            return 'test return'

        results = cache_test()
        expected = 'test return'

        self.assertFalse(func_cache.called)
        self.assertEqual(results, expected)

    @patch('yaml.dump')
    @patch('yaml.load')
    @patch('os.path.exists')
    @patch.object(cache, 'is_expired')
    @patch.object(cache, 'cache_file')
    @patch.object(cache, 'mkdirs')
    def test_function_cache(self, mkdirs, cache_file, is_expired, exists,
                            yaml_load, yaml_dump):
        """ Test when the file doesn't exist, is forced or is expired """
        empty_test = Mock()
        empty_test.__name__ = 'empty_test'
        empty_test.return_value = 'from empty_test'

        is_expired.return_value = False
        exists.return_value = False
        cache_file.return_value = 'test.yaml'
        yaml_load.return_value = "from cache"

        """ File doesn't exist, isn't expired, and isn't forced """
        with patch.object(cache, 'open', create=True) as mock_open:
            result = cache.function_cache(empty_test, 5, False)

            mkdirs.assert_called_once_with(cache.BASE_DIR)
            mock_open.assert_called_once_with('test.yaml', 'w')
            self.assertEqual(result, "from empty_test")

            exists.return_value = True

            """ Exists, isn't expired, forced """
            result = cache.function_cache(empty_test, 5, True)
            self.assertEqual(result, "from empty_test")

            """ Exists, but expired """
            is_expired.return_value = True

            result = cache.function_cache(empty_test, 5, False)
            self.assertEqual(result, "from empty_test")

            self.assertEqual(yaml_load.call_count, 0)
            self.assertEqual(empty_test.call_count, 3)

    @patch('yaml.dump')
    @patch('yaml.load')
    @patch('os.path.exists')
    @patch.object(cache, 'is_expired')
    @patch.object(cache, 'cache_file')
    @patch.object(cache, 'mkdirs')
    def test_function_cache_hit(self, mkdirs, cache_file, is_expired, exists,
                                yaml_load, yaml_dump):
        """ Test when the loading from cache """
        empty_test = Mock()
        empty_test.return_value = 'from empty_test'
        empty_test.__name__ = 'empty_test'

        is_expired.return_value = False
        exists.return_value = True
        cache_file.return_value = 'test.yaml'
        yaml_load.return_value = "from cache"

        with patch.object(cache, 'open', create=True) as mock_open:
            result = cache.function_cache(empty_test, 5, False)

            mock_open.assert_called_once_with('test.yaml', 'r')

            self.assertEqual(result, "from cache")

    @patch('os.makedirs')
    @patch('os.path.exists')
    def test_mkdirs(self, exists, makedirs):
        """ Test create directories """
        exists.return_value = False

        cache.mkdirs('test')

        makedirs.assert_called_once_with('test')

    @patch('os.makedirs')
    @patch('os.path.exists')
    def test_mkdirs_exists(self, exists, makedirs):
        """ Test create directories when exists """
        exists.return_value = True

        cache.mkdirs('test')

        self.assertFalse(makedirs.called)

    @patch('os.makedirs')
    @patch('os.path.exists')
    def test_mkdirs_error(self, exists, makedirs):
        """ Test create directories raising an error """
        exists.return_value = False
        makedirs.side_effect = Exception('Boom!')

        cache.mkdirs('test')
        self.assertEqual(makedirs.call_count, 1)

        self.assertRaises(Exception, cache.mkdirs, 'test', raiseError=True)
        self.assertEqual(makedirs.call_count, 2)

    @patch('os.path.join', mock_join)
    @patch('os.path.abspath', mock_abspath)
    @patch.object(cache, '_remove_files')
    @patch('os.walk')
    def test_clear_all_dry(self, walk, remove):
        _files = ['one', 'two', 'three']
        walk.return_value = [(BASE_DIR, [], _files)]

        result = cache.clear_all(dry_run=True)

        self.assertFalse(remove.called)
        self.assertEqual(result, _files)

    @patch('os.path.join', mock_join)
    @patch('os.path.abspath', mock_abspath)
    @patch.object(cache, '_remove_files')
    @patch('os.walk')
    def test_clear_all_bad(self, walk, remove):
        self.assertRaises(Exception, cache.clear_all, [], dry_run=False)

        self.assertRaises(Exception, cache.clear_all, None, dry_run=False)

        self.assertRaises(Exception, cache.clear_all, dry_run=False)

        # remove never should have been called
        self.assertFalse(remove.called)

    @patch('os.path.join', mock_join)
    @patch('os.path.abspath', mock_abspath)
    @patch.object(cache, '_remove_files')
    @patch('os.walk')
    def test_clear_all_remove(self, walk, remove):
        files = ['%s/%s' % (BASE_DIR, n) for n in ['one', 'two']]

        cache.clear_all(files, dry_run=False)

        # walk should not have been called
        self.assertFalse(walk.called)

        remove.assert_called_once_with(files)

    @patch('os.path.join', mock_join)
    @patch('os.remove')
    @patch('os.path.exists')
    def test__remove_files(self, exists, os_remove):
        filenames = ['one', 'two']
        fullpaths = ['%s/%s' % (BASE_DIR, n) for n in filenames]

        exists.return_value = True

        self.assertEqual(cache._remove_files(filenames), fullpaths)

        calls = [call('%s/%s' % (BASE_DIR, f)) for f in filenames]

        self.assertEqual(os_remove.call_args_list, calls)

    @patch('os.path.exists', mock_exists(PATTERN_MISSING))
    @patch('os.path.join', mock_join)
    @patch('os.remove')
    def test__remove_files_missing(self, os_remove):
        filenames = ['one', 'two']
        expected = ['%s/%s' % (BASE_DIR, n) for n in ['one']]

        self.assertEqual(cache._remove_files(filenames), expected)

        calls = [call('%s/%s' % (BASE_DIR, f)) for f in ['one']]

        self.assertEqual(os_remove.call_args_list, calls)

    @patch('os.path.join', mock_join)
    @patch('os.path.abspath', mock_abspath)
    @patch('os.remove')
    @patch('os.path.exists')
    def test__remove_files_none(self, exists, os_remove):
        exists.return_value = True

        self.assertEqual(cache._remove_files(None), [])
        self.assertEqual(cache._remove_files([]), [])

        exists.return_value = False

        self.assertEqual(cache._remove_files(['one']), [])

        # Should not have been called
        self.assertFalse(os_remove.called)

    @patch('os.path.join', mock_join)
    @patch('os.remove')
    @patch('os.path.exists')
    def test__remove_files_bad(self, exists, os_remove):
        """ Attempt to put a path in a lower directory """
        exists.return_value = True
        filenames = ['one', '../../two']

        self.assertRaises(
            cache.ForbiddenFilePath,
            cache._remove_files, filenames)

        self.assertFalse(os_remove.called)
