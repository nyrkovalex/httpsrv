import json
import unittest
import requests
from httpsrv import listen, PendingRequestsLeftException

server = listen(8080).start()

class ServerTest(unittest.TestCase):

    def tearDown(self):
        server.reset()

    def test_should_launch_http_server(self):
        server.on_get('/').respond('hello')
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.text, 'hello')

    def test_should_serve_multiple_responses_to_same_url(self):
        server.on_get('/').respond('Hello')
        server.on_get('/').respond('Goodbye')
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.text, 'Hello')
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.text, 'Goodbye')

    def test_should_respond_500_if_no_rule_matches(self):
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.status_code, 500)

    def test_should_match_by_query_parameters(self):
        server.on_get('/user?name=John').respond('John Doe')
        res = requests.get('http://localhost:8080/user?name=John')
        self.assertEqual(res.text, 'John Doe')

    def test_should_set_header(self):
        headers = {'x-header': 'some'}
        server.on_get('/').respond('hello', headers=headers)
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.headers['x-header'], 'some')

    def test_should_respond_with_json(self):
        expected = dict(hello='world')
        server.on_get('/').json(expected)
        res = requests.get('http://localhost:8080')
        self.assertEqual(json.loads(res.text), expected)

    def test_should_set_content_type_responding_with_json(self):
        server.on_get('/').json(dict(hello='world'))
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.headers['content-type'], 'application/json')

    def test_should_not_change_content_type(self):
        headers = {'content-type': 'text/plain'}
        server.on_get('/').json(dict(hello='world'), headers)
        res = requests.get('http://localhost:8080')
        self.assertEqual(res.headers['content-type'], 'text/plain')

    def test_should_raise_if_pending_requetss_left(self):
        server.on_get('/').respond('hello')
        with self.assertRaises(PendingRequestsLeftException):
            server.assert_no_pending()

    def test_should_not_raise_anything(self):
        server.assert_no_pending()

    def test_should_respond_to_post(self):
        server.on_post('/').respond('hello')
        res = requests.post('http://localhost:8080')
        self.assertEqual(res.text, 'hello')

    def test_should_expect_post_body(self):
        server.on_post('/', data='foo=bar').respond('hello')
        res = requests.post('http://localhost:8080', data='foo=bar')
        self.assertEqual(res.text, 'hello')



class ServerRunningTest:
    def test_should_launch_http_server_as_contextmanager(self):
        second_server = listen(8081).on_get('/').respond('Hello')
        with second_server.run():
            res = requests.get('http://localhost:8081')
            self.assertEqual(res.text, 'Hello')
        self.assertFalse(server.running)

    def test_should_handle_exception_as_contextmanager(self):
        server.on_get('/').respond('Hello')
        try:
            with server.run():
                raise Exception('bad thing happened')
        except:
            self.assertFalse(server.running)

    def test_should_reset_server_state(self):
        second_server = listen(8081).on_get('/').respond('Hello')
        second_server.reset()
        with second_server.run():
            res = requests.get('http://localhost:8081')
            self.assertEqual(res.status_code, 500)
