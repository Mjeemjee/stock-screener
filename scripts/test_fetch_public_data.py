from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

import requests
from scripts.fetch_public_data import FILES, main


class PublicFetchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)

    def response(self, code=200, payload=None):
        response = Mock(status_code=code, content=b'{"public":true}')
        response.json.return_value = {} if payload is None else payload
        if code >= 400:
            response.raise_for_status.side_effect = requests.HTTPError(str(code))
        return response

    def test_optional_etf_404_does_not_block_publishing_or_fetch_private_files(self):
        get = Mock(side_effect=[self.response() for _ in FILES[:-1]] + [self.response(404)])
        main(self.path, get)
        self.assertFalse((self.path / 'history/etf.json').exists())
        self.assertEqual((self.path / 'tracking.json').read_bytes(), b'{"public":true}')
        urls = [call.args[0] for call in get.call_args_list]
        self.assertFalse(any('positions' in url or 'quotes' in url for url in urls))

    def test_required_payload_404_fails_closed(self):
        with self.assertRaises(requests.HTTPError):
            main(self.path, Mock(return_value=self.response(404)))

    def test_malformed_payload_is_not_published(self):
        with self.assertRaises(ValueError):
            main(self.path, Mock(return_value=self.response(payload=[])))
        self.assertFalse((self.path / 'screener_results.json').exists())
