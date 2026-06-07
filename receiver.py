import os
import time
from protocol import *
from qr_utils import QRDisplay, QRScanner
from state import save_state, load_state, clear_state


DATA_MSG_TYPES = {MSG_FILE_HEADER, MSG_CHUNK, MSG_FILE_FOOTER, MSG_MANIFEST, MSG_DONE}


class Receiver:
    def __init__(self, dest_dir: str, display_mode: str = None):
        self.dest_dir = dest_dir
        self.display = QRDisplay(display_mode or DISPLAY_MODE)

        self.current_file = ""
        self.current_path = ""
        self.temp_path = ""
        self.expected_chunks = 0
        self.expected_md5 = ""
        self.chunks: dict[int, bytes] = {}
        self.completed_files: set[str] = set()
        self.received_count = 0

    def run(self, resume: bool = False):
        print(f"\n{'=' * 60}")
        print(f"  QR FILE TRANSFER - RECEIVER")
        print(f"{'=' * 60}")
        print(f"  Destination : {os.path.abspath(self.dest_dir)}")
        print(f"  Mode        : {self.display.mode.upper()}")
        print(f"{'=' * 60}\n")

        os.makedirs(self.dest_dir, exist_ok=True)

        if resume:
            state = load_state()
            if state and state.get("role") == "receiver":
                self.completed_files = set(state.get("completed_files", []))
                self.received_count = len(self.completed_files)
                print(f"  > Resuming -- {self.received_count} files already done\n")

        self.display.show_text(
            "QR File Transfer - RECEIVER\n\n"
            "Waiting for sender...\n"
            "Point camera at sender screen."
        )

        with QRScanner() as scanner:
            while True:
                data = scanner.scan(timeout=1)
                if not data:
                    continue

                try:
                    msg = decode_msg(data)
                except Exception:
                    continue

                t = msg.get("t")

                # Only process data-type messages (ignore ACK)
                if t not in DATA_MSG_TYPES:
                    continue

                if t == MSG_FILE_HEADER:
                    self._handle_header(msg)
                elif t == MSG_CHUNK:
                    self._handle_chunk(msg)
                elif t == MSG_FILE_FOOTER:
                    self._handle_footer(msg)
                elif t == MSG_MANIFEST:
                    self._handle_manifest(msg)
                elif t == MSG_DONE:
                    self._handle_done()
                    break

        clear_state()
        self.display.close()

    # ── Internal helpers ────────────────────────────────────────

    def _ack(self, idx: int, status: str):
        self.display.show(make_ack(self.current_file, idx, status))
        time.sleep(1.2)
        self.display.show_text("Scanning for next data...")
        time.sleep(0.3)

    # ── Message handlers ────────────────────────────────────────

    def _handle_header(self, msg: dict):
        rel_path = msg["f"]
        n = msg["n"]
        md5 = msg["m"]

        # Duplicate header for file already in progress: just re-ACK
        if rel_path == self.current_file and n == self.expected_chunks and md5 == self.expected_md5 and self.chunks:
            self._ack(-1, "ok")
            return

        # New file
        self.expected_chunks = n
        self.expected_md5 = md5
        self.chunks = {}
        self.current_file = rel_path

        full_path = os.path.join(self.dest_dir, rel_path.replace("/", os.sep))
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        self.current_path = full_path
        self.temp_path = full_path + ".tmp"

        if os.path.exists(self.temp_path):
            os.remove(self.temp_path)

        print(f"\n  {'-' * 58}")
        print(f"  >> {rel_path}")
        print(f"       Chunks: {self.expected_chunks}  MD5: {self.expected_md5[:16]}...")

        self._ack(-1, "ok")

    def _handle_chunk(self, msg: dict):
        rel_path = msg["f"]
        idx = msg["i"]
        expected_crc = msg["c"]

        if rel_path != self.current_file:
            self._ack(idx, "nak")
            return

        if idx in self.chunks:
            self._ack(idx, "ok")
            return

        data = b64_decode(msg["d"])
        actual_crc = crc32(data)
        if actual_crc != expected_crc:
            print(f"\n       X CRC mismatch chunk {idx}")
            self._ack(idx, "nak")
            return

        self.chunks[idx] = data
        bar = progress_bar(len(self.chunks), self.expected_chunks)
        print(f"       Chunk {idx + 1:>{len(str(self.expected_chunks))}}/{self.expected_chunks} {bar}", end="\r")

        self._ack(idx, "ok")

    def _handle_footer(self, msg: dict):
        rel_path = msg["f"]

        if len(self.chunks) != self.expected_chunks:
            print(f"\n       X Missing chunks: got {len(self.chunks)}, need {self.expected_chunks}")
            self._ack(self.expected_chunks, "nak")
            return

        full_data = b"".join(self.chunks[i] for i in range(self.expected_chunks))

        with open(self.temp_path, "wb") as f:
            f.write(full_data)

        actual_md5 = file_md5(self.temp_path)
        if actual_md5 != self.expected_md5:
            print(f"\n       X MD5 mismatch")
            os.remove(self.temp_path)
            self._ack(self.expected_chunks, "nak")
            return

        if os.path.exists(self.current_path):
            os.remove(self.current_path)
        os.rename(self.temp_path, self.current_path)

        self.completed_files.add(rel_path)
        self.received_count += 1

        print(f"\n       > OK - {len(full_data)} bytes")

        self._ack(self.expected_chunks, "ok")

        save_state({
            "role": "receiver",
            "completed_files": list(self.completed_files),
        })

    def _handle_manifest(self, msg: dict):
        paths = msg.get("paths", [])
        print(f"\n  {'-' * 58}")
        print(f"  ## Verifying {len(paths)} files...\n")

        all_ok = True
        missing = []
        for rel_path in paths:
            full = os.path.join(self.dest_dir, rel_path.replace("/", os.sep))
            if os.path.exists(full):
                actual = file_md5(full)
                expected = ""
                print(f"    OK {rel_path}")
            else:
                print(f"    X  {rel_path}  -- MISSING")
                missing.append(rel_path)
                all_ok = False

        print()
        if all_ok:
            print(f"  ++ ALL {len(paths)} FILES VERIFIED SUCCESSFULLY!")
        else:
            print(f"  !! {len(missing)} file(s) missing")

        self._ack(-1, "ok" if all_ok else "nak")

    def _handle_done(self):
        print(f"\n  {'-' * 58}")
        print(f"  OK Transfer complete! Received {self.received_count} files.")
        if self.completed_files:
            print()
            for f in sorted(self.completed_files):
                print(f"     * {f}")
