"""
Application Layer Implementation
Level 3: Application Protocols

This module implements:
- Simple HTTP-like protocol
- Request-response pattern
- File transfer protocol (FTP-like)
- Echo service

HTTP-like Protocol:
Request:  METHOD /path HTTP/1.0\r\nHeaders\r\n\r\nBody
Response: HTTP/1.0 STATUS Message\r\nHeaders\r\n\r\nBody
"""

from typing import Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
import json
import time

from network_layer import Host, StarTopology
from transport_layer import ReliableTransport, TransportConnection


# =============================================================================
# HTTP Request/Response
# =============================================================================

@dataclass
class HTTPRequest:
    """HTTP-like request."""
    method: str
    path: str
    version: str = "HTTP/1.0"
    headers: Dict[str, str] = field(default_factory=dict)
    body: str = ""

    def to_bytes(self) -> bytes:
        """Serialize request to bytes."""
        # Request line
        lines = [f"{self.method} {self.path} {self.version}"]

        # Headers
        for key, value in self.headers.items():
            lines.append(f"{key}: {value}")

        # Add content length if body exists
        if self.body:
            lines.append(f"Content-Length: {len(self.body)}")

        # Empty line before body
        lines.append("")
        lines.append(self.body)

        return "\r\n".join(lines).encode('utf-8')

    @classmethod
    def from_bytes(cls, data: bytes) -> 'HTTPRequest':
        """Parse request from bytes."""
        text = data.decode('utf-8', errors='replace')
        lines = text.split('\r\n')

        # Parse request line
        if not lines:
            raise ValueError("Empty request")

        parts = lines[0].split(' ', 2)
        if len(parts) < 2:
            raise ValueError("Invalid request line")

        method = parts[0]
        path = parts[1]
        version = parts[2] if len(parts) > 2 else "HTTP/1.0"

        # Parse headers
        headers = {}
        body_start = 1
        for i, line in enumerate(lines[1:], 1):
            if line == "":
                body_start = i + 1
                break
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip()] = value.strip()

        # Parse body
        body = '\r\n'.join(lines[body_start:]) if body_start < len(lines) else ""

        return cls(method=method, path=path, version=version,
                  headers=headers, body=body)

    def __repr__(self):
        return f"HTTPRequest({self.method} {self.path})"


@dataclass
class HTTPResponse:
    """HTTP-like response."""
    status_code: int
    status_message: str
    version: str = "HTTP/1.0"
    headers: Dict[str, str] = field(default_factory=dict)
    body: str = ""

    def to_bytes(self) -> bytes:
        """Serialize response to bytes."""
        # Status line
        lines = [f"{self.version} {self.status_code} {self.status_message}"]

        # Headers
        for key, value in self.headers.items():
            lines.append(f"{key}: {value}")

        # Add content length
        if self.body:
            lines.append(f"Content-Length: {len(self.body)}")

        # Content type
        if 'Content-Type' not in self.headers:
            lines.append("Content-Type: text/plain")

        # Empty line before body
        lines.append("")
        lines.append(self.body)

        return "\r\n".join(lines).encode('utf-8')

    @classmethod
    def from_bytes(cls, data: bytes) -> 'HTTPResponse':
        """Parse response from bytes."""
        text = data.decode('utf-8', errors='replace')
        lines = text.split('\r\n')

        # Parse status line
        if not lines:
            raise ValueError("Empty response")

        parts = lines[0].split(' ', 2)
        if len(parts) < 3:
            raise ValueError("Invalid status line")

        version = parts[0]
        status_code = int(parts[1])
        status_message = parts[2]

        # Parse headers
        headers = {}
        body_start = 1
        for i, line in enumerate(lines[1:], 1):
            if line == "":
                body_start = i + 1
                break
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip()] = value.strip()

        # Parse body
        body = '\r\n'.join(lines[body_start:]) if body_start < len(lines) else ""

        return cls(status_code=status_code, status_message=status_message,
                  version=version, headers=headers, body=body)

    @classmethod
    def ok(cls, body: str = "", content_type: str = "text/plain") -> 'HTTPResponse':
        """Create 200 OK response."""
        return cls(200, "OK", headers={"Content-Type": content_type}, body=body)

    @classmethod
    def not_found(cls, message: str = "Not Found") -> 'HTTPResponse':
        """Create 404 Not Found response."""
        return cls(404, "Not Found", body=message)

    @classmethod
    def error(cls, code: int, message: str) -> 'HTTPResponse':
        """Create error response."""
        return cls(code, message, body=message)

    def __repr__(self):
        return f"HTTPResponse({self.status_code} {self.status_message})"


# =============================================================================
# HTTP Server
# =============================================================================

class HTTPServer:
    """
    Simple HTTP-like server.

    Handles requests and routes to registered handlers.
    """

    def __init__(self, host: Host):
        """
        Initialize HTTP server.

        Args:
            host: Network layer host
        """
        self.host = host
        self.transport = ReliableTransport(host)

        # Route handlers: path -> handler function
        self.routes: Dict[str, Callable[[HTTPRequest], HTTPResponse]] = {}

        # Static files
        self.static_files: Dict[str, str] = {}

        # Statistics
        self.stats = {
            'requests_received': 0,
            'responses_sent': 0,
            'errors': 0
        }

        # Install receive handler
        self.transport.on_receive = self._handle_receive

    def route(self, path: str):
        """
        Decorator to register route handler.

        Usage:
            @server.route("/hello")
            def hello(request):
                return HTTPResponse.ok("Hello!")
        """
        def decorator(handler: Callable[[HTTPRequest], HTTPResponse]):
            self.routes[path] = handler
            return handler
        return decorator

    def register_handler(self, path: str, handler: Callable[[HTTPRequest], HTTPResponse]):
        """Register a route handler."""
        self.routes[path] = handler

    def add_static_file(self, path: str, content: str):
        """Add a static file."""
        self.static_files[path] = content

    def _handle_receive(self, data: bytes, src_mac: str):
        """Handle received data."""
        self.stats['requests_received'] += 1

        try:
            # Parse request
            request = HTTPRequest.from_bytes(data)

            # Find handler
            response = self._process_request(request)

            # Send response
            self.transport.send(src_mac, response.to_bytes())
            self.stats['responses_sent'] += 1

        except Exception as e:
            self.stats['errors'] += 1
            # Send error response
            error_response = HTTPResponse.error(500, str(e))
            self.transport.send(src_mac, error_response.to_bytes())

    def _process_request(self, request: HTTPRequest) -> HTTPResponse:
        """Process request and return response."""
        path = request.path

        # Check routes
        if path in self.routes:
            return self.routes[path](request)

        # Check static files
        if path in self.static_files:
            return HTTPResponse.ok(self.static_files[path])

        # Not found
        return HTTPResponse.not_found(f"Path '{path}' not found")

    def get_stats(self) -> dict:
        """Get server statistics."""
        return self.stats.copy()


# =============================================================================
# HTTP Client
# =============================================================================

class HTTPClient:
    """
    Simple HTTP-like client.

    Makes requests to HTTP servers.
    """

    def __init__(self, host: Host):
        """
        Initialize HTTP client.

        Args:
            host: Network layer host
        """
        self.host = host
        self.transport = ReliableTransport(host)
        self.pending_response: Optional[HTTPResponse] = None

        # Install receive handler
        self.transport.on_receive = self._handle_receive

        # Statistics
        self.stats = {
            'requests_sent': 0,
            'responses_received': 0
        }

    def _handle_receive(self, data: bytes, src_mac: str):
        """Handle received response."""
        try:
            self.pending_response = HTTPResponse.from_bytes(data)
            self.stats['responses_received'] += 1
        except Exception:
            pass

    def get(self, dst_mac: str, path: str, headers: Dict[str, str] = None) -> Optional[HTTPResponse]:
        """
        Send GET request.

        Args:
            dst_mac: Server MAC address
            path: Request path
            headers: Optional headers

        Returns:
            Response or None if failed
        """
        request = HTTPRequest(
            method="GET",
            path=path,
            headers=headers or {}
        )
        return self._send_request(dst_mac, request)

    def post(self, dst_mac: str, path: str, body: str,
             headers: Dict[str, str] = None) -> Optional[HTTPResponse]:
        """
        Send POST request.

        Args:
            dst_mac: Server MAC address
            path: Request path
            body: Request body
            headers: Optional headers

        Returns:
            Response or None if failed
        """
        request = HTTPRequest(
            method="POST",
            path=path,
            headers=headers or {},
            body=body
        )
        return self._send_request(dst_mac, request)

    def _send_request(self, dst_mac: str, request: HTTPRequest) -> Optional[HTTPResponse]:
        """Send request and wait for response."""
        self.pending_response = None
        self.stats['requests_sent'] += 1

        # Send request
        success = self.transport.send(dst_mac, request.to_bytes())
        if not success:
            return None

        # Wait for response (simple polling)
        # In practice, we'd process frames here
        frame = self.host.get_received(timeout=1.0)
        if frame:
            self._handle_receive(frame.payload, str(frame.src_mac))

        return self.pending_response

    def get_stats(self) -> dict:
        """Get client statistics."""
        return self.stats.copy()


# =============================================================================
# File Transfer Service
# =============================================================================

class FileServer:
    """
    Simple file transfer server.

    Supports:
    - LIST: List available files
    - GET <filename>: Download file
    - PUT <filename>: Upload file
    """

    def __init__(self, host: Host):
        """Initialize file server."""
        self.host = host
        self.transport = ReliableTransport(host)
        self.files: Dict[str, bytes] = {}

        self.transport.on_receive = self._handle_receive

    def add_file(self, name: str, content: bytes):
        """Add a file to the server."""
        self.files[name] = content

    def _handle_receive(self, data: bytes, src_mac: str):
        """Handle file transfer commands."""
        try:
            text = data.decode('utf-8')
            parts = text.split(' ', 1)
            command = parts[0].upper()

            if command == "LIST":
                response = "\n".join(self.files.keys()) or "(empty)"
            elif command == "GET":
                filename = parts[1] if len(parts) > 1 else ""
                if filename in self.files:
                    response = self.files[filename].decode('utf-8', errors='replace')
                else:
                    response = f"ERROR: File '{filename}' not found"
            elif command == "PUT":
                # Format: PUT filename\ncontent
                if len(parts) > 1:
                    file_parts = parts[1].split('\n', 1)
                    filename = file_parts[0].strip()
                    content = file_parts[1] if len(file_parts) > 1 else ""
                    self.files[filename] = content.encode('utf-8')
                    response = f"OK: Saved '{filename}'"
                else:
                    response = "ERROR: Invalid PUT format"
            else:
                response = f"ERROR: Unknown command '{command}'"

            self.transport.send(src_mac, response.encode('utf-8'))

        except Exception as e:
            self.transport.send(src_mac, f"ERROR: {e}".encode('utf-8'))


class FileClient:
    """File transfer client."""

    def __init__(self, host: Host):
        """Initialize file client."""
        self.host = host
        self.transport = ReliableTransport(host)
        self.last_response: Optional[str] = None
        self.transport.on_receive = self._handle_receive

    def _handle_receive(self, data: bytes, src_mac: str):
        """Handle response."""
        self.last_response = data.decode('utf-8', errors='replace')

    def _send_command(self, server_mac: str, command: str) -> Optional[str]:
        """Send command and get response."""
        self.last_response = None
        self.transport.send(server_mac, command.encode('utf-8'))

        # Wait for response
        frame = self.host.get_received(timeout=1.0)
        if frame:
            self._handle_receive(frame.payload, str(frame.src_mac))

        return self.last_response

    def list_files(self, server_mac: str) -> List[str]:
        """List files on server."""
        response = self._send_command(server_mac, "LIST")
        if response and response != "(empty)":
            return response.split('\n')
        return []

    def get_file(self, server_mac: str, filename: str) -> Optional[str]:
        """Download file from server."""
        return self._send_command(server_mac, f"GET {filename}")

    def put_file(self, server_mac: str, filename: str, content: str) -> bool:
        """Upload file to server."""
        response = self._send_command(server_mac, f"PUT {filename}\n{content}")
        return response and response.startswith("OK")


# =============================================================================
# Echo Service
# =============================================================================

class EchoServer:
    """Simple echo server - returns whatever is sent to it."""

    def __init__(self, host: Host):
        """Initialize echo server."""
        self.host = host
        self.transport = ReliableTransport(host)
        self.transport.on_receive = self._handle_receive

    def _handle_receive(self, data: bytes, src_mac: str):
        """Echo back received data."""
        # Prepend "ECHO: " to response
        response = b"ECHO: " + data
        self.transport.send(src_mac, response)


# =============================================================================
# JSON API Service
# =============================================================================

class JSONAPIServer:
    """
    JSON-based API server.

    Handles JSON requests and returns JSON responses.
    """

    def __init__(self, host: Host):
        """Initialize JSON API server."""
        self.host = host
        self.transport = ReliableTransport(host)
        self.endpoints: Dict[str, Callable[[dict], dict]] = {}
        self.data_store: Dict[str, any] = {}

        self.transport.on_receive = self._handle_receive

    def endpoint(self, name: str):
        """Decorator to register API endpoint."""
        def decorator(handler: Callable[[dict], dict]):
            self.endpoints[name] = handler
            return handler
        return decorator

    def _handle_receive(self, data: bytes, src_mac: str):
        """Handle JSON request."""
        try:
            request = json.loads(data.decode('utf-8'))
            endpoint = request.get('endpoint', '')
            params = request.get('params', {})

            if endpoint in self.endpoints:
                result = self.endpoints[endpoint](params)
                response = {'status': 'ok', 'result': result}
            else:
                response = {'status': 'error', 'message': f'Unknown endpoint: {endpoint}'}

        except json.JSONDecodeError:
            response = {'status': 'error', 'message': 'Invalid JSON'}
        except Exception as e:
            response = {'status': 'error', 'message': str(e)}

        self.transport.send(src_mac, json.dumps(response).encode('utf-8'))


class JSONAPIClient:
    """JSON API client."""

    def __init__(self, host: Host):
        """Initialize JSON API client."""
        self.host = host
        self.transport = ReliableTransport(host)
        self.last_response: Optional[dict] = None
        self.transport.on_receive = self._handle_receive

    def _handle_receive(self, data: bytes, src_mac: str):
        """Handle JSON response."""
        try:
            self.last_response = json.loads(data.decode('utf-8'))
        except:
            self.last_response = None

    def call(self, server_mac: str, endpoint: str, params: dict = None) -> Optional[dict]:
        """Call API endpoint."""
        self.last_response = None

        request = {
            'endpoint': endpoint,
            'params': params or {}
        }
        self.transport.send(server_mac, json.dumps(request).encode('utf-8'))

        # Wait for response
        frame = self.host.get_received(timeout=1.0)
        if frame:
            self._handle_receive(frame.payload, str(frame.src_mac))

        return self.last_response


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Application Layer Demo - Level 3: Protocols")
    print("=" * 70)

    # Test HTTP Request/Response
    print("\n1. HTTP Request/Response Serialization:")

    # Create request
    request = HTTPRequest(
        method="GET",
        path="/hello",
        headers={"User-Agent": "TestClient/1.0"}
    )
    print(f"   Request: {request}")

    req_bytes = request.to_bytes()
    print(f"   Serialized ({len(req_bytes)} bytes):")
    print(f"   {req_bytes[:50]}...")

    # Parse back
    parsed_req = HTTPRequest.from_bytes(req_bytes)
    print(f"   Parsed: {parsed_req.method} {parsed_req.path}")

    # Create response
    response = HTTPResponse.ok("Hello, World!")
    print(f"\n   Response: {response}")

    resp_bytes = response.to_bytes()
    parsed_resp = HTTPResponse.from_bytes(resp_bytes)
    print(f"   Parsed: {parsed_resp.status_code} {parsed_resp.status_message}")
    print(f"   Body: {parsed_resp.body}")

    # Test HTTP Server/Client
    print("\n2. HTTP Server/Client Test:")
    topology = StarTopology(num_hosts=2)
    server_host = topology.get_host("00:00:00:00:00:01")
    client_host = topology.get_host("00:00:00:00:00:02")

    # Create server
    server = HTTPServer(server_host)

    @server.route("/hello")
    def hello_handler(req):
        return HTTPResponse.ok("Hello from server!")

    @server.route("/time")
    def time_handler(req):
        return HTTPResponse.ok(f"Server time: {time.time():.2f}")

    @server.route("/echo")
    def echo_handler(req):
        return HTTPResponse.ok(f"You said: {req.body}")

    # Add static file
    server.add_static_file("/index.html", "<html><body>Welcome!</body></html>")

    # Create client
    client = HTTPClient(client_host)

    # Make requests
    print("\n   GET /hello:")
    resp = client.get("00:00:00:00:00:01", "/hello")
    # Process server response
    frame = server_host.get_received()
    if frame:
        server._handle_receive(frame.payload, str(frame.src_mac))
    frame = client_host.get_received()
    if frame:
        client._handle_receive(frame.payload, str(frame.src_mac))

    if client.pending_response:
        print(f"   Response: {client.pending_response.body}")

    print("\n   GET /index.html (static):")
    client.get("00:00:00:00:00:01", "/index.html")
    frame = server_host.get_received()
    if frame:
        server._handle_receive(frame.payload, str(frame.src_mac))
    frame = client_host.get_received()
    if frame:
        client._handle_receive(frame.payload, str(frame.src_mac))

    if client.pending_response:
        print(f"   Response: {client.pending_response.body}")

    print("\n   GET /notfound:")
    client.get("00:00:00:00:00:01", "/notfound")
    frame = server_host.get_received()
    if frame:
        server._handle_receive(frame.payload, str(frame.src_mac))
    frame = client_host.get_received()
    if frame:
        client._handle_receive(frame.payload, str(frame.src_mac))

    if client.pending_response:
        print(f"   Response: {client.pending_response.status_code} {client.pending_response.body}")

    # Test File Transfer
    print("\n3. File Transfer Service:")
    topology2 = StarTopology(num_hosts=2)
    fs_server = FileServer(topology2.get_host("00:00:00:00:00:01"))
    fs_client = FileClient(topology2.get_host("00:00:00:00:00:02"))

    # Add some files
    fs_server.add_file("readme.txt", b"This is a readme file.")
    fs_server.add_file("data.txt", b"Some data content here.")

    print("   Files on server:", list(fs_server.files.keys()))

    # Test JSON API
    print("\n4. JSON API Service:")
    topology3 = StarTopology(num_hosts=2)
    api_server = JSONAPIServer(topology3.get_host("00:00:00:00:00:01"))
    api_client = JSONAPIClient(topology3.get_host("00:00:00:00:00:02"))

    # Register endpoints
    @api_server.endpoint("add")
    def add_handler(params):
        a = params.get('a', 0)
        b = params.get('b', 0)
        return {'sum': a + b}

    @api_server.endpoint("multiply")
    def multiply_handler(params):
        a = params.get('a', 1)
        b = params.get('b', 1)
        return {'product': a * b}

    # Make API call
    print("   Calling 'add' endpoint with a=5, b=3...")
    result = api_client.call("00:00:00:00:00:01", "add", {'a': 5, 'b': 3})

    # Process
    frame = topology3.get_host("00:00:00:00:00:01").get_received()
    if frame:
        api_server._handle_receive(frame.payload, str(frame.src_mac))
    frame = topology3.get_host("00:00:00:00:00:02").get_received()
    if frame:
        api_client._handle_receive(frame.payload, str(frame.src_mac))

    if api_client.last_response:
        print(f"   Response: {api_client.last_response}")

    print("\n" + "=" * 70)
