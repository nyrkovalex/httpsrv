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
            server.on_any('GET', '/').text('hello')
            res = requests.get('http://localhost:8080')
            assert res.text == 'hello'

        def test_should_always_respond_to_options(self):
            # this means that any OPTIONS request will get status 200
            # such behavior is particulary useful when mocking preflight queries
            server.on_any('OPTIONS', always=True).status(200)
            res = requests.get('http://localhost:8080')
            assert res.status_code == 200

        def test_should_respond_to_json(self):
            # this means that server will respond to the POST request
            # containing target json document in its body
            server.on_json('POST', '/users', {'name': 'John Doe'}).json(
                {'id': 1, 'name': 'John Doe'}, status=201)
            res = requests.post('http://localhost:8080/users', json={'name': 'John Doe'})
            assert res.status_code == 201

For more details and full list of ``on_*`` methods see `API documentation`_


Installation
------------

::

    pip install httpsrv


Documentation
-------------

http://httpsrv.readthedocs.org


.. _requests: http://docs.python-requests.org/en/master/
.. _httpsrvvcr: https://httpsrvvcr.readthedocs.io/
.. _API documentation: http://httpsrv.readthedocs.io/en/latest/api.html