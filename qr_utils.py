import os
import sys
import time
import cv2
import numpy as np
import qrcode


class QRDisplay:
    def __init__(self, mode: str = "image"):
        self.mode = mode
        self.window_name = "QR Transfer - Display"

    def show(self, data: str):
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)

        if self.mode == "image":
            img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            arr = np.array(img)
            arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            s = 3
            h, w = arr.shape[:2]
            arr = cv2.resize(arr, (w * s, h * s), interpolation=cv2.INTER_NEAREST)
            cv2.imshow(self.window_name, arr)
            cv2.waitKey(1)
        else:
            os.system("cls" if os.name == "nt" else "clear")
            border = qr.border
            mod = qr.modules
            size = len(mod)
            for r in range(size):
                line = ""
                for c in range(size):
                    line += "##" if mod[r][c] else "  "
                print(line)
            preview = data[:80].replace("\n", " ")
            print(f"\n{'-' * 60}")
            print(f"  {preview}{'...' if len(data) > 80 else ''}")
            print(f"{'-' * 60}")

    def show_text(self, text: str):
        if self.mode == "image":
            canvas = np.ones((400, 600, 3), dtype=np.uint8) * 255
            y = 30
            for line in text.split("\n"):
                cv2.putText(
                    canvas, line, (20, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1,
                )
                y += 25
            cv2.imshow(self.window_name, canvas)
            cv2.waitKey(1)
        else:
            os.system("cls" if os.name == "nt" else "clear")
            print(text)

    def close(self):
        if self.mode == "image":
            try:
                cv2.destroyWindow(self.window_name)
            except Exception:
                pass


class QRScanner:
    def __init__(self, camera_id: int = 0):
        self.camera_id = camera_id
        self.cap = None
        self.window_name = "QR Transfer - Camera"

    def __enter__(self):
        self.cap = cv2.VideoCapture(self.camera_id)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open camera #{self.camera_id}")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        return self

    def __exit__(self, *args):
        self.release()

    def release(self):
        if self.cap:
            self.cap.release()
            self.cap = None
        try:
            cv2.destroyWindow(self.window_name)
        except Exception:
            pass
        cv2.waitKey(1)

    def scan(self, timeout: float = 2) -> str | None:
        if not self.cap:
            raise RuntimeError("Scanner not opened. Use 'with' block.")
        detector = cv2.QRCodeDetector()
        start = time.time()
        while time.time() - start < timeout:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.05)
                continue
            data, points, _ = detector.detectAndDecode(frame)
            if data:
                return data
            cv2.imshow(self.window_name, frame)
            key = cv2.waitKey(50)
            if key & 0xFF == ord("q"):
                break
        return None
