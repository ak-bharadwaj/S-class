"""Authenticated OS-level IPC transport for Trusted Deployment Authority Broker."""
import os
import sys
import json
import socket
import struct
import threading
from typing import Optional, Dict, Any, Tuple, Callable

MAX_FRAME_SIZE = 1024 * 1024  # 1MB
HEADER_FORMAT = "!I"  # 4-byte big-endian frame length


def encode_frame(payload: Dict[str, Any]) -> bytes:
    data = json.dumps(payload).encode("utf-8")
    if len(data) > MAX_FRAME_SIZE:
        raise ValueError(f"Payload size {len(data)} exceeds maximum frame size {MAX_FRAME_SIZE}")
    header = struct.pack(HEADER_FORMAT, len(data))
    return header + data


def read_exact(sock: socket.socket, num_bytes: int) -> bytes:
    buf = bytearray()
    while len(buf) < num_bytes:
        chunk = sock.recv(num_bytes - len(buf))
        if not chunk:
            raise ConnectionResetError("Connection closed before all bytes were read.")
        buf.extend(chunk)
    return bytes(buf)


def decode_frame(sock: socket.socket) -> Dict[str, Any]:
    header = read_exact(sock, 4)
    length = struct.unpack(HEADER_FORMAT, header)[0]
    if length > MAX_FRAME_SIZE:
        raise ValueError(f"Frame length {length} exceeds maximum allowable {MAX_FRAME_SIZE}")
    data = read_exact(sock, length)
    return json.loads(data.decode("utf-8"))


class OSIPCServer:
    """Authenticated OS IPC Server for Trust Domain A (Broker)."""
    def __init__(
        self,
        endpoint_path: str,
        handler: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]],
        allowed_uid: Optional[int] = None,
        auth_secret: Optional[str] = None,
    ):
        self.endpoint_path = endpoint_path
        self.handler = handler
        self.allowed_uid = allowed_uid if allowed_uid is not None else (os.getuid() if hasattr(os, "getuid") else None)
        self.auth_secret = auth_secret
        self.server_socket: Optional[socket.socket] = None
        self._is_running = False
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        with self._lock:
            if self._is_running:
                return
            if sys.platform != "win32":
                if os.path.exists(self.endpoint_path):
                    try:
                        os.remove(self.endpoint_path)
                    except OSError:
                        pass
                self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.server_socket.bind(self.endpoint_path)
                os.chmod(self.endpoint_path, 0o600)
            else:
                try:
                    if os.path.exists(self.endpoint_path):
                        try:
                            os.remove(self.endpoint_path)
                        except OSError:
                            pass
                    self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    self.server_socket.bind(self.endpoint_path)
                except Exception:
                    self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.server_socket.bind(("127.0.0.1", 0))
                    port = self.server_socket.getsockname()[1]
                    with open(self.endpoint_path, "w") as f:
                        f.write(f"127.0.0.1:{port}")

            self.server_socket.listen(16)
            self._is_running = True
            self._thread = threading.Thread(target=self._serve_loop, daemon=True)
            self._thread.start()

    def _verify_peer_credentials(self, client_sock: socket.socket) -> Tuple[bool, Dict[str, Any]]:
        peer_meta = {"authenticated": False}
        if sys.platform != "win32":
            try:
                so_peercred = getattr(socket, "SO_PEERCRED", 17)
                cred_bytes = client_sock.getsockopt(socket.SOL_SOCKET, so_peercred, struct.calcsize("3i"))
                pid, uid, gid = struct.unpack("3i", cred_bytes)
                peer_meta["pid"] = pid
                peer_meta["uid"] = uid
                peer_meta["gid"] = gid
                if self.allowed_uid is not None and uid != self.allowed_uid:
                    return False, peer_meta
            except Exception:
                pass

        if self.auth_secret is not None:
            try:
                auth_req = decode_frame(client_sock)
                if auth_req.get("auth_secret") == self.auth_secret:
                    peer_meta["authenticated"] = True
                    client_sock.sendall(encode_frame({"status": "AUTH_OK"}))
                    return True, peer_meta
                else:
                    client_sock.sendall(encode_frame({"status": "AUTH_DENIED", "error": "Invalid auth credentials"}))
                    return False, peer_meta
            except Exception:
                return False, peer_meta

        peer_meta["authenticated"] = True
        return True, peer_meta

    def _serve_loop(self) -> None:
        while self._is_running:
            try:
                client_sock, _ = self.server_socket.accept()
            except Exception:
                break

            client_thread = threading.Thread(
                target=self._handle_client,
                args=(client_sock,),
                daemon=True,
            )
            client_thread.start()

    def _handle_client(self, client_sock: socket.socket) -> None:
        try:
            authenticated, peer_meta = self._verify_peer_credentials(client_sock)
            if not authenticated:
                client_sock.close()
                return

            while self._is_running:
                try:
                    req = decode_frame(client_sock)
                except (ConnectionResetError, EOFError, ValueError):
                    break

                try:
                    resp = self.handler(req, peer_meta)
                except Exception as e:
                    resp = {"error": str(e), "success": False}

                try:
                    client_sock.sendall(encode_frame(resp))
                except Exception:
                    break
        finally:
            try:
                client_sock.close()
            except Exception:
                pass

    def stop(self) -> None:
        with self._lock:
            self._is_running = False
            if self.server_socket:
                try:
                    self.server_socket.close()
                except Exception:
                    pass
                self.server_socket = None
            if sys.platform != "win32" or not self.endpoint_path.endswith(".txt"):
                if os.path.exists(self.endpoint_path):
                    try:
                        os.remove(self.endpoint_path)
                    except OSError:
                        pass


class OSIPCClient:
    """Authenticated OS IPC Client for Trust Domain B (S-Class Application)."""
    def __init__(self, endpoint_path: str, auth_secret: Optional[str] = None):
        self.endpoint_path = endpoint_path
        self.auth_secret = auth_secret
        self._sock: Optional[socket.socket] = None
        self._lock = threading.RLock()

    def connect(self) -> None:
        with self._lock:
            if self._sock is not None:
                return

            if not os.path.exists(self.endpoint_path):
                raise ConnectionError(f"IPC endpoint not found at '{self.endpoint_path}'")

            if sys.platform != "win32":
                self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self._sock.connect(self.endpoint_path)
            else:
                try:
                    self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    self._sock.connect(self.endpoint_path)
                except Exception:
                    with open(self.endpoint_path, "r") as f:
                        content = f.read().strip()
                    host, port_str = content.split(":")
                    self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self._sock.connect((host, int(port_str)))

            if self.auth_secret is not None:
                self._sock.sendall(encode_frame({"auth_secret": self.auth_secret}))
                resp = decode_frame(self._sock)
                if resp.get("status") != "AUTH_OK":
                    self._sock.close()
                    self._sock = None
                    raise PermissionError(f"IPC connection rejected by authority broker: {resp.get('error')}")

    def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            if self._sock is None:
                self.connect()

            req = {"method": method, "params": params or {}}
            try:
                self._sock.sendall(encode_frame(req))
                resp = decode_frame(self._sock)
                if resp.get("status") == "AUTH_DENIED":
                    raise PermissionError(f"IPC request rejected by authority broker: {resp.get('error')}")
                return resp
            except PermissionError:
                self.close()
                raise
            except Exception as e:
                self.close()
                raise ConnectionError(f"Authority broker IPC communication failure: {e}") from e

    def close(self) -> None:
        with self._lock:
            if self._sock:
                try:
                    self._sock.close()
                except Exception:
                    pass
                self._sock = None
