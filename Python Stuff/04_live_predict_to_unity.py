import time
import socket
import numpy as np
import joblib

from scipy.signal import butter, filtfilt
from pylsl import resolve_byprop, StreamInlet

MODEL_FILE = "mi_csp_lda.joblib"

UNITY_IP = "127.0.0.1"
UNITY_PORT = 12346

WINDOW_SECONDS = 2.0
STEP_SECONDS = 0.25
CONFIDENCE_THRESHOLD = 0.60

# Jaw squeeze toggle settings
JAW_WINDOW_SECONDS = 0.20
JAW_BASELINE_SECONDS = 5.0
JAW_THRESHOLD_MULTIPLIER = 8.0
JAW_COOLDOWN_SECONDS = 1.0


def bandpass_window(x, fs, lowcut, highcut):
    nyq = fs / 2.0
    b, a = butter(4, [lowcut / nyq, highcut / nyq], btype="bandpass")
    return filtfilt(b, a, x, axis=-1)


def bandpower_avg(buffer, fs, lowcut, highcut):
    """
    buffer shape: channels x samples
    returns average power across all channels
    """
    X = buffer[np.newaxis, :, :]
    Xf = bandpass_window(X, fs, lowcut, highcut)[0]
    power_per_channel = np.mean(Xf ** 2, axis=1)
    return float(np.mean(power_per_channel))


def get_lsl_inlet():
    print("Looking for Unicorn Data LSL stream...")
    streams = resolve_byprop("type", "Data", timeout=10)

    if len(streams) == 0:
        raise RuntimeError("No Unicorn Data LSL stream found.")

    inlet = StreamInlet(streams[0])

    print("Connected to:", streams[0].name())
    print("Type:", streams[0].type())
    print("Channels:", streams[0].channel_count())
    print("Rate:", streams[0].nominal_srate())

    return inlet


def send_udp(udp, msg):
    udp.sendto(msg.encode("ascii"), (UNITY_IP, UNITY_PORT))


def compute_jaw_score(buffer, jaw_samples):
    recent = buffer[:, -jaw_samples:]
    diff = np.diff(recent, axis=1)
    return float(np.mean(np.abs(diff)))


def main():
    payload = joblib.load(MODEL_FILE)

    model = payload["model"]
    fs = int(payload["fs"])
    lowcut = float(payload["lowcut"])
    highcut = float(payload["highcut"])
    n_channels = int(payload["n_channels"])

    window_samples = int(WINDOW_SECONDS * fs)
    step_samples = int(STEP_SECONDS * fs)
    jaw_samples = int(JAW_WINDOW_SECONDS * fs)
    jaw_baseline_samples_needed = int(JAW_BASELINE_SECONDS / STEP_SECONDS)

    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    inlet = get_lsl_inlet()

    buffer = np.zeros((n_channels, window_samples), dtype=np.float64)
    sample_counter = 0

    jaw_baseline_scores = []
    jaw_baseline = None
    jaw_mad = None
    last_jaw_toggle_time = 0.0

    print("Live prediction started.")
    print("Commands:")
    print("MOVE:-1 = left")
    print("MOVE:0  = idle")
    print("MOVE:1  = right")
    print("TOGGLE  = switch mode")
    print()
    print("Also sending:")
    print("CONF, ALPHA, BETA, GAMMA")
    print()
    print("Stay relaxed for the first few seconds for jaw baseline.")
    print("Do NOT squeeze your jaw during baseline calibration.")
    print()

    while True:
        sample, timestamp = inlet.pull_sample(timeout=1.0)

        if sample is None:
            continue

        x = np.array(sample[:n_channels], dtype=np.float64)

        buffer = np.roll(buffer, -1, axis=1)
        buffer[:, -1] = x

        sample_counter += 1

        if sample_counter < window_samples:
            continue

        if sample_counter % step_samples != 0:
            continue

        # -------------------------
        # Jaw squeeze detection
        # -------------------------
        jaw_score = compute_jaw_score(buffer, jaw_samples)

        if jaw_baseline is None:
            jaw_baseline_scores.append(jaw_score)

            print(
                f"Calibrating jaw baseline... "
                f"{len(jaw_baseline_scores)}/{jaw_baseline_samples_needed}"
            )

            if len(jaw_baseline_scores) >= jaw_baseline_samples_needed:
                baseline_array = np.array(jaw_baseline_scores)

                jaw_baseline = float(np.median(baseline_array))
                jaw_mad = float(np.median(np.abs(baseline_array - jaw_baseline)))

                if jaw_mad < 1e-9:
                    jaw_mad = max(jaw_baseline * 0.1, 1e-9)

                print()
                print(
                    f"Jaw baseline ready: "
                    f"baseline={jaw_baseline:.6f}, MAD={jaw_mad:.6f}"
                )
                print(
                    f"Jaw threshold = "
                    f"{jaw_baseline + JAW_THRESHOLD_MULTIPLIER * jaw_mad:.6f}"
                )
                print()

            continue

        now = time.time()
        jaw_threshold = jaw_baseline + JAW_THRESHOLD_MULTIPLIER * jaw_mad

        if jaw_score > jaw_threshold and now - last_jaw_toggle_time > JAW_COOLDOWN_SECONDS:
            send_udp(udp, "TOGGLE")
            last_jaw_toggle_time = now

            print(
                f"JAW TOGGLE detected | "
                f"score={jaw_score:.6f}, threshold={jaw_threshold:.6f}"
            )

            continue

        # -------------------------
        # Alpha / Beta / Gamma values
        # -------------------------
        alpha_avg = bandpower_avg(buffer, fs, 8.0, 12.0)
        beta_avg = bandpower_avg(buffer, fs, 13.0, 30.0)
        gamma_avg = bandpower_avg(buffer, fs, 30.0, 45.0)

        # -------------------------
        # Motor imagery prediction
        # -------------------------
        X = buffer[np.newaxis, :, :]
        Xf = bandpass_window(X, fs, lowcut, highcut)

        probs = model.predict_proba(Xf)[0]
        pred = int(np.argmax(probs))
        conf = float(np.max(probs))

        if conf < CONFIDENCE_THRESHOLD:
            cmd = 0
        else:
            cmd = -1 if pred == 0 else 1

        message = (
            f"MOVE:{cmd};"
            f"CONF:{conf:.3f};"
            f"ALPHA:{alpha_avg:.6f};"
            f"BETA:{beta_avg:.6f};"
            f"GAMMA:{gamma_avg:.6f}"
        )

        send_udp(udp, message)

        label = "LEFT" if pred == 0 else "RIGHT"

        print(
            f"pred={label}, conf={conf:.2f}, cmd={cmd}, "
            f"alpha={alpha_avg:.6f}, beta={beta_avg:.6f}, gamma={gamma_avg:.6f}, "
            f"jaw={jaw_score:.6f}/{jaw_threshold:.6f}"
        )

        time.sleep(0.001)


if __name__ == "__main__":
    main()