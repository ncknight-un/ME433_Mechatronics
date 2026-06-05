"""
hx711_host.py
-------------
Sends a sample count to the Pico, reads back raw + IIR-filtered load-cell
data, plots both vs time, and computes/displays their FFTs.

Requirements:
    pip install pyserial matplotlib numpy
"""

import serial
import time
import numpy as np
import matplotlib.pyplot as plt
import sys

# ── Configuration ──────────────────────────────────────────────────────────────
PORT       = "/dev/ttyACM0"
BAUD       = 115200
N_SAMPLES  = 400             # ~10 seconds at 40 Hz
TIMEOUT_S  = 60              # serial read timeout
# ───────────────────────────────────────────────────────────────────────────────


def main():
    port = PORT
    if len(sys.argv) > 1:
        port = sys.argv[1]

    print(f"Opening {port} at {BAUD} baud …")
    with serial.Serial(port, BAUD, timeout=TIMEOUT_S) as ser:
        time.sleep(6)

        #  Wait for READY from Pico:
        print("Waiting for READY …")
        while True:
            line = ser.readline().decode(errors="replace").strip()
            if line == "READY":
                break
            if line:
                print(f"  [pico] {line}")

        # Send sample count:
        print(f"Requesting {N_SAMPLES} samples …")
        ser.write(f"{N_SAMPLES}\n".encode())

        # Wait for BEGIN:
        while True:
            line = ser.readline().decode(errors="replace").strip()
            if line.startswith("BEGIN"):
                expected = int(line.split()[1])
                print(f"Receiving {expected} samples …")
                break
            if line.startswith("ERROR"):
                print(f"Pico error: {line}")
                return

        # Read DATA:
        raw      = []
        filtered = []
        t_ms     = []

        while True:
            line = ser.readline().decode(errors="replace").strip()
            if line == "END":
                break
            if line.startswith("DATA"):
                parts = line.split()
                # DATA <time_ms> <raw> <filtered>
                t_ms.append(int(parts[1]))
                raw.append(int(parts[2]))
                filtered.append(float(parts[3]))

    print(f"Received {len(raw)} samples.")

    # Build time axis:
    t_s = (np.array(t_ms) - t_ms[0]) / 1000.0
    raw_arr  = np.array(raw,      dtype=float)
    filt_arr = np.array(filtered, dtype=float)

    # Estimate actual sample rate
    if len(t_s) > 1:
        fs = (len(t_s) - 1) / (t_s[-1] - t_s[0])
    else:
        fs = 40.0
    print(f"Estimated sample rate: {fs:.2f} Hz  (Nyquist: {fs/2:.1f} Hz)")

    # Set up FFT:
    N    = len(raw_arr)
    freq = np.fft.rfftfreq(N, d=1.0/fs)

    # Remove DC before FFT so the zero-freq spike doesn't drown everything
    fft_raw  = np.abs(np.fft.rfft(raw_arr  - raw_arr.mean()))
    fft_filt = np.abs(np.fft.rfft(filt_arr - filt_arr.mean()))

    # Plot Data:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("HX711 Load-Cell Data", fontsize=14, fontweight="bold")

    # Left plot: both time-domain signals
    ax1 = axes[0]
    ax1b = ax1.twinx()
    ax1.plot(t_s, raw_arr, color="#2196F3", linewidth=0.8, label="Raw (time)")
    ax1.plot(t_s, filt_arr, color="#F44336", linewidth=0.8, label="Filtered (time)")
    ax1.set_title("Time Domain")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("ADC counts")
    ax1b.set_yticks([])
    lines1 = ax1.get_lines() + ax1b.get_lines()
    ax1.legend(lines1, [l.get_label() for l in lines1], fontsize=8)
    ax1.grid(True, alpha=0.3)

    # Right plot: both FFT signals
    ax2 = axes[1]
    ax2b = ax2.twinx()
    ax2b.plot(freq, fft_raw, color="#90CAF9", linewidth=0.8, linestyle="--", alpha=0.8, label="Raw (FFT)")
    ax2b.plot(freq, fft_filt, color="#EF9A9A", linewidth=0.8, linestyle="--", alpha=0.8, label="Filtered (FFT)")
    ax2.set_title("Frequency Domain (FFT)")
    ax2.set_xlabel("Frequency (Hz)")
    ax2.set_ylabel("ADC counts")
    ax2b.set_ylabel("|X(f)|")
    ax2.set_yticks([])
    lines2 = ax2.get_lines() + ax2b.get_lines()
    ax2.legend(lines2, [l.get_label() for l in lines2], fontsize=8)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("HW14_data.png", dpi=150)
    print("Plot saved to HW14_data.png")
    plt.show()


if __name__ == "__main__":
    main()