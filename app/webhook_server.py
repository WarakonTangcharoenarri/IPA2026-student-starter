"""Part 4 student implementation."""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

from app.integration import process_request
from app.webex_client import WebexClient


_MAX_EVENT_BYTES = 1_000_000
_LOG = logging.getLogger(__name__)


class WebexEventHandler:
    def __init__(self, client, bot_person_id, processor=None):
        self.client = client
        self.bot_person_id = bot_person_id
        self.processor = processor or process_request

    def handle_event(self, event):
        if not isinstance(event, dict):
            return None
        data = event.get("data")
        if (
            event.get("resource") != "messages"
            or event.get("event") != "created"
            or not isinstance(data, dict)
            or not isinstance(data.get("id"), str)
            or not data["id"]
        ):
            return None
        if (
            isinstance(self.bot_person_id, str)
            and data.get("personId") == self.bot_person_id
        ):
            return None

        message = self.client.get_message(data["id"])
        if not isinstance(message, dict):
            return None
        if (
            isinstance(self.bot_person_id, str)
            and message.get("personId") == self.bot_person_id
        ):
            return None

        room_id = message.get("roomId")
        mentioned_people = message.get("mentionedPeople")
        if not isinstance(room_id, str) or not room_id:
            return None

        files = message.get("files")
        if files is None:
            files = []
        if not isinstance(files, list):
            return None

        _LOG.info("Processing Webex message attachment_count=%d", len(files))
        if len(files) > 1:
            result = {
                "status": "error",
                "result": "multiple_attachments",
            }
        elif not files:
            result = self.processor(
                mentioned_people,
                None,
                self.bot_person_id,
            )
        else:
            file_url = files[0]
            if not isinstance(file_url, str) or not file_url:
                return None
            content = self.client.download_file(file_url)
            with TemporaryDirectory(prefix="ipa2026-webhook-") as directory:
                attachment_path = Path(directory) / "request.yaml"
                with open(attachment_path, "wb") as attachment_file:
                    attachment_file.write(content)
                result = self.processor(
                    mentioned_people,
                    attachment_path,
                    self.bot_person_id,
                )

        if not isinstance(result, dict):
            raise TypeError("Request processor must return a response dictionary")
        if result.get("status") == "error":
            _LOG.warning(
                "Webex message processing returned error result=%s",
                result.get("result"),
            )
        self.client.send_message(
            room_id,
            json.dumps(result),
        )
        _LOG.info("Webex message processing and reply completed")
        return result

def make_http_handler(submit_event):
    class WebhookHTTPHandler(BaseHTTPRequestHandler):
        def _send_json(self, status_code, payload):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path != "/health":
                self._send_json(
                    404,
                    {"status": "error", "result": "not_found"},
                )
                return
            self._send_json(
                200,
                {"status": "ok", "result": "healthy"},
            )

        def do_POST(self):
            if self.path != "/webhook":
                self._send_json(
                    404,
                    {"status": "error", "result": "not_found"},
                )
                return

            content_length = self.headers.get("Content-Length")
            try:
                length = int(content_length) if content_length is not None else 0
            except ValueError:
                length = 0
            if length < 1 or length > _MAX_EVENT_BYTES:
                self._send_json(
                    400,
                    {"status": "error", "result": "invalid_event"},
                )
                return

            body = self.rfile.read(length)
            if len(body) != length:
                self._send_json(
                    400,
                    {"status": "error", "result": "invalid_event"},
                )
                return
            try:
                event = json.loads(body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send_json(
                    400,
                    {"status": "error", "result": "invalid_event"},
                )
                return
            if not isinstance(event, dict):
                self._send_json(
                    400,
                    {"status": "error", "result": "invalid_event"},
                )
                return

            submit_event(event)
            self._send_json(
                200,
                {"status": "ok", "result": "accepted"},
            )

        def log_message(self, format_string, *args):
            _LOG.info("Webhook HTTP: " + format_string, *args)

    return WebhookHTTPHandler

def main():
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    client = WebexClient()
    identity = client.get_me()
    bot_person_id = identity.get("id") if isinstance(identity, dict) else None
    if not isinstance(bot_person_id, str) or not bot_person_id:
        raise RuntimeError("Webex /people/me did not return a person ID")

    event_handler = WebexEventHandler(client, bot_person_id)

    def process_event(event):
        try:
            event_handler.handle_event(event)
        except Exception:
            _LOG.exception("Failed to process Webex event")

    executor = ThreadPoolExecutor(
        max_workers=1,
        thread_name_prefix="webex-event",
    )
    host = os.environ.get("WEBHOOK_HOST", "0.0.0.0")
    port = int(os.environ.get("WEBHOOK_PORT", "8000"))
    server = ThreadingHTTPServer(
        (host, port),
        make_http_handler(
            lambda event: executor.submit(process_event, event)
        ),
    )
    _LOG.info("Webhook server listening on %s:%s", host, port)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        executor.shutdown(wait=True)

if __name__ == "__main__":
    main()
