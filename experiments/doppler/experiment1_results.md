# Experiment 1 Results: Signal Existence Check

## Final Summary

**Overall verdict: NO-GO.**

The 19kHz pilot carrier reached the microphone consistently and reliably
across every run — measured at roughly **-66 to -67dB**, stable within
~1dB across dozens of trials via the per-trial `[diag]` signal check. This
confirms the signal path end-to-end: tone generation, simultaneous
play/record, and mic capture all work correctly on this hardware. The
failure is not a dead or marginal signal.

However, the motion-vs-rest bandwidth increase never came close to the
go/no-go bar (>= 4 bins in >= 4/5 trials) across **four independent full
runs**, run under progressively more controlled conditions:

| Run | Conditions | Motion trials passing (>= 4 bins) |
|---|---|---|
| 1 | Noisy room | 0/5 |
| 2 | Quiet room | 2/5 |
| 3 | Ambient-noise-gated (post `09f2d21`) | 0/5 |
| 4 | Close-range / fast-motion | 1/5 |

No run approached the required 4/5 threshold, including the final
close-range/fast-motion attempt, which was the most favorable condition
tried.

Per the original spec (Section 8): *"If Experiment 1 fails cleanly and
consistently, this project should stop here rather than proceed on hope."*
This is that outcome. The signal path works; the Doppler-bandwidth effect
this method depends on is not recoverable on this hardware at a level
usable for motion detection.

**Untested variable:** a second device was not available to test whether
this result is specific to this laptop's speaker/mic combination or more
general to consumer laptop hardware. That question is open.

**Note on artifacts:** the four trial runs referenced above were executed
locally and were not synced back into this repo — no `.wav` recordings
(gitignored by design) or `plots/*.png` files exist in this repository.
The numbers in this summary are as reported after each run.

---

## Method

Sample rate: 44100Hz, tone: 19.0kHz, FFT: 2048-point Hamming, bin
resolution: ~21.53Hz/bin.

Go/no-go bar: >= 4 bins (~86Hz) bandwidth increase during motion, in >= 4/5
trials, with rest baseline <= 2 bins.

Auto-timer trial design: each motion trial recorded continuously through a
2s rest phase then a 3s motion (hand-wave) phase, with a 300ms guard band
discarded at the transition before analysis (see `09f2d21`,
`f611b17`). An ambient-noise pre-check (mic-only sample, retry up to 3x if
room noise exceeded -40dBFS RMS) gated recording start from run 3 onward.

## Verdict: NO-GO

Project stops here per the spec's hard gate. No further prompts (P2+) proceed.
