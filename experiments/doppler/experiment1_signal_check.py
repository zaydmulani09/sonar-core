"""
Experiment 1: Signal existence check (SoundWave method, CHI 2012).

Plays a continuous 19kHz pilot tone and records concurrently. Measures
spectral peak bandwidth broadening caused by Doppler shift from hand motion
near the device, vs. a rest (no-motion) baseline.

Auto-timer design (no manual keypress sync): each motion trial is one
continuous recording split into a "rest" phase (first REST_S seconds, stay
still) and a "motion" phase (remaining MOTION_S seconds, wave hand). A
BUFFER_S guard band is discarded on both sides of the phase transition
before analysis, since human reaction to the countdown is imprecise but the
script only scores the parts it's confident are correctly labeled.

Separate dedicated rest-only trials (no transition, no wave) are recorded
to establish the noise-floor bandwidth of the pilot tone at rest.
"""

import sys
import time
import json
from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.signal.windows import hamming
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

FS = 44100
TONE_FREQ = 19000.0
N_FFT = 2048
HOP = 1024
BIN_HZ = FS / N_FFT  # ~21.53 Hz/bin

REST_S = 2.0
MOTION_S = 3.0
BUFFER_S = 0.3
TRIAL_DURATION_S = REST_S + MOTION_S

REST_ONLY_DURATION_S = 3.0
N_MOTION_TRIALS = 5
N_REST_TRIALS = 2

PASS_BINS_INCREASE = 4
PASS_MIN_MOTION_TRIALS = 4
PASS_REST_BASELINE_MAX_BINS = 2

SEARCH_HALF_WIDTH_HZ = 500.0

# -40dBFS RMS default: a quiet room's mic noise floor on typical laptop
# hardware sits below -50dBFS RMS; -40dBFS leaves headroom above HVAC/fan
# hum while still catching speech, footsteps, or keyboard clatter that
# would contaminate a "rest" reading.
AMBIENT_THRESHOLD_DB = -40.0
AMBIENT_CHECK_S = 1.0
AMBIENT_MAX_ATTEMPTS = 3
AMBIENT_RETRY_PAUSE_S = 3.0

SUSPECT_REST_MULTIPLIER = 2.0

OUT_DIR = Path(__file__).parent
PLOTS_DIR = OUT_DIR / "plots"
RESULTS_MD = OUT_DIR / "experiment1_results.md"

AMBIENT_LOG = []


def make_tone(duration_s, fs=FS, freq=TONE_FREQ):
    t = np.arange(int(duration_s * fs)) / fs
    tone = 0.5 * np.sin(2 * np.pi * freq * t)
    return tone.astype(np.float32)


def play_record(duration_s):
    tone = make_tone(duration_s)
    tone_stereo = np.column_stack([tone, tone])
    rec = sd.playrec(tone_stereo, samplerate=FS, channels=1, dtype="float32")
    sd.wait()
    return rec[:, 0]


def countdown(label, seconds=3):
    print(f"\n{label}")
    for n in range(seconds, 0, -1):
        print(f"  {n}...")
        time.sleep(1)
    print("  RECORDING")


def check_ambient_noise(label):
    """Mic-only sample (no tone playing) before a trial starts. Retries up
    to AMBIENT_MAX_ATTEMPTS times if the room is too loud, then proceeds
    anyway with a logged warning so a persistently noisy room is documented
    rather than silently hidden."""
    db = None
    for attempt in range(1, AMBIENT_MAX_ATTEMPTS + 1):
        ambient = sd.rec(int(AMBIENT_CHECK_S * FS), samplerate=FS, channels=1, dtype="float32")
        sd.wait()
        ambient = ambient[:, 0]
        rms = np.sqrt(np.mean(ambient ** 2))
        db = 20 * np.log10(rms + 1e-12)
        if db <= AMBIENT_THRESHOLD_DB:
            entry = {"label": label, "passed": True, "attempts": attempt, "final_db": db}
            AMBIENT_LOG.append(entry)
            return entry
        print(f"  [ambient] Room noise too high ({db:.1f}dB) — pausing "
              f"{AMBIENT_RETRY_PAUSE_S:.0f}s, keep quiet (attempt {attempt}/{AMBIENT_MAX_ATTEMPTS})")
        if attempt < AMBIENT_MAX_ATTEMPTS:
            time.sleep(AMBIENT_RETRY_PAUSE_S)
    print(f"  [ambient] WARNING: room noise still high after {AMBIENT_MAX_ATTEMPTS} "
          f"attempts ({db:.1f}dB) — proceeding anyway")
    entry = {"label": label, "passed": False, "attempts": AMBIENT_MAX_ATTEMPTS, "final_db": db}
    AMBIENT_LOG.append(entry)
    return entry


def avg_power_spectrum(segment, fs=FS, n_fft=N_FFT, hop=HOP):
    if len(segment) < n_fft:
        raise ValueError(f"segment too short: {len(segment)} samples < n_fft={n_fft}")
    win = hamming(n_fft)
    frames = []
    for start in range(0, len(segment) - n_fft + 1, hop):
        frame = segment[start : start + n_fft] * win
        spec = np.fft.rfft(frame)
        frames.append(np.abs(spec) ** 2)
    if not frames:
        raise ValueError("no frames extracted")
    power = np.mean(frames, axis=0)
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / fs)
    return freqs, power


def print_signal_diagnostic(segment, fs=FS, n_fft=N_FFT, hop=HOP, label=""):
    """Raw power at the 19kHz carrier vs. a 1kHz reference bin, independent
    of any bandwidth logic. Tells us if the tone reaches the mic at all."""
    freqs, power = avg_power_spectrum(segment, fs, n_fft, hop)
    carrier_idx = np.argmin(np.abs(freqs - TONE_FREQ))
    ref_idx = np.argmin(np.abs(freqs - 1000.0))
    carrier_db = 10 * np.log10(power[carrier_idx] + 1e-20)
    ref_db = 10 * np.log10(power[ref_idx] + 1e-20)
    print(f"  [diag{' ' + label if label else ''}] "
          f"19kHz bin ({freqs[carrier_idx]:.0f}Hz): {carrier_db:.1f}dB | "
          f"1kHz ref bin ({freqs[ref_idx]:.0f}Hz): {ref_db:.1f}dB | "
          f"delta: {carrier_db - ref_db:+.1f}dB")
    return carrier_db, ref_db


def measure_bandwidth(segment, fs=FS, n_fft=N_FFT, hop=HOP,
                       target_freq=TONE_FREQ, search_half_width_hz=SEARCH_HALF_WIDTH_HZ):
    freqs, power = avg_power_spectrum(segment, fs, n_fft, hop)
    lo = target_freq - search_half_width_hz
    hi = target_freq + search_half_width_hz
    search_mask = (freqs >= lo) & (freqs <= hi)
    search_idx = np.where(search_mask)[0]
    if len(search_idx) == 0:
        raise ValueError("search window out of range")
    peak_idx = search_idx[np.argmax(power[search_idx])]
    peak_power = power[peak_idx]
    threshold = peak_power / 2.0  # -3dB / half-power width

    search_lo, search_hi = search_idx.min(), search_idx.max()

    left = peak_idx
    while left > search_lo and power[left - 1] >= threshold:
        left -= 1
    right = peak_idx
    while right < search_hi and power[right + 1] >= threshold:
        right += 1

    bandwidth_bins = right - left + 1
    bandwidth_hz = bandwidth_bins * BIN_HZ
    return {
        "bins": bandwidth_bins,
        "hz": bandwidth_hz,
        "peak_freq": freqs[peak_idx],
        "peak_idx": peak_idx,
        "freqs": freqs,
        "power": power,
        "left_idx": left,
        "right_idx": right,
    }


def run_rest_trial(trial_num):
    print(f"\n=== Rest baseline trial {trial_num} ===")
    check_ambient_noise(f"rest trial {trial_num}")
    countdown("Stay still. Recording starts in:", 3)
    rec = play_record(REST_ONLY_DURATION_S)
    print_signal_diagnostic(rec, label=f"rest trial {trial_num}")
    result = measure_bandwidth(rec)
    print(f"Rest trial {trial_num}: {result['bins']} bins (~{result['hz']:.1f}Hz)")
    return result


def run_motion_trial(trial_num, rest_baseline_avg_bins=None):
    print(f"\n=== Motion trial {trial_num} ===")
    check_ambient_noise(f"motion trial {trial_num}")
    print(f"Stay still for {REST_S:.0f}s, then wave your hand near the laptop for {MOTION_S:.0f}s.")
    countdown("Recording starts in:", 3)
    rec = play_record(TRIAL_DURATION_S)
    print_signal_diagnostic(rec, label=f"motion trial {trial_num} (full recording)")

    rest_end = int((REST_S - BUFFER_S) * FS)
    motion_start = int((REST_S + BUFFER_S) * FS)

    rest_segment = rec[:rest_end]
    motion_segment = rec[motion_start:]

    rest_result = measure_bandwidth(rest_segment)
    motion_result = measure_bandwidth(motion_segment)
    increase_bins = motion_result["bins"] - rest_result["bins"]
    increase_hz = increase_bins * BIN_HZ

    suspect = (rest_baseline_avg_bins is not None
               and rest_result["bins"] > SUSPECT_REST_MULTIPLIER * rest_baseline_avg_bins)

    suffix = "  [SUSPECT: elevated rest-segment noise]" if suspect else ""
    print(f"Trial {trial_num}: rest {rest_result['bins']} bins, "
          f"motion {motion_result['bins']} bins -> "
          f"{increase_bins} bins (~{increase_hz:.1f}Hz) above rest baseline{suffix}")

    return {
        "trial_num": trial_num,
        "rest": rest_result,
        "motion": motion_result,
        "increase_bins": increase_bins,
        "increase_hz": increase_hz,
        "suspect": suspect,
    }


def save_trial_plot(trial):
    fig, ax = plt.subplots(figsize=(8, 5))
    r, m = trial["rest"], trial["motion"]
    ax.plot(r["freqs"], 10 * np.log10(r["power"] + 1e-20), label="rest", alpha=0.8)
    ax.plot(m["freqs"], 10 * np.log10(m["power"] + 1e-20), label="motion", alpha=0.8)
    ax.set_xlim(TONE_FREQ - 500, TONE_FREQ + 500)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Power (dB)")
    ax.set_title(f"Trial {trial['trial_num']}: rest {r['bins']} bins vs motion {m['bins']} bins "
                 f"(+{trial['increase_bins']} bins, ~{trial['increase_hz']:.1f}Hz)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out = PLOTS_DIR / f"trial_{trial['trial_num']}_spectrum.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def save_summary_plot(best_trial, rest_trials):
    fig, ax = plt.subplots(figsize=(8, 5))
    r, m = best_trial["rest"], best_trial["motion"]
    ax.plot(r["freqs"], 10 * np.log10(r["power"] + 1e-20), label="rest (in-trial)", linewidth=2)
    ax.plot(m["freqs"], 10 * np.log10(m["power"] + 1e-20), label="motion", linewidth=2)
    if rest_trials:
        avg_rest_power = np.mean([rt["power"] for rt in rest_trials], axis=0)
        ax.plot(rest_trials[0]["freqs"], 10 * np.log10(avg_rest_power + 1e-20),
                label="rest baseline (dedicated trials, avg)", linestyle="--", alpha=0.7)
    ax.set_xlim(TONE_FREQ - 500, TONE_FREQ + 500)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Power (dB)")
    ax.set_title(f"Best motion trial ({best_trial['trial_num']}): "
                 f"+{best_trial['increase_bins']} bins (~{best_trial['increase_hz']:.1f}Hz)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out = PLOTS_DIR / "summary_comparison.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def write_results_md(motion_trials, rest_trials, passing, verdict, ambient_log=None):
    ambient_log = ambient_log or []
    lines = []
    lines.append("# Experiment 1 Results: Signal Existence Check\n")
    lines.append(f"Sample rate: {FS}Hz, tone: {TONE_FREQ/1000:.1f}kHz, "
                 f"FFT: {N_FFT}-point Hamming, bin resolution: ~{BIN_HZ:.2f}Hz/bin.\n")
    lines.append(f"Go/no-go bar: >= {PASS_BINS_INCREASE} bins (~{PASS_BINS_INCREASE*BIN_HZ:.0f}Hz) "
                 f"bandwidth increase during motion, in >= {PASS_MIN_MOTION_TRIALS}/{N_MOTION_TRIALS} trials, "
                 f"with rest baseline <= {PASS_REST_BASELINE_MAX_BINS} bins.\n")

    lines.append("## Motion trials\n")
    for t in motion_trials:
        status = "PASS" if t["increase_bins"] >= PASS_BINS_INCREASE else "FAIL"
        suspect_tag = "  **[SUSPECT: elevated rest-segment noise]**" if t.get("suspect") else ""
        lines.append(f"- Trial {t['trial_num']}: rest {t['rest']['bins']} bins, "
                     f"motion {t['motion']['bins']} bins -> "
                     f"**{t['increase_bins']} bins (~{t['increase_hz']:.1f}Hz)** above rest baseline "
                     f"[{status}]{suspect_tag}")
    lines.append("")

    lines.append("## Rest baseline trials (dedicated)\n")
    for i, rt in enumerate(rest_trials, 1):
        lines.append(f"- Rest trial {i}: {rt['bins']} bins (~{rt['hz']:.1f}Hz)")
    lines.append("")

    n_pass = sum(1 for t in motion_trials if t["increase_bins"] >= PASS_BINS_INCREASE)
    lines.append("## Summary\n")
    lines.append(f"{n_pass}/{len(motion_trials)} motion trials passed (>= {PASS_BINS_INCREASE} bins increase).\n")

    pass_vals = [t["increase_bins"] for t in motion_trials if t["increase_bins"] >= PASS_BINS_INCREASE]
    if pass_vals:
        lines.append(f"Passing trials ranged from {min(pass_vals)} to {max(pass_vals)} bins above baseline.\n")
        margin_notes = []
        for t in motion_trials:
            if t["increase_bins"] >= PASS_BINS_INCREASE:
                comfort = "comfortable" if t["increase_bins"] >= PASS_BINS_INCREASE * 1.5 else "marginal"
                margin_notes.append(f"trial {t['trial_num']}: {t['increase_bins']} bins ({comfort})")
        lines.append("Margins: " + "; ".join(margin_notes) + ".\n")

    rest_bins_vals = [rt["bins"] for rt in rest_trials]
    rest_avg = np.mean(rest_bins_vals) if rest_bins_vals else float("nan")
    rest_ok = all(b <= PASS_REST_BASELINE_MAX_BINS for b in rest_bins_vals) if rest_bins_vals else False
    lines.append(f"Rest baseline bins: {rest_bins_vals} (avg {rest_avg:.1f}), "
                 f"bar <= {PASS_REST_BASELINE_MAX_BINS} bins: {'MET' if rest_ok else 'NOT MET'}.\n")

    lines.append("## Data quality\n")
    retry_count = sum(1 for a in ambient_log if a["attempts"] > 1 or not a["passed"])
    still_noisy_count = sum(1 for a in ambient_log if not a["passed"])
    suspect_count = sum(1 for t in motion_trials if t.get("suspect"))
    lines.append(f"- Standalone rest-baseline bins (clean reference): {rest_bins_vals} "
                 f"(avg {rest_avg:.1f} bins) — every other trial is compared against this.")
    lines.append(f"- Trials that triggered an ambient-noise retry: {retry_count}/{len(ambient_log)}.")
    lines.append(f"- Trials still above the ambient threshold after {AMBIENT_MAX_ATTEMPTS} attempts "
                 f"(proceeded anyway, logged): {still_noisy_count}.")
    lines.append(f"- Motion trials flagged [SUSPECT: elevated rest-segment noise] "
                 f"(internal rest bins > {SUSPECT_REST_MULTIPLIER:.0f}x standalone rest-baseline avg): "
                 f"{suspect_count}/{len(motion_trials)}.")
    if ambient_log:
        lines.append("")
        lines.append("Ambient log detail:")
        for a in ambient_log:
            status = "OK" if a["passed"] else "STILL NOISY"
            lines.append(f"  - {a['label']}: {a['attempts']} attempt(s), "
                         f"final {a['final_db']:.1f}dB [{status}]")
    lines.append("")

    lines.append(f"## Verdict: {verdict}\n")

    RESULTS_MD.write_text("\n".join(lines), encoding="utf-8")
    return RESULTS_MD


def main():
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Experiment 1: Signal Existence Check")
    print(f"Default output/input devices: {sd.query_devices(kind='output')['name']} / "
          f"{sd.query_devices(kind='input')['name']}")
    input("Press Enter when ready to begin (this is the only manual pause; "
          "all subsequent trials are auto-timed)...")

    AMBIENT_LOG.clear()

    rest_trials = []
    for i in range(1, N_REST_TRIALS + 1):
        rest_trials.append(run_rest_trial(i))

    rest_baseline_avg_bins = np.mean([rt["bins"] for rt in rest_trials])

    motion_trials = []
    for i in range(1, N_MOTION_TRIALS + 1):
        motion_trials.append(run_motion_trial(i, rest_baseline_avg_bins=rest_baseline_avg_bins))

    for t in motion_trials:
        p = save_trial_plot(t)
        print(f"Saved {p}")

    best_trial = max(motion_trials, key=lambda t: t["increase_bins"])
    summary_path = save_summary_plot(best_trial, rest_trials)
    print(f"Saved {summary_path}")

    n_pass = sum(1 for t in motion_trials if t["increase_bins"] >= PASS_BINS_INCREASE)
    rest_ok = all(rt["bins"] <= PASS_REST_BASELINE_MAX_BINS for rt in rest_trials)
    verdict = "GO" if (n_pass >= PASS_MIN_MOTION_TRIALS and rest_ok) else "NO-GO"

    print(f"\n{'='*50}")
    print(f"VERDICT: {verdict} ({n_pass}/{N_MOTION_TRIALS} motion trials passed, "
          f"rest baseline bar {'met' if rest_ok else 'NOT met'})")
    print(f"{'='*50}")

    results_path = write_results_md(motion_trials, rest_trials, n_pass, verdict, ambient_log=AMBIENT_LOG)
    print(f"Wrote {results_path}")


if __name__ == "__main__":
    main()
