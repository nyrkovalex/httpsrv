import json

from contextlib import contextmanager
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler


class PendingRequestsLeftException(Exception):
    pass


class Rule:
    def __init__(self, server, method, url, data=None):
        self._server = server
        self.method = method
        self.url = url
        self.data = data
        self.response = None
        self.headers = None

    def respond(self, text, headers=None):
        self.headers = headers or {}
        self.response = text
        return self._server

    def json(self, json_doc, headers=None):
        headers = headers or {}
        if 'content-type' not in headers:
            headers['content-type'] = 'application/json'
        return self.respond(json.dumps(json_doc), headers)

    def matches(self, method, url, data):
        print('matching', method, url, data)
        return self.method == method and self.url == url and self.data == data


class Server:
    def __init__(self, port):
        self._port = port
        self._rules = []
        self._thread = None
        self._server = None
        self.running = False

    def on_get(self, url):
        rule = Rule(self, 'GET', url)
        self._rules.append(rule)
        return rule

    def on_post(self, url, data=None):
        rule = Rule(self, 'POST', url, data)
        self._rules.append(rule)
        return rule


    def start(self):
        handler_class = create_handler_class(self._rules)
        self._server = HTTPServer(('', self._port), handler_class)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self.running = True
        return self

    def stop(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()
        self.running = False

    @contextmanager
    def run(self):
        try:
            yield self.start()
        finally:
            self.stop()

    def reset(self):
        self._rules.clear()

    def assert_no_pending(self):
        if self._rules:
            raise PendingRequestsLeftException()


def create_handler_class(rules):

    class Handler(BaseHTTPRequestHandler):
        def _read_body(self):
            if 'content-length' in self.headers:
                length = int(self.headers['content-length'])
                return self.rfile.read(length).decode('utf-8') if length > 0 else None
            return None

        def _respond(self, rule):
            self.send_response(200)
            for key, value in rule.headers.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(rule.response.encode('utf-8'))

        def _handle(self, method):
            body = self._read_body()
            matching_rules = [r for r in rules if r.matches(method, self.path, body)]
            if not matching_rules:
                return self.send_error(
                    500, 'No matching rule found for ' + self.requestline + ' body ' + str(body))
            rule = matching_rules[0]
            self._respond(rule)
            rules.remove(rule)

        def do_GET(self):
            return self._handle('GET')

        def do_POST(self):
            return self._handle('POST')


    return Handler


def listen(port):
    return Server(port)
