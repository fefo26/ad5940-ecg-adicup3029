#!/usr/bin/env python3
"""Live view of the EcgStream firmware output (mV, one sample per line).

Runs on Linux, Windows and macOS with Python 3, Tk and pyserial.

usage: ecg_view.py [port] [--seconds N] [--log FILE] [--list]

Without a port the board is searched by the USB id of its DAPLink
(0d28:0204); if it is not there the viewer waits for it.

keys:  space = pause, q = quit
"""
import argparse
import collections
import statistics
import threading
import time
import tkinter as tk
import tkinter.font

import serial
import serial.tools.list_ports

FS = 250
BAUD = 230400
DAPLINK_ID = (0x0D28, 0x0204)
BG = "#101418"
NOTE_SECONDS = 6    # the firmware repeats a warning every 5 s while it holds


def find_port():
    """Serial port of the DAPLink, or None."""
    for port in serial.tools.list_ports.comports():
        if (port.vid, port.pid) == DAPLINK_ID:
            return port.device
    return None


class Viewer:
    def __init__(self, port, seconds, log=None):
        self.port = port
        self.n = int(seconds * FS)
        self.seconds = seconds
        self.samples = collections.deque(maxlen=self.n)
        self.link = "starting"      # state of the serial connection
        self.note = ""              # last status line of the firmware
        self.note_time = 0.0
        self.paused = False
        self.running = True
        self.center = None
        self.span = 100.0
        self.log = open(log, "ab", buffering=0) if log else None

        self.root = tk.Tk()
        self.root.title("ECG")
        fixed = tkinter.font.nametofont("TkFixedFont")
        self.grid_font = (fixed.actual("family"), 9)
        self.canvas = tk.Canvas(self.root, width=1200, height=500, bg=BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.label = tk.Label(self.root, anchor="w", font=(fixed.actual("family"), 10), bg=BG, fg="#c0c8d0")
        self.label.pack(fill=tk.X)
        self.root.bind("q", lambda e: self.quit())
        self.root.bind("<space>", lambda e: setattr(self, "paused", not self.paused))
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        threading.Thread(target=self.reader, daemon=True).start()
        self.root.after(40, self.draw)

    def quit(self):
        self.running = False
        self.root.destroy()

    def reader(self):
        """Read the port forever; (re)connect when the board appears."""
        while self.running:
            port = self.port or find_port()
            if port is None:
                self.link = "waiting for the board (DAPLink serial port not found)"
                time.sleep(1)
                continue
            try:
                with serial.Serial(port, BAUD, timeout=0.2) as ser:
                    self.link = "connected to %s" % port
                    self.read_port(ser)
            except (serial.SerialException, OSError) as exc:
                self.link = "%s: %s" % (port, exc)
                time.sleep(1)

    def read_port(self, ser):
        buf = b""
        while self.running:
            data = ser.read(256)
            if self.log:
                self.log.write(data)
            buf += data
            *lines, buf = buf.split(b"\n")
            for raw in lines:
                line = raw.decode("ascii", "ignore").strip()
                if line.startswith("#"):
                    self.note = line[1:].strip()
                    self.note_time = time.monotonic()
                    continue
                try:
                    value = float(line.split()[0])
                except (ValueError, IndexError):
                    continue
                if not self.paused:
                    self.samples.append(value)

    def status_text(self):
        """Connection state, plus the firmware status while it is recent."""
        if self.note and time.monotonic() - self.note_time < NOTE_SECONDS:
            return "%s: %s" % (self.link, self.note)
        return self.link

    def draw(self):
        c = self.canvas
        w, h = c.winfo_width(), c.winfo_height()
        data = list(self.samples)
        c.delete("all")
        if len(data) > FS // 2:
            mid = statistics.median(data)
            lo, hi = min(data), max(data)
            want = max(40.0, 2.4 * max(hi - mid, mid - lo))
            self.center = mid if self.center is None else self.center + 0.1 * (mid - self.center)
            self.span += 0.1 * (want - self.span)
            top, bottom = self.center + self.span / 2, self.center - self.span / 2
            # grid: one vertical line per second, five horizontal divisions
            for s in range(int(self.seconds) + 1):
                x = w * s / self.seconds
                c.create_line(x, 0, x, h, fill="#243038")
            for i in range(6):
                y = h * i / 5
                c.create_line(0, y, w, y, fill="#243038")
                c.create_text(4, min(max(y, 8), h - 8), anchor="w", fill="#708090", font=self.grid_font,
                              text="%.0f mV" % (top - (top - bottom) * i / 5))
            x0 = w * (self.n - len(data)) / self.n
            step = (w - x0) / max(len(data) - 1, 1)
            pts = []
            for i, v in enumerate(data):
                pts.append(x0 + i * step)
                pts.append(h * (top - v) / (top - bottom))
            c.create_line(pts, fill="#40e080", width=1.5)
        self.label.config(text="%s%s   |   %d s window, 1 s per division   |   space: pause, q: quit"
                          % ("[PAUSED] " if self.paused else "", self.status_text(), self.seconds))
        if self.running:
            self.root.after(40, self.draw)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("port", nargs="?", help="serial port (COM5, /dev/ttyACM1); default: search the DAPLink")
    ap.add_argument("--seconds", type=float, default=8, help="width of the window (default 8)")
    ap.add_argument("--log", help="append everything received to this file")
    ap.add_argument("--list", action="store_true", help="list the serial ports and exit")
    args = ap.parse_args()
    if args.list:
        for port in serial.tools.list_ports.comports():
            if port.vid is None:    # not a USB port
                continue
            mark = "  <- DAPLink" if (port.vid, port.pid) == DAPLINK_ID else ""
            print("%s  %s%s" % (port.device, port.description, mark))
        return
    Viewer(args.port, args.seconds, args.log).root.mainloop()


if __name__ == "__main__":
    main()
