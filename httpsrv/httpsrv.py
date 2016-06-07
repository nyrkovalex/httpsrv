'''
Httpsrv is a simple HTTP server for API mocking during automated testing
'''
import json

from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler


class PendingRequestsLeftException(Exception):
    '''
    Raises when server has pending reques expectations by calling
    the :func:`Server.assert_no_pending` method
    '''
    pass


class _Expectation:
    def __init__(self, method, path, headers, text, json):
        self.method = method
        self.path = path
        self.headers = headers or {}
        self.bytes = text.encode('utf-8') if text else None
        self.json = json

    def matches(self, method, path, headers, bytes):
        return (self.method == method
                and self.path == path
                and self._match_headers(headers)
                and self._match_body(bytes))

    def _match_headers(self, headers):
        for name, value in self.headers.items():
            if not (name in headers and value == headers[name]):
                return False
        return True

    def _match_body(self, bytes):
        if not self.json:
            return bytes == self.bytes if self.bytes else True
        try:
            parsed = json.loads(bytes.decode('utf8'))
            return self.json == parsed
        except ValueError:
            return False


class _Response:
    def __init__(self, code=200, headers=None, bytes=None):
        self.code = code
        self.headers = headers or {}
        self.bytes = bytes


class Rule:
    '''
    Expectation rule — defines expected request parameters and response values

    :type method: str
    :param method: expected request method: ``'GET'``, ``'POST'``, etc.
        Can take any custom string

    :type path: str
    :param path: expected path including query parameters, e.g. ``'/users?name=John%20Doe'``

    :type headers: dict
    :param headers: dictionary of expected request headers

    :type text: str
    :param text: expected request body text

    :type json: dict
    :param json: request json to expect. If ommited any json will match,
        if present text param will be ignored
    '''
    def __init__(self, method, path, headers, text, json):
        self._expectation = _Expectation(method, path, headers, text, json)
        self.response = None

    def status(self, status, headers=None):
        '''
        Respond with given status and no content

        :type status: int
        :param status: status code to return

        :type headers: dict
        :param headers: dictionary of headers to add to response

        :returns: itself
        :rtype: Rule
        '''
        self.response = _Response(status, headers)
        return self

    def text(self, text, status=200, headers=None):
        '''
        Respond with given status and text content

        :type text: str
        :param text: text to return

        :type status: int
        :param status: status code to return

        :type headers: dict
        :param headers: dictionary of headers to add to response

        :returns: itself
        :rtype: Rule
        '''
        self.response = _Response(status, headers, text.encode('utf8'))
        return self

    def json(self, json_doc, status=200, headers=None):
        '''
        Respond with given status and JSON content. Will also set ``'Content-Type'`` to
        ``'applicaion/json'`` if header is not specified explicitly

        :type json_doc: dict
        :param json_doc: dictionary to respond with converting to JSON string

        :type status: int
        :param status: status code to return

        :type headers: dict
        :param headers: dictionary of headers to add to response
        '''
        headers = headers or {}
        if 'content-type' not in headers:
            headers['content-type'] = 'application/json'
        return self.text(json.dumps(json_doc), status, headers)

    def matches(self, method, path, headers, bytes=None):
        '''
        Checks if rule matches given request parameters

        :type method: str
        :param method: HTTP method, e.g. ``'GET'``, ``'POST'``, etc.
            Can take any custom string

        :type path: str
        :param path: request path including query parameters,
            e.g. ``'/users?name=John%20Doe'``

        :type bytes: bytes
        :param bytes: request body

        :returns: ``True`` if this rule matches given params
        :rtype: bool
        '''
        return self._expectation.matches(method, path, headers, bytes)


class Server:
    '''
    Tunable HTTP server running in a parallel thread.

    Please note that `this server is not thread-safe` which should not cause any troubles
    in common use-cases due to python single-threaded nature.

    :type port: int
    :param port: port this server will listen to after :func:`Server.start` is called
    '''
    def __init__(self, port):
        self._port = port
        self._rules = []
        self._thread = None
        self._server = None
        self._handler = None
        self.running = False

    # pylint: disable=invalid-name
    def on(self, method, path, headers=None, text=None, json=None):
        '''
        Defines a :class:`Rule` expectation — after recieving a request with matching parameters
        target response will be sent

        :type method: str
        :param method: request method: ``'GET'``, ``'POST'``, etc. can be some custom string

        :type path: str
        :param path: request path including query parameters

        :type headers: dict
        :param headers: dictionary of headers to expect. If omitted any headers will do

        :type text: str
        :param text: request text to expect. If ommited any text will match

        :type json: dict
        :param json: request json to expect. If ommited any json will match,
            if present text param will be ignored

        :rtype: Rule
        :returns: newly created expectation rule
        '''
        rule = Rule(method, path, headers, text, json)
        self._rules.append(rule)
        if method not in self._handler.known_methods:
            self._handler.add_method(method)
        return rule
    # pylint: enable=invalid-name

    def start(self):
        '''
        Starts a server on the port provided in the :class:`Server` constructor
        in a separate thread

        :rtype: Server
        :returns: server instance for chaining
        '''
        self._handler = _create_handler_class(self._rules)
        self._server = HTTPServer(('', self._port), self._handler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self.running = True
        return self

    def stop(self):
        '''
        Shuts the server down and waits for server thread to join
        '''
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()
        self.running = False

    def reset(self):
        '''
        Clears the server expectations. Useful for resetting the server to its default state
        in ``teardDown()`` test method instead of time-consuming restart procedure
        '''
        self._rules.clear()

    def assert_no_pending(self, target_rule=None):
        '''
        Raises a :class:`PendingRequestsLeftException` error if server has target rule
        non-resolved.

        When target_rule argument is ommitted raises if server has any pending
        expectations.

        Useful in ``tearDown()`` test method to verify that test had correct expectations

        :type target_rule: Rule
        :param target_rule: will raise if this rule is left pending

        :raises: :class:`PendingRequestsLeftException`
        '''
        if target_rule:
            if target_rule in self._rules:
                raise PendingRequestsLeftException()
        elif self._rules:
            raise PendingRequestsLeftException()


def _create_handler_class(rules):
    class _Handler(BaseHTTPRequestHandler):
        known_methods = set()

        @classmethod
        def add_method(cls, method):
            '''
            Adds a handler function for HTTP method provided
            '''
            if method in cls.known_methods:
                return
            func = lambda self: cls._handle(self, method)
            setattr(cls, 'do_' + method, func)
            cls.known_methods.add(method)

        def _read_body(self):
            if 'content-length' in self.headers:
                length = int(self.headers['content-length'])
                return self.rfile.read(length) if length > 0 else None
            return None

        def _respond(self, response):
            self.send_response(response.code)
            for key, value in response.headers.items():
                self.send_header(key, value)
            self.end_headers()
            if response.bytes:
                self.wfile.write(response.bytes)

        def _handle(self, method):
            body = self._read_body()
            matching_rules = [r for r in rules if r.matches(method, self.path, dict(self.headers), body)]
            if not matching_rules:
                return self.send_error(
                    500, 'No matching rule found for ' + self.requestline + ' body ' + str(body))
            rule = matching_rules[0]
            self._respond(rule.response)
            rules.remove(rule)

    for rule in rules:
        _Handler.add_method(rule.method)

    return _Handler
