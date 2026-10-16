import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from googleapiclient.errors import HttpError

from renderer.gdocs import auth, config


def http_error(status):
    return HttpError(mock.Mock(status=status, reason="x"), b"{}")


class ConfigTest(unittest.TestCase):
    def load(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text(text, encoding="utf-8")
            return config.load_config(path)

    VALID = "targetFolderId: a\ntemplateId: b\nspreadsheetId: c\n"

    def test_valid(self):
        self.assertEqual(self.load(self.VALID)["templateId"], "b")

    def test_missing_empty_null(self):
        for key in ("templateId", "spreadsheetId", "targetFolderId"):
            lines = self.VALID.splitlines()
            others = "\n".join(l for l in lines if not l.startswith(key))
            for variant in ("", f"{key}:", f"{key}: ''", f"{key}: null"):
                with self.subTest(key=key, variant=variant):
                    with self.assertRaises(config.ConfigError) as ctx:
                        self.load(others + "\n" + variant + "\n")
                    self.assertIn(key, str(ctx.exception))


class AuthTest(unittest.TestCase):
    def test_old_token_triggers_consent(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            token = tmp / "token.json"
            token.write_text(
                json.dumps({"scopes": ["https://www.googleapis.com/auth/drive.file"]})
            )
            secrets = tmp / "credentials.json"
            secrets.write_text("{}")
            new_credentials = mock.Mock(valid=True)
            new_credentials.to_json.return_value = '{"new": true}'
            flow = mock.Mock()
            flow.run_local_server.return_value = new_credentials
            with mock.patch.object(auth, "TOKEN_PATH", token), mock.patch.object(
                auth, "CREDENTIALS_PATH", secrets
            ), mock.patch.object(auth, "OUTPUT_DIR", tmp), mock.patch.object(
                auth.InstalledAppFlow, "from_client_secrets_file", return_value=flow
            ) as factory:
                result = auth.authenticate()
            self.assertIs(result, new_credentials)
            factory.assert_called_once_with(secrets, auth.SCOPES)
            self.assertEqual(token.read_text(), '{"new": true}')


class ExecuteTest(unittest.TestCase):
    def run_with(self, errors, result="ok"):
        request = mock.Mock()
        request.execute.side_effect = errors + [result]
        with mock.patch.object(auth.time, "sleep") as sleep:
            try:
                return auth.execute(request), request, sleep
            except HttpError as error:
                return error, request, sleep

    def test_retries_429_and_503(self):
        value, request, sleep = self.run_with([http_error(429), http_error(503)])
        self.assertEqual(value, "ok")
        self.assertEqual(request.execute.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_stops_after_five(self):
        value, request, _ = self.run_with([http_error(503)] * 6)
        self.assertIsInstance(value, HttpError)
        self.assertEqual(request.execute.call_count, 5)

    def test_no_retry_on_404(self):
        value, request, _ = self.run_with([http_error(404)])
        self.assertIsInstance(value, HttpError)
        self.assertEqual(request.execute.call_count, 1)



class BuildServicesTest(unittest.TestCase):
    def test_clients_use_the_long_http_timeout(self):
        with mock.patch.object(auth, "build") as build:
            auth.build_services(mock.Mock())
        self.assertEqual(build.call_count, 3)
        for call in build.call_args_list:
            self.assertEqual(call.kwargs["http"].http.timeout, auth.HTTP_TIMEOUT_SECONDS)


if __name__ == "__main__":
    unittest.main()
