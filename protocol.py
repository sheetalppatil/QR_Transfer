import hashlib
import zlib
import base64
import json

# === CONFIGURATION ===
DISPLAY_MODE = "image"   # "image" or "ascii"
CHUNK_SIZE = 100        # bytes per raw data chunk before base64
ACK_TIMEOUT = 2          # seconds to wait for ACK
MAX_RETRIES = 3          # max retries per message

# === Message types ===
MSG_FILE_HEADER = "fh"
MSG_CHUNK = "ch"
MSG_FILE_FOOTER = "ff"
MSG_ACK = "ack"
MSG_MANIFEST = "mf"
MSG_DONE = "done"


# === Helpers ===

def crc32(data: bytes) -> str:
    return format(zlib.crc32(data) & 0xFFFFFFFF, '08x')


def file_md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def b64_encode(data: bytes) -> str:
    return base64.b64encode(data).decode('ascii')


def b64_decode(s: str) -> bytes:
    return base64.b64decode(s)


def encode_msg(msg: dict) -> str:
    return json.dumps(msg, separators=(',', ':'))


def decode_msg(s: str) -> dict:
    return json.loads(s)


def chunk_data(data: bytes, size: int = None) -> list:
    sz = size or CHUNK_SIZE
    return [data[i:i + sz] for i in range(0, len(data), sz)]


def progress_bar(curr: int, total: int, width: int = 20) -> str:
    if total == 0:
        return f"[{'░' * width}] 0%"
    filled = int(width * curr / total)
    bar = "█" * filled + "░" * (width - filled)
    pct = int(100 * curr / total)
    return f"[{bar}] {pct}%"


# === Message factories ===

def make_header(path: str, n: int, md5: str) -> str:
    return encode_msg({"t": MSG_FILE_HEADER, "f": path, "n": n, "m": md5})


def make_chunk(path: str, i: int, data: bytes) -> str:
    return encode_msg({
        "t": MSG_CHUNK,
        "f": path,
        "i": i,
        "d": b64_encode(data),
        "c": crc32(data),
    })


def make_footer(path: str, md5: str) -> str:
    return encode_msg({"t": MSG_FILE_FOOTER, "f": path, "m": md5})


def make_ack(path: str, i: int, status: str) -> str:
    return encode_msg({"t": MSG_ACK, "f": path, "i": i, "s": status})


def make_manifest(paths: list) -> str:
    return encode_msg({"t": MSG_MANIFEST, "paths": paths})


def make_done() -> str:
    return encode_msg({"t": MSG_DONE})
