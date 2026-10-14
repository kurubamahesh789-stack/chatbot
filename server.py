import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


PORT = int(os.environ.get("PORT", "3000"))
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
PUBLIC_DIR = Path(__file__).parent / "public"
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}


class ChatHandler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        request_path = urlsplit(self.path).path
        if request_path == "/api/models":
            try:
                with urlopen(f"{OLLAMA_HOST}/api/tags", timeout=10) as response:
                    self.send_response(response.status)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(response.read())
            except HTTPError as error:
                try:
                    details = json.loads(error.read())
                    message = details.get("error", "Could not load Ollama models.")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    message = "Could not load Ollama models."
                self.send_json(error.code, {"error": message})
            except (URLError, TimeoutError, OSError) as error:
                self.send_json(
                    502,
                    {"error": f"Cannot connect to Ollama at {OLLAMA_HOST}: {error}"},
                )
            return

        static_file = STATIC_FILES.get(request_path)
        if static_file:
            file_name, content_type = static_file
            try:
                body = (PUBLIC_DIR / file_name).read_bytes()
            except OSError:
                self.send_json(500, {"error": "Could not load the chatbot."})
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(404, "Not found")

    def do_POST(self):
        if urlsplit(self.path).path != "/api/chat":
            self.send_error(404, "Not found")
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0:
                raise ValueError("A request body is required.")
            if content_length > 1024 * 1024:
                self.send_json(413, {"error": "Request body is too large."})
                return
            payload = json.loads(self.rfile.read(content_length))
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            self.send_json(400, {"error": "Invalid JSON request."})
            return

        messages = payload.get("messages") if isinstance(payload, dict) else None
        valid_messages = (
            isinstance(messages, list)
            and len(messages) > 0
            and all(
                isinstance(message, dict)
                and message.get("role") in ("system", "user", "assistant")
                and isinstance(message.get("content"), str)
                for message in messages
            )
        )
        model = payload.get("model") if isinstance(payload, dict) else None
        if not isinstance(model, str) or not valid_messages:
            self.send_json(
                400,
                {"error": "A model and a non-empty list of valid messages are required."},
            )
            return

        request_body = json.dumps(
            {"model": model, "messages": messages, "stream": True}
        ).encode("utf-8")
        request = Request(
            f"{OLLAMA_HOST}/api/chat",
            data=request_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        response_started = False
        try:
            with urlopen(request, timeout=300) as response:
                self.send_response(response.status)
                self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
                self.send_header("Cache-Control", "no-cache, no-transform")
                self.send_header("Connection", "close")
                self.end_headers()
                response_started = True
                self.close_connection = True
                while chunk := response.read(65536):
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except HTTPError as error:
            try:
                details = json.loads(error.read())
                message = details.get("error", "Ollama could not generate a reply.")
            except (json.JSONDecodeError, UnicodeDecodeError):
                message = "Ollama could not generate a reply."
            self.send_json(error.code, {"error": message})
        except (URLError, TimeoutError, OSError) as error:
            if not response_started:
                self.send_json(502, {"error": f"Could not reach Ollama: {error}"})

    def log_message(self, format, *args):
        print(f"{self.log_date_time_string()} - {format % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), ChatHandler)
    print(f"Ollama Chat is ready at http://localhost:{PORT}")
    print(f"Using Ollama at {OLLAMA_HOST}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Ollama Chat.")
    finally:
        server.server_close()
