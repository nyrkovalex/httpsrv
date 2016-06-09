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

    def test_should_not_raise_if_specific_pending_requets_left(self):
        resolved_rule = server.on('GET', '/').text('hello')
        pending_rule = server.on('GET', '/pending').text('nope')
        requests.get('http://localhost:8080/')
        server.assert_no_pending(resolved_rule)

    def test_should_raise_if_target_rule_left_unresolved(self):
        resolved_rule = server.on('GET', '/').text('hello')
        pending_rule = server.on('GET', '/pending').text('nope')
        requests.get('http://localhost:8080/')
        with self.assertRaises(PendingRequestsLeftException):
            server.assert_no_pending(pending_rule)

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

    def test_should_match_request_headers(self):
        server.on('GET', '/', headers={'Authorization': 'Custom'}).text('hello')
        res = requests.get('http://localhost:8080', headers={'Authorization': 'Custom'})
        self.assertEqual(res.text, 'hello')

    def test_should_ignore_request_body(self):
        server.on('POST', '/').text('hello')
        res = requests.post('http://localhost:8080', data='Foo')
        self.assertEqual(res.text, 'hello')

    def test_should_match_json_bosy(self):
        server.on('POST', '/', json=dict(foo='bar')).text('hello')
        res = requests.post('http://localhost:8080', data='{ "foo": "bar" }')
        self.assertEqual(res.text, 'hello')

    def test_should_not_fall_on_json_parse_error(self):
        server.on('POST', '/', json=dict(foo='bar')).text('hello')
        res = requests.post('http://localhost:8080', data='{ "foo": }')
        self.assertEqual(res.status_code, 500)

    def test_should_ignore_text_when_json_present(self):
        server.on('POST', '/', json=dict(foo='bar'), text='{ "foo": "bar" }').text('hello')
        res = requests.post('http://localhost:8080', data='{"foo": "bar"}')
        self.assertEqual(res.text, 'hello')

    def test_should_respond_to_any_options(self):
        server.on('OPTIONS').status(200)
        res = requests.options('http://localhost:8080/some/url', headers={'foo': 'bar'})
        self.assertEqual(res.status_code, 200)

    def test_should_always_respond_to_matching_queries(self):
        server.always('OPTIONS').status(200)
        res = requests.options('http://localhost:8080/some/url', headers={'foo': 'bar'})
        self.assertEqual(res.status_code, 200)
        res = requests.options('http://localhost:8080/some/url', headers={'foo': 'bar'})
        self.assertEqual(res.status_code, 200)

    def test_should_reset_always_rules(self):
        server.always('OPTIONS').status(200)
        server.reset()
        res = requests.options('http://localhost:8080/some/url', headers={'foo': 'bar'})
        self.assertEqual(res.status_code, 500)


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
