import json

from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler


class PendingRequestsLeftException(Exception):
    pass


class Rule:
    def __init__(self, method, path, headers=None, text=None):
        self.method = method
        self.path = path
        self.data = text.encode('utf-8') if text else None
        self.response = None
        self.headers = headers or {}
        self.code = 200

    def status(self, status, headers=None):
        self.code = status
        self.headers.update(headers or {})

    def text(self, text, status=None, headers=None):
        self.status(status or self.code, headers)
        self.response = text.encode('utf-8')

    def json(self, json_doc, status=None, headers=None):
        headers = headers or {}
        if 'content-type' not in headers:
            headers['content-type'] = 'application/json'
        return self.text(json.dumps(json_doc), status, headers)

    def matches(self, method, path, data):
        return self.method == method and self.path == path and self.data == data


class Server:
    '''
    Tunable HTTP server running in a parallel thread.

    Example usage (using `requests` library)::
        server = Server(8080).start()
        server.on('GET', '/').text('hello')
        res = requests.get('http://localhost:8080')
        assert res.text == 'hello'
    '''

    def __init__(self, port):
        '''
        Creates an instance of :class:`Server`

        :param port: port this server will listen to after :func:`Server.start` is called
        '''
        self._port = port
        self._rules = []
        self._thread = None
        self._server = None
        self._handler = None
        self.running = False

    def on(self, method, path, headers=None, text=None):
        '''
        Defines a rule expectation — after recieving a request with matching parameters
        target response will be sent

        :param method: request method: `'GET'`, `'POST'`, etc. can be some custom string
        :param path: request path including query parameters
        :param headers: (optional) dictionary of headers to expect.
            All keys must be lowercase, e.g. `'content-type'`
        :param text: (optional) response text to expect
        '''
        rule = Rule(method, path, headers, text)
        self._rules.append(rule)
        if method not in self._handler.known_methods:
            self._handler.add_method(method)
        return rule

    def start(self):
        self._handler = create_handler_class(self._rules)
        self._server = HTTPServer(('', self._port), self._handler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self.running = True
        return self

    def stop(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()
        self.running = False

    def reset(self):
        self._rules.clear()

    def assert_no_pending(self):
        if self._rules:
            raise PendingRequestsLeftException()


def create_handler_class(rules):
    class Handler(BaseHTTPRequestHandler):
        known_methods = set()

        @classmethod
        def add_method(cls, method):
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

        def _respond(self, rule):
            self.send_response(rule.code)
            for key, value in rule.headers.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(rule.response)

        def _handle(self, method):
            body = self._read_body()
            matching_rules = [r for r in rules if r.matches(method, self.path, body)]
            if not matching_rules:
                return self.send_error(
                    500, 'No matching rule found for ' + self.requestline + ' body ' + str(body))
            rule = matching_rules[0]
            self._respond(rule)
            rules.remove(rule)

    for rule in rules:
        Handler.add_method(rule.method)

    return Handler
