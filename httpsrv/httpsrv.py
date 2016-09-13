'''
Httpsrv is a simple HTTP server for API mocking during automated testing
'''
import json as libjson
from threading import Thread

import tornado.web
import tornado.ioloop
from tornado.gen import coroutine



class PendingRequestsLeftException(Exception):
    '''
    Raises when server has pending reques expectations by calling
    the :func:`Server.assert_no_pending` method
    '''
    pass


class _Expectation:
    def __init__(self, method, path, headers):
        self.method = method
        self.path = path
        self.headers = headers or {}

    def matches(self, request):
        return (self._match_method(request)
                and self._match_path(request)
                and self._match_headers(request)
                and self.match_content(request))

    def _match_method(self, request):
        return self.method == request.method

    def _match_path(self, request):
        return self.path == request.uri if self.path else True

    def _match_headers(self, request):
        for name, value in self.headers.items():
            if not (name in request.headers and value == request.headers[name]):
                return False
        return True

    def match_content(self, request):
        raise NotImplementedError('Implement in a base class')


class _AnyExpectation(_Expectation):
    def match_content(self, request):
        return True


class _TextExpectation(_Expectation):
    def __init__(self, method, path, headers, text):
        super().__init__(method, path, headers)
        self.text = text.encode('utf-8')

    def match_content(self, request):
        return self.text == request.body


class _JsonExpectation(_Expectation):
    def __init__(self, method, path, headers, json):
        super().__init__(method, path, headers)
        self.json = json

    def match_content(self, request):
        try:
            return self.json == libjson.loads(request.body.decode('utf8'))
        except ValueError:
            return False


class _FormExpectation(_Expectation):
    def __init__(self, method, path, headers, form):
        super().__init__(method, path, headers)
        self.form = {}
        for name, values in form.items():
            self.form[name] = [v.encode('utf-8') for v in values]

    def match_content(self, request):
        return self.form == request.arguments


class _FilesExpectation(_Expectation):
    def __init__(self, method, path, headers, files, form):
        super().__init__(method, path, headers)
        self.files = files
        self.form = form
        self._form_expectation = _FormExpectation(method, path, headers, form or {})

    def match_content(self, request):
        if self.form:
            form_ok = self._form_expectation.match_content(request)
            if not form_ok:
                return False
        for field, expected in self.files.items():
            uploaded = request.files.get(field)
            if not uploaded:
                return False
            if not self._compare_files(expected, uploaded):
                return False
        return True

    def _compare_files(self, expected, uploaded):
        for filename, contents in expected.items():
            if not self._file_in_uploaded(filename, contents, uploaded):
                return False
        return True

    def _file_in_uploaded(self, filename, contents, uploaded):
        for file in uploaded:
            if file.filename == filename and file.body == contents:
                return True


class _Response:
    def __init__(self, code=200, headers=None, body=None):
        self.code = code
        self.headers = headers or {}
        self.bytes = body


class Rule:
    '''
    Expectation rule — defines expected request parameters and response values

    :type method: str
    :param method: expected request method: ``'GET'``, ``'POST'``, etc.
        Can take any custom string

    :type path: str
    :param path: expected path including query parameters, e.g. ``'/users?name=John%20Doe'``
        if ommited any path will do

    :type headers: dict
    :param headers: dictionary of expected request headers

    :type text: str
    :param text: expected request body text

    :type json: dict
    :param json: request json to expect. If ommited any json will match,
        if present text param will be ignored
    '''
    def __init__(self, expectation):
        self._expectation = expectation
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
        return self.text(libjson.dumps(json_doc), status, headers)

    def matches(self, request):
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
        return self._expectation.matches(request)

    @property
    def method(self):
        '''
        Method name this rule will respond to

        :returns: epected method name
        :rtype: str
        '''
        return self._expectation.method


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
        self._always_rules = []
        self._thread = None
        self._server = None

    def on_any(self, method, path=None, headers=None, always=False):
        '''
        Request with any content. Path is optional if omitted any path will match.

        Server will respond to matching parameters one time and remove the rule from list
        unless ``always`` flag is set to ``True``

        :type method: str
        :param method: request method: ``'GET'``, ``'POST'``, etc. can be some custom string

        :type path: str
        :param path: request path including query parameters. If omitted any path will do

        :type headers: dict
        :param headers: dictionary of headers to expect. If omitted any headers will do

        :type always: bool
        :param always: if ``True`` this rule will not be removed after use

        :rtype: Rule
        :returns: newly created expectation rule
        '''
        return self._add_rule(_AnyExpectation(method, path, headers), always)

    def on_text(self, method, path, text, headers=None, always=False):
        '''
        Request with generic text data. Can be used if nothing else matches.

        Server will respond to matching parameters one time and remove the rule from list
        unless ``always`` flag is set to ``True``
        :type method: str
        :param method: request method: ``'GET'``, ``'POST'``, etc. can be some custom string

        :type path: str
        :param path: request path including query parameters

        :type text: str
        :param text: expected text sent with request

        :type headers: dict
        :param headers: dictionary of headers to expect. If omitted any headers will do

        :type always: bool
        :param always: if ``True`` this rule will not be removed after use

        :rtype: Rule
        :returns: newly created expectation rule
        '''
        return self._add_rule(_TextExpectation(method, path, headers, text), always)

    def on_json(self, method, path, json, headers=None, always=False):
        '''
        Request with JSON body. This will not check for ``Content-Type`` header.
        Instead we'll try to parse whatever request body contains.'

        Server will respond to matching parameters one time and remove the rule from list
        unless ``always`` flag is set to ``True``

        :type method: str
        :param method: request method: ``'GET'``, ``'POST'``, etc. can be some custom string

        :type path: str
        :param path: request path including query parameters

        :type json: dict
        :param json: expected json data

        :type headers: dict
        :param headers: dictionary of headers to expect. If omitted any headers will do

        :type always: bool
        :param always: if ``True`` this rule will not be removed after use

        :rtype: Rule
        :returns: newly created expectation rule
        '''
        return self._add_rule(_JsonExpectation(method, path, headers, json), always)

    def on_form(self, method, path, form, headers=None, always=False):
        '''
        Request with form data either in requets body or query params.

        Server will respond to matching parameters one time and remove the rule from list
        unless ``always`` flag is set to ``True``


        :type method: str
        :param method: request method: ``'GET'``, ``'POST'``, etc. can be some custom string

        :type path: str
        :param path: request path including query parameters

        :type form: dict
        :param json: expected form data. **Please note that filed values must always be
            of collection type** e.g. ``{'user': ['Dude']}``. this restriction is caused by possible
            multivalue fields and may be lifted in future releases

        :type headers: dict
        :param headers: dictionary of headers to expect. If omitted any headers will do

        :type always: bool
        :param always: if ``True`` this rule will not be removed after use

        :rtype: Rule
        :returns: newly created expectation rule
        '''
        return self._add_rule(_FormExpectation(method, path, headers, form), always)

    def on_files(self, method, path, files, form=None, headers=None, always=False):
        '''
        File upload with optional form data.

        Server will respond to matching parameters one time and remove the rule from list
        unless ``always`` flag is set to ``True``

        :type method: str
        :param method: request method: ``'GET'``, ``'POST'``, etc. can be some custom string

        :type path: str
        :param path: request path including query parameters

        :type form: dict
        :param json: expected form data. **Please note that filed values must always BaseException
            of collection type e.g. ``{'user': ['Dude']}``.** this restriction is caused by possible
            multivalue fields and may be lifted in future releases

        :type headers: dict
        :param headers: dictionary of headers to expect. If omitted any headers will do

        :type always: bool
        :param always: if ``True`` this rule will not be removed after use

        :rtype: Rule
        :returns: newly created expectation rule
        '''
        return self._add_rule(_FilesExpectation(method, path, headers, files, form), always)

    def _add_rule(self, expectation, always):
        rule = Rule(expectation)
        if always:
            self._always_rules.append(rule)
        else:
            self._rules.append(rule)
        return rule

    def start(self):
        '''
        Starts a server on the port provided in the :class:`Server` constructor
        in a separate thread

        :rtype: Server
        :returns: server instance for chaining
        '''
        app = tornado.web.Application([
            (r'.*', _TornadoHandler, dict(rules=self._rules, always_rules=self._always_rules)),
        ])
        app.listen(self._port)
        self._thread = Thread(target=tornado.ioloop.IOLoop.current().start, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        '''
        Shuts the server down and waits for server thread to join
        '''
        tornado.ioloop.IOLoop.current().stop()
        self._thread.join()

    def reset(self):
        '''
        Clears the server expectations. Useful for resetting the server to its default state
        in ``teardDown()`` test method instead of time-consuming restart procedure
        '''
        self._rules.clear()
        self._always_rules.clear()

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


class _TornadoHandler(tornado.web.RequestHandler):
    # pylint: disable=w0223,w0221

    def initialize(self, rules, always_rules):
        self._rules = rules
        self._always_rules = always_rules

    @coroutine
    def prepare(self):
        rule = self._find_rule(self._rules)
        if rule:
            # Order is important here - we should respond only after
            # the rule is removed, or we may run into concurency issues
            self._rules.remove(rule)
            self._respond(rule.response)
            return
        always_rule = self._find_rule(self._always_rules)
        if always_rule:
            self._respond(always_rule.response)
            return
        self.set_status(500)
        self.write(
            'No matching rule found for ' +
            self.request.uri + ' body ' +
            str(self.request.body))
        self.finish()

    def _find_rule(self, rules):
        matching_rules = [r for r in rules if r.matches(self.request)]
        if matching_rules:
            rule = matching_rules[0]
            return rule
        return None

    def _respond(self, response):
        self.set_status(response.code)
        for key, value in response.headers.items():
            self.set_header(key, value)
        if response.bytes:
            self.write(response.bytes)
        self.finish()
