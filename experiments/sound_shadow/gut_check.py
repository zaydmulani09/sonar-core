"""
Sound shadow sensing — informal gut-check (pre-experiment, not a formal gate).

Passive mic-only recording: no emitted tone, no speaker playback. Records
ambient background noise (room hum, fan, HVAC, whatever's present) at rest,
then again while walking/moving, and produces a spectrogram (time vs.
frequency) for each — motion-induced distortion of ambient noise is a
broadband, time-varying effect, so a single averaged spectrum (as used in
the P1 Doppler experiment) is the wrong tool here.

This sidesteps P1's failure mode (direct-path leakage between the on-chassis
speaker and mic overwhelming the weak reflected signal) entirely, since
there's no transmitter at all.

No pass/fail threshold logic — this is "is there anything visually
interesting here", not a numeric gate. Look at the plots yourself.
"""

import time
from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.signal import spectrogram
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

FS = 44100
DURATION_S = 18.0

NPERSEG = 2048
NOVERLAP = 1024

FREQ_DISPLAY_MAX_HZ = 20000

# (label, low_hz, high_hz) — coarse bands for an eyeball-level variance readout
BANDS = [
    ("low (0-500Hz)", 0, 500),
    ("mid (500-4000Hz)", 500, 4000),
    ("high (4000-20000Hz)", 4000, 20000),
]

OUT_DIR = Path(__file__).parent
PLOTS_DIR = OUT_DIR / "plots"


def countdown(label, seconds=3):
    print(f"\n{label}")
    for n in range(seconds, 0, -1):
        print(f"  {n}...")
        time.sleep(1)
    print("  RECORDING")


def record(duration_s, fs=FS):
    rec = sd.rec(int(duration_s * fs), samplerate=fs, channels=1, dtype="float32")
    sd.wait()
    return rec[:, 0]


def compute_spectrogram(signal, fs=FS, nperseg=NPERSEG, noverlap=NOVERLAP):
    f, t, Sxx = spectrogram(signal, fs=fs, window="hamming",
                             nperseg=nperseg, noverlap=noverlap, scaling="density")
    return f, t, Sxx


def band_variance_stats(f, Sxx, label):
    print(f"\n  Per-band energy variance over time ({label}):")
    for band_label, lo, hi in BANDS:
        mask = (f >= lo) & (f < hi)
        if not mask.any():
            continue
        band_energy_per_frame = Sxx[mask, :].sum(axis=0)
        variance = np.var(band_energy_per_frame)
        mean = np.mean(band_energy_per_frame)
        cv = (np.sqrt(variance) / mean) if mean > 0 else float("nan")
        print(f"    {band_label}: mean={mean:.3e}, variance={variance:.3e}, "
              f"coeff.of.variation={cv:.3f}")


def save_spectrogram_plot(f, t, Sxx, title, out_path):
    fig, ax = plt.subplots(figsize=(10, 5))
    freq_mask = f <= FREQ_DISPLAY_MAX_HZ
    db = 10 * np.log10(Sxx[freq_mask, :] + 1e-20)
    mesh = ax.pcolormesh(t, f[freq_mask], db, shading="auto", cmap="magma")
    fig.colorbar(mesh, ax=ax, label="Power (dB)")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (Hz)")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def main():
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Sound shadow sensing — informal gut-check")
    print(f"Default input device: {sd.query_devices(kind='input')['name']}")
    print("\nBefore starting: note what ambient sound source is actually present right now —")
    print("  e.g. \"fan on\", \"AC running\", \"quiet room, no consistent background noise\".")
    print("This technique depends on something already being there to distort. If the room is")
    print("genuinely quiet, turn on a fan or similar before recording — a null result against")
    print("silence isn't informative either way.")
    input("\nPress Enter when ready to begin...")

    print(f"\n=== Phase 1: rest ({DURATION_S:.0f}s) ===")
    print("Sit still near the laptop. Normal room noise only — don't add anything artificial.")
    countdown("Recording starts in:", 3)
    rest_signal = record(DURATION_S)

    print(f"\n=== Phase 2: motion ({DURATION_S:.0f}s) ===")
    print("Get up, walk around, move in and out of proximity to the laptop.")
    countdown("Recording starts in:", 3)
    motion_signal = record(DURATION_S)

    f_rest, t_rest, Sxx_rest = compute_spectrogram(rest_signal)
    f_motion, t_motion, Sxx_motion = compute_spectrogram(motion_signal)

    band_variance_stats(f_rest, Sxx_rest, "rest")
    band_variance_stats(f_motion, Sxx_motion, "motion")

    rest_path = save_spectrogram_plot(f_rest, t_rest, Sxx_rest,
                                       "Ambient noise — rest", PLOTS_DIR / "spectrogram_rest.png")
    motion_path = save_spectrogram_plot(f_motion, t_motion, Sxx_motion,
                                         "Ambient noise — motion", PLOTS_DIR / "spectrogram_motion.png")

    print(f"\nSaved {rest_path}")
    print(f"Saved {motion_path}")
    print("\nNo pass/fail here — this is a gut-check. Look at the spectrograms yourself.")


if __name__ == "__main__":
    main()
