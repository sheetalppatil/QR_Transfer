import os
import sys
import time
import cv2
import numpy as np
import qrcode


def _get_screen_size():
    try:
        import ctypes
        user32 = ctypes.windll.user32
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except Exception:
        try:
            import tkinter as tk
            root = tk.Tk()
            w = root.winfo_screenwidth()
            h = root.winfo_screenheight()
            root.destroy()
            return w, h
        except Exception:
            return 1920, 1080


class QRDisplay:
    def __init__(self, mode: str = "image"):
        self.mode = mode
        self.window_name = "QR Transfer - Display"
        self.screen_width, self.screen_height = _get_screen_size()
        self._window_inited = False

    def _init_window(self):
        if self.mode == "image" and not self._window_inited:
            cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
            try:
                cv2.setWindowProperty(self.window_name, cv2.WND_PROP_TOPMOST, 1)
            except Exception:
                pass
            x = max(0, (self.screen_width - 600) // 2)
            y = max(0, (self.screen_height - 600) // 3)
            cv2.moveWindow(self.window_name, x, y)
            self._window_inited = True

    def show(self, data: str):
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=1,
            border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)

        if self.mode == "image":
            img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            arr = np.array(img)
            arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            h, w = arr.shape[:2]

            max_w = int(self.screen_width * 0.75)
            max_h = int(self.screen_height * 0.80)
            scale = min(max_w / w, max_h / h)
            scale = max(2, int(scale))

            if scale != 1:
                arr = cv2.resize(arr, (w * scale, h * scale), interpolation=cv2.INTER_NEAREST)

            self._init_window()
            cv2.imshow(self.window_name, arr)
            cv2.waitKey(1)
        else:
            os.system("cls" if os.name == "nt" else "clear")
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
            self._init_window()
            cw = int(self.screen_width * 0.80)
            ch = int(self.screen_height * 0.60)
            canvas = np.ones((ch, cw, 3), dtype=np.uint8) * 255

            lines = text.split("\n")
            font_scale = max(0.6, min(1.8, cw / 700))
            font = cv2.FONT_HERSHEY_SIMPLEX
            thickness = 2
            line_heights = []
            total_h = 0
            for line in lines:
                (fw, fh), _ = cv2.getTextSize(line, font, font_scale, thickness)
                line_heights.append(fh)
                total_h += fh + 20
            total_h -= 20

            start_y = (ch - total_h) // 2 + line_heights[0]
            y = start_y
            for i, line in enumerate(lines):
                (fw, fh), _ = cv2.getTextSize(line, font, font_scale, thickness)
                x = (cw - fw) // 2
                cv2.putText(canvas, line, (x, y), font, font_scale, (0, 0, 0), thickness)
                if i + 1 < len(lines):
                    y += line_heights[i] + 20
                else:
                    y += line_heights[i]

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
            cv2.waitKey(1)


class QRScanner:
    def __init__(self, camera_id: int = 0):
        self.camera_id = camera_id
        self.cap = None
        self.window_name = "QR Transfer - Camera"
        self._window_inited = False

    def _init_window(self):
        if not self._window_inited:
            cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
            try:
                cv2.setWindowProperty(self.window_name, cv2.WND_PROP_TOPMOST, 1)
            except Exception:
                pass
            x = max(0, self.screen_width - 680) if hasattr(self, 'screen_width') else 0
            y = 0
            cv2.moveWindow(self.window_name, x, y)
            self._window_inited = True

    def __enter__(self):
        self.screen_width, self.screen_height = _get_screen_size()
        self.cap = cv2.VideoCapture(self.camera_id)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open camera #{self.camera_id}")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self._init_window()
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

    def scan(self, timeout: float = 2, filter_fn=None) -> str | None:
        """Scan for QR codes. Returns the first decoded string matching filter_fn,
        or any QR if filter_fn is None."""
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
                if filter_fn is None or filter_fn(data):
                    return data
            cv2.imshow(self.window_name, frame)
            key = cv2.waitKey(50)
            if key & 0xFF == ord("q"):
                break
        return None
