"""Isolated loopback HTTP tests. No Gemini requests or project services are started."""
import json
import os
from pathlib import Path
import sys
from threading import Thread
import unittest
from unittest.mock import patch
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from basilcare_assistant.http_server import Handler, answer

KEY = 'fixture-internal-key-at-least-24-characters'

class HttpServerTest(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'ASSISTANT_SERVICE_KEY': KEY})
        self.env.start()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)
        self.opener = build_opener(ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.env.stop()

    def post(self, body=b'{"question":"How should I prune basil?"}', key=KEY, path='/ask'):
        request = Request(self.base+path, data=body, headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
        try: response=self.opener.open(request,timeout=3)
        except HTTPError as error: response=error
        with response:
            return response.status, json.loads(response.read()), response.headers

    def test_internal_key_and_path_are_checked_before_model_access(self):
        with patch('basilcare_assistant.http_server.answer') as fake:
            self.assertEqual(self.post(key='wrong')[0],401)
            self.assertEqual(self.post(path='/other')[0],404)
            with patch.dict(os.environ,{'ASSISTANT_SERVICE_KEY':''}):
                self.assertEqual(self.post()[0],401)
            fake.assert_not_called()

    def test_bad_json_empty_question_extra_fields_and_size_are_rejected(self):
        with patch('basilcare_assistant.http_server.answer') as fake:
            for body in (b'{}',b'[]',b'bad',b'{"question":123}',b'{"question":" "}',
                         b'{"question":"basil","token":"extra"}',json.dumps({'question':'x'*2001}).encode()):
                self.assertEqual(self.post(body)[0],400)
            self.assertEqual(self.post(b'x'*16385)[0],413)
            fake.assert_not_called()

    def test_success_and_expected_refusals_are_uncached_without_provider_metadata(self):
        result={'status':'answered','answer':'Pinch tips.','citations':[{'title':'NC State','text':'Pinch tips.',
                'url':'https://plants.ces.ncsu.edu/plants/ocimum-basilicum/'}]}
        with patch('basilcare_assistant.http_server.answer',return_value=result) as fake:
            status,body,headers=self.post()
            self.assertEqual(status,200)
            self.assertEqual(body,result)
            self.assertEqual(headers['Cache-Control'],'no-store')
            fake.assert_called_once_with('How should I prune basil?')

    def test_projection_preserves_generated_answer_without_provider_metadata(self):
        result = {'status':'answered','answer':'markdown','citations':[{'title':'NC State',
                  'url':'https://plants.ces.ncsu.edu/plants/ocimum-basilicum/','text':'Prune tips.'}],
                  'metadata':{'internal':'not-for-the-browser'}}
        with patch('basilcare_assistant.http_server.load_api_key', return_value='fixture'), \
             patch('basilcare_assistant.http_server.GeminiSelector'), \
             patch('basilcare_assistant.http_server.Assistant') as fake:
            fake.return_value.ask.return_value = result
            projected = answer('basil')
            self.assertEqual(set(projected), {'status','answer','citations'})
            self.assertEqual(projected['answer'], 'markdown')

    def test_busy_missing_config_and_provider_errors_fail_without_fallback(self):
        with patch('basilcare_assistant.http_server.SLOTS') as slots:
            slots.acquire.return_value=False
            with patch('basilcare_assistant.http_server.answer') as fake:
                self.assertEqual(self.post()[0],503)
                fake.assert_not_called()
        with patch('basilcare_assistant.http_server.answer',side_effect=ValueError('secret-detail')):
            status,body,_=self.post()
            self.assertEqual(status,503)
            self.assertNotIn('secret-detail',str(body))
        with patch('basilcare_assistant.http_server.answer',return_value={'status':'model_unavailable','answer':'Quota exhausted.','citations':[]}):
            self.assertEqual(self.post()[0],503)

if __name__=='__main__': unittest.main()
