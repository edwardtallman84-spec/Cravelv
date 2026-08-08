import json
import mimetypes
import uuid
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ProviderError(RuntimeError):
    pass


def _read(request, timeout=40):
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        try:
            message = json.loads(detail).get("error", {}).get("message") or json.loads(detail).get("error_description")
        except Exception:
            message = None
        raise ProviderError(message or f"Provider request failed with status {exc.code}.") from exc


def get_json(url, params=None, headers=None, timeout=40):
    if params:
        url = f"{url}?{urlencode(params)}"
    return _read(Request(url, headers=headers or {}), timeout)


def post_form(url, data, timeout=40):
    body = urlencode(data).encode()
    return _read(Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST"), timeout)


def post_multipart(url, fields, filename, content_type, content, timeout=60):
    boundary = f"----CraveLV{uuid.uuid4().hex}"
    pieces = []
    for name, value in fields.items():
        pieces.extend([f"--{boundary}\r\n".encode(), f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(), str(value).encode(), b"\r\n"])
    pieces.extend([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="source"; filename="{filename}"\r\n'.encode(),
        f"Content-Type: {content_type or mimetypes.guess_type(filename)[0] or 'application/octet-stream'}\r\n\r\n".encode(),
        content,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    request = Request(url, data=b"".join(pieces), headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST")
    return _read(request, timeout)

