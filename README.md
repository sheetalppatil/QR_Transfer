# QR File Transfer

Transfer files between two computers using QR codes — no network, no cables, no cloud. One PC shows QR codes on its screen; the other scans them with a camera.

## How It Works

```
┌──────────────┐         QR codes (data)         ┌──────────────┐
│   SENDER     │ ───────────────────────────────► │   RECEIVER   │
│  (screen)    │    fh / ch / ff / mf / done      │  (camera)    │
│              │◄─────────────────────────────── │              │
│  (camera)    │         QR codes (ACK)           │  (screen)    │
└──────────────┘         ack                      └──────────────┘
```

- **Sender**: reads files from disk, splits them into chunks, encodes each chunk as a QR code displayed on screen
- **Receiver**: scans QR codes with a camera, reassembles chunks, writes files to disk
- **ACK protocol**: receiver acknowledges each message with its own QR code; sender retries on timeout (3 attempts, 3s timeout)
- **Integrity**: CRC32 per chunk + MD5 per file

## Requirements

- Python 3.10+
- Webcam (receiver) + optional webcam (sender for ACK scanning)
- Two screens (can be same machine for testing with two camera angles)

## Dependencies

```
opencv-python>=4.8.0
qrcode[pil]>=7.4
Pillow>=10.0.0
```

Install with:

```
pip install -r requirements.txt
```

## Usage

### Step 1: Prepare files to send

Put files in a directory on the sender machine (e.g., `./to_send`).

### Step 2: Start the receiver

```
python main.py receiver --dest ./received
```

On the receiver machine. Point its camera at the sender's screen.

### Step 3: Start the sender

```
python main.py sender --source ./to_send
```

On the sender machine. Press ENTER when both sides are ready.

### Full CLI Reference

```
python main.py <role> [options]
```

| Argument | Description |
|----------|-------------|
| `role` | `sender` or `receiver` |
| `--source DIR` | Source directory to send (required for sender) |
| `--dest DIR` | Destination directory (default: `./received`) |
| `--resume` | Resume from last saved state |
| `--display MODE` | Display mode: `image` (default) or `ascii` |

**Examples:**

```bash
# Sender
python main.py sender --source ./my_documents

# Receiver
python main.py receiver --dest ./downloaded_files

# Resume a broken transfer
python main.py receiver --dest ./downloaded_files --resume

# Use ASCII art QR codes (no GUI needed)
python main.py sender --source ./docs --display ascii
```

## Two-Computer Setup

| Machine | Role | Has Camera | Shows QR |
|---------|------|------------|----------|
| Computer A | Sender | Yes (for ACK) | Data QR codes |
| Computer B | Receiver | Yes (for data) | ACK QR codes |

**Positioning:**

1. Point **Receiver's camera** at **Sender's screen** (to read data QR codes)
2. Point **Sender's camera** at **Receiver's screen** (to read ACK QR codes)

Start receiver first, then sender.

## Single-Computer Test

You can test on one machine if you have two cameras or one camera that can see the screen. Position the camera to clearly see the QR codes on screen without reflection loops.

## Display Modes

### `image` (default)

Opens an always-on-top OpenCV window with the QR code, dynamically sized to fit your screen.

### `ascii`

Prints QR codes as ASCII art directly in the terminal. Useful for SSH sessions or headless setups.

### Window Management

- Display window: always-on-top, centered, auto-sized
- Camera window: always-on-top, positioned at top-right
- Press `q` in camera window to exit scan early

## Protocol

Messages are JSON with minimal keys. Types:

| Type | Code | Sender | Receiver | Fields |
|------|------|--------|----------|--------|
| File Header | `fh` | Shows | Scans | `f` (path), `n` (chunks), `m` (MD5) |
| Chunk | `ch` | Shows | Scans | `f`, `i` (index), `d` (base64 data), `c` (CRC32) |
| File Footer | `ff` | Shows | Scans | `f`, `m` (MD5) |
| ACK | `ack` | Scans | Shows | `f`, `i`, `s` (ok/nak) |
| Manifest | `mf` | Shows | Scans | `paths` (list) |
| Done | `done` | Shows | Scans | (none) |

After all chunks, sender sends a manifest. Receiver verifies all files exist. Then sender sends "done" to signal completion.

## Resume

If the transfer is interrupted, use `--resume` on both sides to continue. Progress is saved to `transfer_state.json` in the working directory.

## Project Structure

```
qr_transfer/
├── main.py           # CLI entry point
├── sender.py         # Sender logic (show data QR, scan ACK)
├── receiver.py       # Receiver logic (scan data QR, show ACK)
├── qr_utils.py       # QR display (OpenCV/ASCII) and camera scanner
├── protocol.py       # Message types, CRC32, MD5, JSON encode/decode
├── state.py          # Save/load/clear resume state
├── requirements.txt
└── README.md
```

## Troubleshooting

| Symptom | Likely Fix |
|---------|------------|
| "X Chunk N failed after 3 retries" | Sender camera isn't seeing receiver's ACK QR. Reposition sender camera to point at receiver screen. |
| Receiver keeps printing the same header | Sender's ACK scan is failing. Ensure sender camera sees receiver screen (not its own). |
| QR window behind terminal | Display and camera windows are now always-on-top. If still behind, minimize other windows. |
| QR code too big for screen | QR is now auto-sized. If still too big, try `--display ascii` mode. |
| Camera not found | Change camera ID in `qr_utils.py` `QRScanner.__init__(camera_id=0)` to 1 or 2. |
| "Invalid QR data, skipping" | Camera is seeing garbage or wrong QR codes. Check positioning and lighting. |

## Modifying for AI/Feature Changes

Key constants in `protocol.py`:

| Constant | Default | Description |
|----------|---------|-------------|
| `CHUNK_SIZE` | 1200 | Raw bytes per chunk before base64 (~1600 chars in QR) |
| `ACK_TIMEOUT` | 2 | Seconds to wait for ACK before retry |
| `MAX_RETRIES` | 3 | Number of send attempts per message |

Timing values in `sender.py` (`_send_with_ack`) and `receiver.py` (`_ack`):

| Value | Location | Description |
|-------|----------|-------------|
| 0.6s | sender `_send_with_ack` | How long data QR is shown before clearing |
| 0.3s | sender `_send_with_ack` | Camera settle time after clearing display |
| 3s | sender `_send_with_ack` | ACK scan timeout (ACK_TIMEOUT + 1) |
| 1.2s | receiver `_ack` | How long ACK QR is shown before clearing |
| 0.3s | receiver `_ack` | Camera settle time after clearing ACK |
