import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest import mock

import requests
from requests.exceptions import HTTPError, Timeout

from tap_jira.http import (Client, JiraUnauthorizedError,
                           should_giveup_on_refresh, TOKEN_EXPIRY_MARGIN_SECONDS)


def make_cloud_client():
    """Build a cloud (OAuth) Client without doing any network I/O at init."""
    config = {
        "oauth_client_id": "cid",
        "oauth_client_secret": "secret",
        "refresh_token": "rt0",
        "access_token": "at0",
        "cloud_id": "abc123",
    }
    with mock.patch.object(Client, "refresh_credentials"), \
         mock.patch.object(Client, "test_credentials_are_authorized"):
        return Client(config)


def make_basic_client():
    with mock.patch.object(Client, "test_basic_credentials_are_authorized"):
        return Client({"base_url": "https://jira.example.com"})


def mock_response(status_code, payload):
    resp = mock.Mock()
    resp.status_code = status_code
    resp.json.return_value = payload
    resp.text = json.dumps(payload)
    return resp


class TestGiveupPolicy(unittest.TestCase):
    """Refresh should retry transient failures but give up on terminal 4xx."""

    def _http_error(self, status_code):
        resp = requests.Response()
        resp.status_code = status_code
        return HTTPError(response=resp)

    def test_giveup_on_4xx(self):
        # invalid_grant (revoked/expired refresh token) => don't retry
        self.assertTrue(should_giveup_on_refresh(self._http_error(400)))
        self.assertTrue(should_giveup_on_refresh(self._http_error(403)))

    def test_retry_on_5xx(self):
        self.assertFalse(should_giveup_on_refresh(self._http_error(503)))

    def test_retry_on_network_error(self):
        # ConnectionError/Timeout carry no response => retry
        self.assertFalse(should_giveup_on_refresh(Timeout()))


class TestEnsureAccessToken(unittest.TestCase):
    def test_refreshes_when_missing_or_expired(self):
        client = make_cloud_client()
        with mock.patch.object(client, "refresh_credentials") as mref:
            client.token_expires_at = None            # never fetched
            client._ensure_access_token()
            self.assertEqual(1, mref.call_count)

            client.token_expires_at = datetime.now() - timedelta(seconds=1)  # expired
            client._ensure_access_token()
            self.assertEqual(2, mref.call_count)

    def test_skips_when_token_fresh(self):
        client = make_cloud_client()
        client.token_expires_at = datetime.now() + timedelta(hours=1)
        with mock.patch.object(client, "refresh_credentials") as mref:
            client._ensure_access_token()
            self.assertEqual(0, mref.call_count)

    def test_noop_for_basic_auth(self):
        client = make_basic_client()
        # No token_expires_at attribute exists for basic auth; must not blow up
        with mock.patch.object(client, "refresh_credentials") as mref:
            client._ensure_access_token()
            self.assertEqual(0, mref.call_count)


class TestRefreshCredentials(unittest.TestCase):
    def test_rotates_tokens_and_persists_atomically(self):
        client = make_cloud_client()
        work_dir = tempfile.mkdtemp()
        cfg_path = os.path.join(work_dir, "config.json")
        with open(cfg_path, "w") as fh:
            json.dump({"oauth_client_id": "cid",
                       "refresh_token": "rt0",
                       "access_token": "at0"}, fh)
        client.config_path = cfg_path

        resp = mock_response(200, {"access_token": "AT1",
                                   "refresh_token": "RT1",
                                   "expires_in": 3600})

        prev_cwd = os.getcwd()
        os.chdir(work_dir)
        try:
            with mock.patch.object(client.session, "post", return_value=resp):
                client.refresh_credentials()
        finally:
            os.chdir(prev_cwd)

        # In-memory tokens rotated
        self.assertEqual("AT1", client.access_token)
        self.assertEqual("RT1", client.refresh_token)

        # Persisted to the real config file (the rotated refresh token must survive)
        written = json.load(open(cfg_path))
        self.assertEqual("RT1", written["refresh_token"])
        self.assertEqual("AT1", written["access_token"])

        # Expiry derived from expires_in minus the safety margin
        remaining = (client.token_expires_at - datetime.now()).total_seconds()
        self.assertAlmostEqual(3600 - TOKEN_EXPIRY_MARGIN_SECONDS, remaining, delta=30)

        # The old debug credential dump must NOT be recreated
        self.assertFalse(os.path.exists(os.path.join(work_dir, "local_storage.json")))
        # No temp files left behind
        self.assertEqual(["config.json"], os.listdir(work_dir))

    def test_original_config_untouched_when_write_fails(self):
        client = make_cloud_client()
        work_dir = tempfile.mkdtemp()
        cfg_path = os.path.join(work_dir, "config.json")
        original = {"oauth_client_id": "cid", "refresh_token": "rt0", "access_token": "at0"}
        with open(cfg_path, "w") as fh:
            json.dump(original, fh)
        client.config_path = cfg_path

        resp = mock_response(200, {"access_token": "AT1",
                                   "refresh_token": "RT1",
                                   "expires_in": 3600})
        with mock.patch.object(client.session, "post", return_value=resp), \
             mock.patch("os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                client.refresh_credentials()

        # Original config still intact, no temp files left
        self.assertEqual(original, json.load(open(cfg_path)))
        self.assertEqual(["config.json"], os.listdir(work_dir))


class TestReactive401Retry(unittest.TestCase):
    def test_cloud_refreshes_and_retries_once_on_401(self):
        client = make_cloud_client()
        client.token_expires_at = datetime.now() + timedelta(hours=1)  # fresh
        unauth = mock_response(401, {"errorMessages": ["Unauthorized"]})
        ok = mock_response(200, {"ok": True})

        with mock.patch.object(client, "_timed_send", side_effect=[unauth, ok]) as msend, \
             mock.patch.object(client, "refresh_credentials") as mref:
            result = client.request("test", "GET", "/rest/api/2/x")

        self.assertEqual({"ok": True}, result)
        self.assertEqual(1, mref.call_count)   # refreshed once
        self.assertEqual(2, msend.call_count)  # original + one retry

    def test_basic_auth_does_not_retry_on_401(self):
        client = make_basic_client()
        unauth = mock_response(401, {"errorMessages": ["Unauthorized"]})
        with mock.patch.object(client, "_timed_send", return_value=unauth):
            with self.assertRaises(JiraUnauthorizedError):
                client.request("test", "GET", "/rest/api/2/x")


if __name__ == "__main__":
    unittest.main()
