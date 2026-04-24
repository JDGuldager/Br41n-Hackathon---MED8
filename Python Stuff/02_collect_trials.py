import time
import random
import numpy as np
from pylsl import resolve_byprop, StreamInlet

FS = 250
N_CHANNELS = 8

REST_SECONDS = 2
CUE_SECONDS = 1
IMAGERY_SECONDS = 4

TRIALS_PER_CLASS = 30

OUTPUT_FILE = "mi_trials_left_right.npz"

def get_lsl_inlet():
    print("Looking for Unicorn LSL stream...")
    streams = resolve_byprop("type", "Data", timeout=10)

    if len(streams) == 0:
        raise RuntimeError("No Unicorn Data LSL stream found.")

    inlet = StreamInlet(streams[0])
    print("Connected to:", streams[0].name())
    print("Type:", streams[0].type())
    print("Channels:", streams[0].channel_count())
    print("Rate:", streams[0].nominal_srate())
    return inlet

def pull_samples(inlet, seconds):
    target_samples = int(seconds * FS)
    data = []

    while len(data) < target_samples:
        sample, timestamp = inlet.pull_sample(timeout=1.0)

        if sample is not None:
            data.append(sample[:N_CHANNELS])

    arr = np.array(data, dtype=np.float64).T
    return arr

def countdown(label, seconds):
    print(label)
    for i in range(seconds, 0, -1):
        print(i)
        time.sleep(1)

def main():
    inlet = get_lsl_inlet()

    trials = []
    labels = []

    schedule = ["left"] * TRIALS_PER_CLASS + ["right"] * TRIALS_PER_CLASS
    random.shuffle(schedule)

    print()
    print("Motor imagery instructions:")
    print("- LEFT = imagine repeatedly squeezing your LEFT hand")
    print("- RIGHT = imagine repeatedly squeezing your RIGHT hand")
    print("- Do not actually move. Keep jaw, face, shoulders relaxed.")
    print()

    input("Press ENTER to start...")

    for idx, cue in enumerate(schedule):
        print()
        print(f"Trial {idx + 1}/{len(schedule)}")

        countdown("REST", REST_SECONDS)

        print()
        print("====================================")
        print(f"          THINK {cue.upper()}")
        print("====================================")
        time.sleep(CUE_SECONDS)

        print("Imagery window recording...")
        eeg = pull_samples(inlet, IMAGERY_SECONDS)

        trials.append(eeg)
        labels.append(0 if cue == "left" else 1)

        print("Saved trial:", cue)

    X = np.stack(trials, axis=0)
    y = np.array(labels, dtype=np.int64)

    np.savez(
        OUTPUT_FILE,
        X=X,
        y=y,
        fs=FS,
        n_channels=N_CHANNELS,
        label_names=np.array(["left", "right"])
    )

    print()
    print("Saved:", OUTPUT_FILE)
    print("X shape:", X.shape)
    print("y shape:", y.shape)

if __name__ == "__main__":
    main()