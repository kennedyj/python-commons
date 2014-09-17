import math
import time
import sys


disabled = False


class RetriableError(Exception):
    pass


def check(tries, delay, backoff):
    if tries < 0:
        raise ValueError("tries must be 0 or greater")

    if delay <= 0:
        raise ValueError("delay must be greater than 0")

    if backoff <= 0:
        raise ValueError("backoff must be greater than 0")

    return True


def handle(except_on, f, *args, **kwargs):
    try:
        return f(*args, **kwargs)
    except except_on as e:
        return e


def function_retry(tries, delay, backoff, except_on, f, *args, **kwargs):
    mtries, mdelay = tries, delay  # make mutable

    # first call
    rv = handle(except_on, f, *args, **kwargs)

    while mtries > 0:
        if not isinstance(rv, Exception):  # Done on success
            break

        if disabled:
            break

        mtries -= 1         # consume an attempt
        time.sleep(mdelay)  # wait...
        mdelay *= backoff   # make future wait longer

        # Try again
        rv = handle(except_on, f, *args, **kwargs)

    if not isinstance(rv, Exception):  # Done on success
        return rv
    else:
        raise rv, None, sys.exc_info()[2]  # Ran out of tries


# Retry decorator with backoff
def retry(tries, delay=1, backoff=1, except_on=RetriableError):
    '''Retries a function or method until it returns True.

    delay sets the initial delay in seconds, and backoff sets the factor by
    which the delay should lengthen after each failure.

    tries must be at least 0, and delay greater than 0.'''

    tries = math.floor(tries)
    check(tries, delay, backoff)

    def decorator(f):
        def f_retry(*args, **kwargs):
            return function_retry(
                tries, delay, backoff, except_on, f, *args, **kwargs)
        return f_retry  # true decorator -> decorated function
    return decorator    # @retry(arg[, ...]) -> true decorator
