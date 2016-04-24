# pylint: disable=missing-docstring,invalid-name
import json
import unittest
import requests
from httpsrv import Server, PendingRequestsLeftException


server = Server(8080).start()


class ServerTest(unittest.TestCase):
    def tearDown(self):
        server.reset()


class TextResponses(ServerTest):
    def test_should_launch_http_server(self):
        server.on('GET', '/').text('hello')
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.text, 'hello')

    def test_should_reset_server_state(self):
        server.on('GET', '/').text('Hello')
        server.reset()
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.status_code, 500)

    def test_should_serve_multiple_responses_to_same_url(self):
        server.on('GET', '/').text('Hello')
        server.on('GET', '/').text('Goodbye')
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.text, 'Hello')
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.text, 'Goodbye')

    def test_should_serve_multiple_responses_to_different_urls(self):
        server.on('GET', '/').text('Hello')
        server.on('POST', '/foo').text('Bar')
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.text, 'Hello')
        res = requests.post('http://localhost:8080/foo')
        self.assertEqual(res.text, 'Bar')

    def test_should_respond_500_if_no_rule_matches(self):
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.status_code, 500)

    def test_should_match_by_query_parameters(self):
        server.on('GET', '/user?name=John').text('John Doe')
        res = requests.get('http://localhost:8080/user?name=John')
        self.assertEqual(res.text, 'John Doe')

    def test_should_set_header(self):
        headers = {'x-header': 'some'}
        server.on('GET', '/').text('hello', headers=headers)
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.headers['x-header'], 'some')

    def test_should_raise_if_pending_requetss_left(self):
        server.on('GET', '/').text('hello')
        with self.assertRaises(PendingRequestsLeftException):
            server.assert_no_pending()

    def test_should_not_raise_anything(self):
        server.assert_no_pending()

    def test_should_respond_to_post(self):
        server.on('POST', '/').text('hello')
        res = requests.post('http://localhost:8080')
        self.assertEqual(res.text, 'hello')

    def test_should_expect_post_body(self):
        server.on('POST', '/', text='foo=bar').text('hello')
        res = requests.post('http://localhost:8080', data='foo=bar')
        self.assertEqual(res.text, 'hello')

    def test_should_respond_with_text_and_code_201(self):
        server.on('GET', '/').text('hello', status=201)
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.status_code, 201)


class JsonResponses(ServerTest):
    def test_should_respond_with_json(self):
        expected = dict(hello='world')
        server.on('GET', '/').json(expected)
        res = requests.get('http://localhost:8080')
        self.assertEqual(json.loads(res.text), expected)

    def test_should_set_content_type_responding_with_json(self):
        server.on('GET', '/').json(dict(hello='world'))
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.headers['content-type'], 'application/json')

    def test_should_not_change_content_type(self):
        headers = {'content-type': 'text/plain'}
        server.on('GET', '/').json(dict(hello='world'), headers=headers)
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.headers['content-type'], 'text/plain')

    def test_should_respond_with_json_and_code_201(self):
        server.on('GET', '/').json(dict(foo='bar'), status=201)
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.status_code, 201)


class StatusResponses(ServerTest):
    def test_should_respond_with_status(self):
        server.on('GET', '/').status(400)
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.status_code, 400)

    def test_should_respond_with_status_and_headers(self):
        server.on('GET', '/').status(400, headers={'x-foo': 'bar'})
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.headers['x-foo'], 'bar')
