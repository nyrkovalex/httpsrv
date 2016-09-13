# pylint: disable=missing-docstring,invalid-name,no-self-use
import json
import unittest
import requests
from httpsrv import Server, PendingRequestsLeftException


server = Server(8080).start()


class ServerTest(unittest.TestCase):
    def tearDown(self):
        server.reset()


class AnyRequests(ServerTest):
    def test_should_launch_http_server(self):
        server.on_any('GET', '/').text('hello')
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.text, 'hello')

    def test_should_reset_server_state(self):
        server.on_any('GET', '/').text('Hello')
        server.reset()
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.status_code, 500)

    def test_should_serve_multiple_responses_to_same_url(self):
        server.on_any('GET', '/').text('Hello')
        server.on_any('GET', '/').text('Goodbye')
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.text, 'Hello')
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.text, 'Goodbye')

    def test_should_serve_multiple_responses_to_different_urls(self):
        server.on_any('GET', '/').text('Hello')
        server.on_any('POST', '/foo').text('Bar')
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.text, 'Hello')
        res = requests.post('http://localhost:8080/foo')
        self.assertEqual(res.text, 'Bar')

    def test_should_respond_500_if_no_rule_matches(self):
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.status_code, 500)

    def test_should_match_by_query_parameters(self):
        server.on_any('GET', '/user?name=John').text('John Doe')
        res = requests.get('http://localhost:8080/user?name=John')
        self.assertEqual(res.text, 'John Doe')

    def test_should_set_header(self):
        headers = {'x-header': 'some'}
        server.on_any('GET', '/').text('hello', headers=headers)
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.headers['x-header'], 'some')

    def test_should_raise_if_pending_requetss_left(self):
        server.on_any('GET', '/').text('hello')
        with self.assertRaises(PendingRequestsLeftException):
            server.assert_no_pending()

    def test_should_not_raise_if_specific_pending_requets_left(self):
        resolved_rule = server.on_any('GET', '/').text('hello')
        server.on_any('GET', '/pending').text('nope')
        requests.get('http://localhost:8080/')
        server.assert_no_pending(resolved_rule)

    def test_should_raise_if_target_rule_left_unresolved(self):
        server.on_any('GET', '/').text('hello')
        pending_rule = server.on_any('GET', '/pending').text('nope')
        requests.get('http://localhost:8080/')
        with self.assertRaises(PendingRequestsLeftException):
            server.assert_no_pending(pending_rule)

    def test_should_not_raise_anything(self):
        server.assert_no_pending()

    def test_should_respond_to_post(self):
        server.on_any('POST', '/').text('hello')
        res = requests.post('http://localhost:8080')
        self.assertEqual(res.text, 'hello')

    def test_should_respond_with_text_and_code_201(self):
        server.on_any('GET', '/').text('hello', status=201)
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.status_code, 201)

    def test_should_match_request_headers(self):
        server.on_any('GET', '/', headers={'Authorization': 'Custom'}).text('hello')
        res = requests.get('http://localhost:8080', headers={'Authorization': 'Custom'})
        self.assertEqual(res.text, 'hello')

    def test_should_ignore_request_body(self):
        server.on_any('POST', '/').text('hello')
        res = requests.post('http://localhost:8080', data='Foo')
        self.assertEqual(res.text, 'hello')

    def test_should_respond_to_any_options(self):
        server.on_any('OPTIONS').status(200)
        res = requests.options('http://localhost:8080/some/url', headers={'foo': 'bar'})
        self.assertEqual(res.status_code, 200)


class MultipartUploads(ServerTest):
    def test_should_respond_to_multipart_post(self):
        expected_files = {
            'user': {'user': b'Dude'}
        }
        server.on_files('POST', '/upload', files=expected_files).text('Let\'s go bowling')
        res = requests.post('http://localhost:8080/upload', files=dict(user=b'Dude'))
        self.assertEqual(res.text, 'Let\'s go bowling')

    def test_should_respond_to_multipart_post_with_multiple_files(self):
        expected_files = {
            'dude': {'dude': b'Lebowski'},
            'walter': {'walter': b'Sobchak'},
        }
        server.on_files(
            'POST', '/upload', expected_files).text('Let\'s go bowling')
        res = requests.post(
            'http://localhost:8080/upload',
            files=dict(dude=b'Lebowski', walter='Sobchak'))
        self.assertEqual(res.text, 'Let\'s go bowling')

    def test_should_respond_to_multipart_post_with_multiple_files_under_one_name(self):
        expected_files = {
            'bowlers': {
                'dude': b'Lebowski',
                'walter': b'Sobchak',
            }
        }
        server.on_files('POST', '/upload', expected_files).text('Let\'s go bowling')
        res = requests.post(
            'http://localhost:8080/upload',
            files=[
                ('bowlers', ('dude', 'Lebowski')),
                ('bowlers', ('walter', 'Sobchak')),
            ])
        self.assertEqual(res.text, 'Let\'s go bowling')

    def test_should_fail_on_wrong_upload_url(self):
        expected_files = {
            'user': {'user': b'Dude'}
        }
        server.on_files('POST', '/upload', files=expected_files).text('Let\'s go bowling')
        res = requests.post('http://localhost:8080/fail', files=dict(user=b'Dude'))
        self.assertEqual(res.status_code, 500)

    def test_should_fail_on_wrong_file_content(self):
        expected_files = {
            'user': {'user': b'Dude'}
        }
        server.on_files('POST', '/upload', files=expected_files).text('Let\'s go bowling')
        res = requests.post('http://localhost:8080/upload', files=dict(user=b'Walter'))
        self.assertEqual(res.status_code, 500)

    def test_should_respond_to_mixed_file_and_form_content(self):
        expected_files = {
            'user': {'user': b'Dude'}
        }
        server.on_files(
            'POST',
            '/upload',
            form={'foo': ('bar',)},
            files=expected_files).text('Let\'s go bowling')
        res = requests.post(
            'http://localhost:8080/upload',
            data={'foo': 'bar'},
            files=dict(user=b'Dude'))
        self.assertEqual(res.text, 'Let\'s go bowling')

    def test_should_fail_to_respond_to_mixed_file_and_form_content(self):
        expected_files = {
            'user': {'user': b'Dude'}
        }
        server.on_files(
            'POST',
            '/upload',
            form={'foo': ('baz',)},
            files=expected_files).text('Let\'s go bowling')
        res = requests.post(
            'http://localhost:8080/upload',
            data={'foo': 'bar'},
            files=dict(user=b'Dude'))
        self.assertEqual(res.status_code, 500)


class TextRequests(ServerTest):
    def test_should_expect_post_body(self):
        server.on_text('POST', '/', 'foo=bar').text('hello')
        res = requests.post('http://localhost:8080', data=dict(foo='bar'))
        self.assertEqual(res.text, 'hello')

    def test_should_respond_to_text(self):
        server.on_text('POST', '/', 'Hi!').text('Goodbye!')
        res = requests.post('http://localhost:8080', data='Hi!')
        self.assertEqual(res.text, 'Goodbye!')


class JsonRequests(ServerTest):
    def test_should_match_json_bosy(self):
        server.on_json('POST', '/', json=dict(foo='bar')).text('hello')
        res = requests.post('http://localhost:8080', data='{"foo": "bar" }')
        self.assertEqual(res.text, 'hello')

    def test_should_not_fall_on_json_parse_error(self):
        server.on_json('POST', '/', json=dict(foo='bar')).text('hello')
        res = requests.post('http://localhost:8080', data='{"foo": }')
        self.assertEqual(res.status_code, 500)

    def test_should_ignore_text_when_json_present(self):
        server.on_json('POST', '/', json=dict(foo='bar')).text('hello')
        res = requests.post('http://localhost:8080', data='{"foo": "bar"}')
        self.assertEqual(res.text, 'hello')


class FormRequests(ServerTest):
    def test_should_respond_to_form_data(self):
        server.on_form('POST', '/form', {
            'name': ('Dude',)
        }).text('Lebowski')
        res = requests.post('http://localhost:8080/form', data={'name': 'Dude'})
        self.assertEqual(res.text, 'Lebowski')

    def test_should_respond_to_multivalue_form_data(self):
        server.on_form('POST', '/form', {
            'name': ('Dude', 'Lebowski')
        }).text('Lebowski')
        res = requests.post('http://localhost:8080/form', data={
            'name': ['Dude', 'Lebowski']
        })
        self.assertEqual(res.text, 'Lebowski')

    def test_should_not_respond_to_wrong_field_value(self):
        server.on_form('POST', '/form', {
            'name': ('Dude',)
        }).text('Lebowski')
        res = requests.post('http://localhost:8080/form', data={'name': 'Walter'})
        self.assertEqual(res.status_code, 500)


class JsonResponses(ServerTest):
    def test_should_respond_with_json(self):
        expected = dict(hello='world')
        server.on_any('GET', '/').json(expected)
        res = requests.get('http://localhost:8080')
        self.assertEqual(json.loads(res.text), expected)

    def test_should_set_content_type_responding_with_json(self):
        server.on_any('GET', '/').json(dict(hello='world'))
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.headers['content-type'], 'application/json')

    def test_should_not_change_content_type(self):
        headers = {'content-type': 'text/plain'}
        server.on_any('GET', '/').json(dict(hello='world'), headers=headers)
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.headers['content-type'], 'text/plain')

    def test_should_respond_with_json_and_code_201(self):
        server.on_any('GET', '/').json(dict(foo='bar'), status=201)
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.status_code, 201)


class StatusResponses(ServerTest):
    def test_should_respond_with_status(self):
        server.on_any('GET', '/').status(400)
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.status_code, 400)

    def test_should_respond_with_status_and_headers(self):
        server.on_any('GET', '/').status(400, headers={'x-foo': 'bar'})
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.headers['x-foo'], 'bar')


class AlwaysRequests(ServerTest):
    def test_should_always_respond_to_matching_queries(self):
        server.on_any('OPTIONS', always=True).status(200)
        res = requests.options('http://localhost:8080/some/url', headers={'foo': 'bar'})
        self.assertEqual(res.status_code, 200)
        res = requests.options('http://localhost:8080/some/url', headers={'foo': 'bar'})
        self.assertEqual(res.status_code, 200)

    def test_should_reset_always_rules(self):
        server.on_any('OPTIONS', always=True).status(200)
        server.reset()
        res = requests.options('http://localhost:8080/some/url', headers={'foo': 'bar'})
        self.assertEqual(res.status_code, 500)

    def test_should_always_respond_to_text(self):
        server.on_text('POST', '/text', 'Dude', always=True).status(200)
        res = requests.post('http://localhost:8080/text', data='Dude')
        self.assertEqual(res.status_code, 200)
        res = requests.post('http://localhost:8080/text', data='Dude')
        self.assertEqual(res.status_code, 200)

    def test_should_always_respond_to_json(self):
        server.on_json('POST', '/json', {'name': 'Dude'}, always=True).status(200)
        res = requests.post('http://localhost:8080/json', data='{"name": "Dude"}')
        self.assertEqual(res.status_code, 200)
        res = requests.post('http://localhost:8080/json', data='{"name": "Dude"}')
        self.assertEqual(res.status_code, 200)

    def test_should_always_respond_to_form(self):
        server.on_form('POST', '/form', {'name': ('Dude',)}, always=True).status(200)
        res = requests.post('http://localhost:8080/form', data={'name': 'Dude'})
        self.assertEqual(res.status_code, 200)
        res = requests.post('http://localhost:8080/form', data={'name': 'Dude'})
        self.assertEqual(res.status_code, 200)

    def test_should_always_respond_to_files(self):
        expected_files = {
            'user': {'user': b'Dude'}
        }
        server.on_files(
            'POST', '/upload', files=expected_files, always=True).text('Let\'s go bowling')
        res = requests.post('http://localhost:8080/upload', files=dict(user=b'Dude'))
        self.assertEqual(res.text, 'Let\'s go bowling')
        res = requests.post('http://localhost:8080/upload', files=dict(user=b'Dude'))
        self.assertEqual(res.text, 'Let\'s go bowling')
