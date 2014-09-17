from mock import patch
import unittest

from .. import retry


class RetryTests(unittest.TestCase):
    def test_check(self):
        "it should return true"
        self.assertTrue(retry.check(1, 1, 1))

    def test_check_bad_tries(self):
        "it should raise a value error due to tries being -1"
        self.assertRaises(ValueError, retry.check, -1, 1, 1)

    def test_check_bad_delay(self):
        "it should raise a value error due to delay being 0"
        self.assertRaises(ValueError, retry.check, 1, 0, 1)

    def test_check_bad_backoff(self):
        "it should raise a value error due to backoff being 0"
        self.assertRaises(ValueError, retry.check, 1, 1, 0)

    def test_handle(self):
        "it should call the passed in method and return true"
        def test_func():
            return True

        self.assertTrue(retry.handle(retry.RetriableError, test_func))

    def test_handle_exception(self):
        "it should call the passed in method and return an exception"
        exception = retry.RetriableError('Woo!')

        def test_func():
            raise exception

        self.assertEqual(
            exception,
            retry.handle(retry.RetriableError, test_func))

    def test_retry(self):
        "it should call the decorated method and return it's value"
        @retry.retry(0)
        def test_func():
            return True

        self.assertTrue(test_func())

    def test_retry_disabled(self):
        '''it should call the decorated method and raise it's exception
        but should only run once'''
        retry.disabled = True
        self.counter = 0

        @retry.retry(3)
        def test_func():
            self.counter += 1
            raise retry.RetriableError('failed')

        self.assertRaises(retry.RetriableError, test_func)
        retry.disabled = False
        self.assertEqual(self.counter, 1)

    @patch.object(retry, 'check')
    def test_retry_fail(self, mock_check):
        "it should call the decorated method and raise it's exception"
        mock_check.return_value = True
        self.counter = 0

        @retry.retry(1, 0, 0)
        def test_func():
            self.counter += 1
            raise retry.RetriableError('failed')

        self.assertRaises(retry.RetriableError, test_func)
        self.assertEqual(self.counter, 2)

    @patch.object(retry, 'check')
    def test_retry_fail_once(self, mock_check):
        "it should call the decorated method and raise it's exception"
        mock_check.return_value = True
        self.counter = 0

        @retry.retry(2, 0, 0)
        def test_func():
            if self.counter > 0:
                return True

            self.counter += 1
            raise retry.RetriableError('failed')

        self.assertTrue(test_func())
        self.assertEqual(self.counter, 1)
