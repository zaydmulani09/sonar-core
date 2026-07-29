# Experiment 1 Results: Signal Existence Check

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
