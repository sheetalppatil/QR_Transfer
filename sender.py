import os
import time
from protocol import *
from qr_utils import QRDisplay, QRScanner
from state import save_state, load_state, clear_state


def _is_ack(data: str) -> bool:
    try:
        return decode_msg(data).get("t") == MSG_ACK
    except Exception:
        return False


def _send_with_ack(display, scanner, msg, expected_file, expected_idx):
    """Show data QR and keep it visible while searching for matching ACK.
    Loops on stale ACKs (wrong file/index from previous chunks)
    until the correct ACK arrives or deadline expires."""
    for attempt in range(MAX_RETRIES):
        display.show(msg)

        deadline = time.time() + ACK_TIMEOUT + 1
        while time.time() < deadline:
            data = scanner.scan(0.6, filter_fn=_is_ack)
            if data:
                try:
                    m = decode_msg(data)
                    file_match = (expected_file is None) or (m.get("f") == expected_file)
                    idx_match = (expected_idx is None) or (m.get("i") == expected_idx)
                    if file_match and idx_match:
                        return m.get("s") == "ok"
                except Exception:
                    pass
                # Stale ACK (e.g. from previous chunk) - brief pause,
                # then keep scanning. The receiver will show the new
                # ACK once it processes our current data QR.
                time.sleep(0.1)
            # No ACK or stale: scanner returned None or we slept, retry

        if attempt < MAX_RETRIES - 1:
            print(f"       * Retry {attempt + 1}/{MAX_RETRIES}...")
    return False


def run_sender(source_dir, resume=False, display_mode=None):
    mode = display_mode or DISPLAY_MODE
    display = QRDisplay(mode)

    # --- Collect files ---
    all_files = []
    for root, dirs, fnames in os.walk(source_dir):
        for f in fnames:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, source_dir).replace("\\", "/")
            all_files.append((rel, full))
    all_files.sort(key=lambda x: x[0])

    print(f"\n{'=' * 60}")
    print(f"  QR FILE TRANSFER - SENDER")
    print(f"{'=' * 60}")
    print(f"  Source  : {os.path.abspath(source_dir)}")
    print(f"  Files   : {len(all_files)}")
    print(f"  Chunk   : {CHUNK_SIZE} bytes  |  Mode: {mode.upper()}")
    print(f"{'=' * 60}\n")

    if not all_files:
        print("  No files found.")
        display.close()
        return

    # --- Resume support ---
    completed_files = set()
    start_idx = 0
    if resume:
        state = load_state()
        if state and state.get("role") == "sender":
            completed_files = set(state.get("completed_files", []))
            start_idx = state.get("current_file_idx", 0)
            print(f"  > Resuming -- {len(completed_files)} files already done\n")

    display.show_text(
        f"Ready to send {len(all_files)} files.\n"
        f"Point receiver camera at this screen.\n"
        f"Press ENTER on receiver first, then here."
    )
    input("  Press ENTER to start...\n")

    success_count = 0
    with QRScanner() as scanner:
        for idx, (rel_path, full_path) in enumerate(all_files):
            if idx < start_idx:
                continue
            if rel_path in completed_files:
                print(f"  >> {rel_path} (already done)")
                success_count += 1
                continue

            print(f"\n  {'-' * 58}")
            print(f"  [{idx + 1}/{len(all_files)}] {rel_path}")

            with open(full_path, "rb") as f:
                raw = f.read()
            md5_val = file_md5(full_path)
            chunks = chunk_data(raw)
            print(f"       Size: {len(raw)} B  |  Chunks: {len(chunks)}")

            # --- Header ---
            print(f"       Header...", end=" ")
            ok = _send_with_ack(
                display, scanner,
                make_header(rel_path, len(chunks), md5_val),
                rel_path, -1,
            )
            if not ok:
                print("FAILED (no ACK)")
                continue
            print("OK")

            # --- Chunks ---
            failed = False
            for ci, chunk in enumerate(chunks):
                bar = progress_bar(ci, len(chunks))
                print(f"       Chunk {ci + 1:>{len(str(len(chunks)))}}/{len(chunks)} {bar}", end="\r")

                ok = _send_with_ack(
                    display, scanner,
                    make_chunk(rel_path, ci, chunk),
                    rel_path, ci,
                )
                if not ok:
                    print(f"\n       X Chunk {ci + 1} failed after {MAX_RETRIES} retries")
                    failed = True
                    break

                save_state({
                    "role": "sender",
                    "completed_files": list(completed_files),
                    "current_file_idx": idx,
                    "current_file": rel_path,
                    "current_chunk": ci,
                    "total_chunks": len(chunks),
                })

            if failed:
                print()
                continue

            print(f"\r       Chunks done    {progress_bar(len(chunks), len(chunks))}  ")

            # --- Footer ---
            print(f"       Verify...", end=" ")
            ok = _send_with_ack(
                display, scanner,
                make_footer(rel_path, md5_val),
                rel_path, len(chunks),
            )
            if not ok:
                print("X MD5 mismatch / no ACK")
                continue
            print("OK")

            completed_files.add(rel_path)
            success_count += 1

            save_state({
                "role": "sender",
                "completed_files": list(completed_files),
                "current_file_idx": idx + 1,
                "current_file": "",
                "current_chunk": -1,
                "total_chunks": 0,
            })

        # --- Manifest ---
        if success_count > 0:
            print(f"\n  {'-' * 58}")
            print(f"  Sending manifest for verification...", end=" ")
            manifest_paths = [f for f, _ in all_files]
            ok = _send_with_ack(
                display, scanner,
                make_manifest(manifest_paths),
                None, -1,
            )
            if ok:
                print("VERIFIED")
            else:
                print("no ACK (continuing)")

        # --- Done ---
        print(f"\n  {'-' * 58}")
        print(f"  OK Transfer complete! {success_count} files sent.")
        display.show(make_done())
        time.sleep(3)

    clear_state()
    display.close()
