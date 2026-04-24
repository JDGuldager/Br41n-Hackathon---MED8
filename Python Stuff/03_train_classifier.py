import numpy as np
import joblib

from scipy.signal import butter, filtfilt
from mne.decoding import CSP

from sklearn.pipeline import Pipeline
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import FunctionTransformer

DATA_FILE = "mi_trials_left_right.npz"
MODEL_FILE = "mi_csp_lda.joblib"

LOWCUT = 8.0
HIGHCUT = 30.0

def bandpass_epochs(X, fs, lowcut=LOWCUT, highcut=HIGHCUT):
    nyq = fs / 2.0
    b, a = butter(4, [lowcut / nyq, highcut / nyq], btype="bandpass")
    return filtfilt(b, a, X, axis=-1)

def main():
    data = np.load(DATA_FILE, allow_pickle=True)

    X = data["X"]
    y = data["y"]
    fs = int(data["fs"])

    print("Loaded X:", X.shape)
    print("Loaded y:", y.shape)

    X = bandpass_epochs(X, fs)

    clf = Pipeline([
        ("csp", CSP(n_components=4, reg="ledoit_wolf", log=True, norm_trace=False)),
        ("lda", LinearDiscriminantAnalysis())
    ])

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(clf, X, y, cv=cv)

    print("Cross-validation scores:", scores)
    print("Mean accuracy:", scores.mean())

    clf.fit(X, y)

    payload = {
        "model": clf,
        "fs": fs,
        "lowcut": LOWCUT,
        "highcut": HIGHCUT,
        "n_channels": X.shape[1],
        "label_names": ["left", "right"]
    }

    joblib.dump(payload, MODEL_FILE)
    print("Saved model:", MODEL_FILE)

if __name__ == "__main__":
    main()