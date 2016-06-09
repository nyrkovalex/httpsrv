Httpsrv
=======

Simple http server for API mocking during automated testing
Plays nicely with httpsrvvcr_ library for automated request recording


Example usage
-------------

A typical usage pattern would probably look like the one below.

Using requests_ library::

    import unittest
    import requests
    from httpsrv import Server

    server = Server(8080).start()

    class MyTestCase(unittest.TestCase):
        def setUp(self):
            server.reset()

        def test_should_get_hello(self):
            # this means that server will respond once upon GET request
            # further GET requests on this path will get 500
            server.on('GET', '/').text('hello')
            res = requests.get('http://localhost:8080')
            assert res.text == 'hello'

        def test_should_always_respond_to_options(self):
            # this means that any OPTIONS request will get status 200
            # such behavior is particulary useful when mocking preflight queries
            server.always('OPTIONS').status(200)
            res = requests.get('http://localhost:8080')
            assert res.status_code == 200


Installation
------------

::

    pip install httpsrv


Documentation
-------------

http://httpsrv.readthedocs.org


.. _requests: http://docs.python-requests.org/en/master/
.. _httpsrvvcr: https://httpsrvvcr.readthedocs.io/
