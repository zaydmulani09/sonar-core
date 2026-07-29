# Experiment 1 Results: Signal Existence Check

## Final Summary

**Verdict: NO-GO — confirmed across two independent threshold methodologies.**

P1 was tested exhaustively before this verdict was finalized: the original
spec's -3dB threshold across four independent runs, close-range/fast
push-pull motion, ambient-noise gating, and a physics-motivated -25dB
threshold retest. Neither methodology found a usable signal.

**-3dB threshold (original spec bar), across all runs:**

| Run | Conditions | Motion trials passing (>= 4 bins) |
|---|---|---|
| 1 | Noisy room | 0/5 |
| 2 | Quiet room | 2/5 |
| 3 | Ambient-noise-gated | 0/5 |
| 4 | Close-range / fast-motion | 1/5 |

Best case (run 2) never approached the required 4/5 bar.

**-25dB threshold retest (physics-motivated: direct path dominates the
peak at -3dB, reflected path off a hand was hypothesized to be a weaker
sideband 20-30dB down):** the -25dB threshold **saturated the entire
±500Hz search window uniformly — 46/46 bins, identical in both the rest
and motion segments.** This is not a detection of a weak reflected
signal; it means the noise floor itself sits within 25dB of peak
amplitude across the whole search band on this hardware, so the threshold
picked up ambient/direct-path noise everywhere rather than isolating a
motion-specific sideband. Widening the sensitivity didn't reveal a hidden
signal — it just proved there's no clean margin between the carrier peak
and the surrounding noise floor to detect one in.

**Carrier signal:** confirmed present and stable in every single trial
across all runs, measured at ~-66 to -67dB via the per-trial `[diag]`
signal check. This rules out a dead or marginal signal path — tone
generation, playback, and mic capture all work correctly.

**Conclusion:** the Doppler-reflected signal off a hand, if present at
all on this hardware, is not distinguishable from the ambient/direct-path
noise floor at any threshold tested — from strict (-3dB) through
deliberately loose (-25dB).

Per the original spec (Section 8): *"If Experiment 1 fails cleanly and
consistently, this project should stop here rather than proceed on
hope."* This is that condition, well-bracketed by two independent
methodologies rather than a single ambiguous run — stopping here is
correct, not premature.

**Scope of this NO-GO:** a second physical device (different
laptop/speaker/mic combination) was never tested. This verdict applies to
**this specific laptop's hardware**, not to the SoundWave technique in
general. Whether the method works on different hardware remains an open
question.

---

## Method

Sample rate: 44100Hz, tone: 19.0kHz, FFT: 2048-point Hamming, bin resolution: ~21.53Hz/bin.

Go/no-go bar: >= 4 bins (~86Hz) bandwidth increase during motion, in >= 4/5 trials, with rest baseline <= 2 bins.

## Motion trials

- Trial 1: rest 2 bins, motion 2 bins -> **0 bins (~0.0Hz)** above rest baseline [FAIL]
- Trial 2: rest 16 bins, motion 3 bins -> **-13 bins (~-279.9Hz)** above rest baseline [FAIL]
- Trial 3: rest 2 bins, motion 2 bins -> **0 bins (~0.0Hz)** above rest baseline [FAIL]
- Trial 4: rest 2 bins, motion 3 bins -> **1 bins (~21.5Hz)** above rest baseline [FAIL]
- Trial 5: rest 2 bins, motion 11 bins -> **9 bins (~193.8Hz)** above rest baseline [PASS]

## Rest baseline trials (dedicated)

- Rest trial 1: 2 bins (~43.1Hz)
- Rest trial 2: 2 bins (~43.1Hz)

## Summary

1/5 motion trials passed (>= 4 bins increase).

Passing trials ranged from 9 to 9 bins above baseline.

Margins: trial 5: 9 bins (comfortable).

Rest baseline bins: [np.int64(2), np.int64(2)] (avg 2.0), bar <= 2 bins: MET.

## Verdict: NO-GO
