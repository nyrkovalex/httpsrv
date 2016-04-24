.. include:: docs/intro.rst

Httpsrv
=======

Simple http server for API mocking


Example usage
-------------

Using requests_ library::

    >>> import requests
    >>> from httpsrv import Server
    >>> server = Server(8080).start()
    >>> server.on('GET', '/').text('hello')
    >>> res = requests.get('http://localhost:8080')
    >>> assert res.text == 'hello'


Installation
------------

To be done


.. _requests: http://docs.python-requests.org/en/master/


Documentation
-------------

http://httpsrv.readthedocs.org
