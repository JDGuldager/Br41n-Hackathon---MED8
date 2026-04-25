import numpy as np
from scipy import signal
import soundfile as sf

# Global settings
BPM = 138
SAMPLE_RATE = 44100
BARS = 4
BEATS_PER_BAR = 4
KEY = 'A_minor'

beat_duration = 60.0 / BPM
loop_duration = BARS * BEATS_PER_BAR * beat_duration
num_samples = int(loop_duration * SAMPLE_RATE)

# A minor related notes
NOTES = {
    'A0': 27.5,
    'A1': 55.0, 'B1': 61.74, 'C2': 65.41, 'D2': 73.42, 'E2': 82.41,
    'A2': 110.0, 'B2': 123.47, 'C3': 130.81, 'D3': 146.83, 'E3': 164.81,
    'A3': 220.0, 'C4': 261.63, 'E4': 329.63,
}


# ----------------------------------------------------------------------
# Utility
# ----------------------------------------------------------------------

def normalize(audio, db=-3.0):
    """Normalize audio to target dBFS."""
    target = 10 ** (db / 20.0)
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio * (target / peak)
    return audio


def generate_envelope(attack, decay, sustain, release, duration, sr=SAMPLE_RATE):
    """Simple ADSR envelope (time in seconds)."""
    total_samples = int(duration * sr)
    env = np.zeros(total_samples, dtype=np.float32)

    a_s = int(attack * sr)
    d_s = int(decay * sr)
    r_s = int(release * sr)

    # clip to total_samples
    a_s = max(0, min(a_s, total_samples))
    d_s = max(0, min(d_s, total_samples - a_s))
    r_s = max(0, min(r_s, total_samples))

    s_s = total_samples - a_s - d_s - r_s
    s_s = max(0, s_s)

    # Attack
    if a_s > 0:
        env[:a_s] = np.linspace(0.0, 1.0, a_s, endpoint=False)
    # Decay
    if d_s > 0:
        env[a_s:a_s + d_s] = np.linspace(1.0, sustain, d_s, endpoint=False)
    # Sustain
    if s_s > 0:
        env[a_s + d_s:a_s + d_s + s_s] = sustain
    # Release
    if r_s > 0:
        env[-r_s:] = np.linspace(sustain, 0.0, r_s, endpoint=False)

    return env


def apply_lowpass_filter(audio, cutoff, sr=SAMPLE_RATE, order=4):
    nyq = sr / 2.0
    cutoff = min(float(cutoff), nyq - 100.0)
    sos = signal.butter(order, cutoff / nyq, btype='low', output='sos')
    return signal.sosfilt(sos, audio)


def apply_highpass_filter(audio, cutoff, sr=SAMPLE_RATE, order=4):
    nyq = sr / 2.0
    cutoff = min(float(cutoff), nyq - 100.0)
    sos = signal.butter(order, cutoff / nyq, btype='high', output='sos')
    return signal.sosfilt(sos, audio)


def apply_bandpass_filter(audio, lowcut, highcut, sr=SAMPLE_RATE, order=4):
    nyq = sr / 2.0
    low = float(lowcut) / nyq
    high = min(float(highcut) / nyq, 0.99)
    sos = signal.butter(order, [low, high], btype='band', output='sos')
    return signal.sosfilt(sos, audio)


def svf_filter(x, cutoff_env, Q=1.0, mode='lp', sr=SAMPLE_RATE):
    """
    State-variable filter (Chamberlin style) with time-varying cutoff.
    Q is the "filter Q" (resonance); higher = more resonance.
    mode: 'lp' (lowpass), 'bp', 'hp'.
    """
    x = np.asarray(x, dtype=float)
    n = x.shape[0]

    if np.isscalar(cutoff_env):
        cutoff = np.full(n, float(cutoff_env), dtype=float)
    else:
        cutoff = np.asarray(cutoff_env, dtype=float)
        if cutoff.shape[0] != n:
            raise ValueError("cutoff_env length must match signal length")

    cutoff = np.clip(cutoff, 20.0, sr / 2.0 - 100.0)
    f = 2.0 * np.sin(np.pi * cutoff / sr)
    f = np.clip(f, 0.0, 0.999)

    q = 1.0 / max(Q, 1e-6)
    low = 0.0
    band = 0.0
    out = np.zeros_like(x)

    for i in range(n):
        high = x[i] - low - q * band
        band = band + f[i] * high
        band = np.tanh(band)  # gentle internal saturation
        low = low + f[i] * band

        if mode == 'lp':
            out[i] = low
        elif mode == 'bp':
            out[i] = band
        else:  # 'hp'
            out[i] = high

    return out


def onepole_lowpass(x, cutoff, sr=SAMPLE_RATE):
    """Simple 1-pole lowpass for smoothing / anti-aliasing."""
    x = np.asarray(x, dtype=float)
    rc = 1.0 / (2.0 * np.pi * float(cutoff))
    dt = 1.0 / sr
    alpha = dt / (rc + dt)

    y = np.zeros_like(x)
    y[0] = alpha * x[0]
    for i in range(1, x.shape[0]):
        y[i] = y[i - 1] + alpha * (x[i] - y[i - 1])
    return y


# ----------------------------------------------------------------------
# DRUMS
# ----------------------------------------------------------------------

def generate_kick_909(alt=False):
    """909-style kick: sine with pitch drop and exponential decay.
       alt=True: shorter, higher, with click – clearly different sound."""
    audio = np.zeros(num_samples)

    if not alt:
        kick_duration = 0.5
        start_f, end_f = 80.0, 30.0
        decay_amount = 8.0
        add_click = False
        sat_amount = 1.0
    else:
        kick_duration = 0.18
        start_f, end_f = 120.0, 40.0
        decay_amount = 20.0
        add_click = True
        sat_amount = 1.8

    kick_samples = int(kick_duration * SAMPLE_RATE)
    t = np.arange(kick_samples) / SAMPLE_RATE

    # Exponential pitch glide start_f -> end_f
    k = np.log(end_f / start_f) / kick_duration
    freq = start_f * np.exp(k * t)
    phase = 2.0 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    kick = np.sin(phase)

    # Exponential amplitude decay
    env = np.exp(-decay_amount * t)
    kick *= env

    if add_click:
        click_len = int(0.004 * SAMPLE_RATE)
        click = np.random.randn(click_len) * 0.6
        click = apply_highpass_filter(click, 5000.0)
        click_env = np.exp(-np.linspace(0, 1, click_len) * 60.0)
        click *= click_env
        kick[:click_len] += click
        kick = np.tanh(sat_amount * kick)

    # Place kick on every beat
    for beat in range(BARS * BEATS_PER_BAR):
        start = int(beat * beat_duration * SAMPLE_RATE)
        end = min(start + kick_samples, num_samples)
        audio[start:end] += kick[:end - start]

    return normalize(audio)


def generate_hihat_closed():
    audio = np.zeros(num_samples)
    hat_duration = 0.03
    hat_samples = int(hat_duration * SAMPLE_RATE)

    t = np.arange(hat_samples) / SAMPLE_RATE
    env = np.exp(-t * 100.0)

    for i in range(BARS * BEATS_PER_BAR * 4):  # 16th notes
        start = int(i * (beat_duration / 4.0) * SAMPLE_RATE)
        noise = np.random.randn(hat_samples)
        hat = apply_highpass_filter(noise, 8000.0)
        hat *= env
        end = min(start + hat_samples, num_samples)
        audio[start:end] += hat[:end - start]

    return normalize(audio)


def generate_hihat_open():
    audio = np.zeros(num_samples)
    hat_duration = 0.2
    hat_samples = int(hat_duration * SAMPLE_RATE)
    t = np.arange(hat_samples) / SAMPLE_RATE
    env = np.exp(-t * 15.0)

    # Shuffled 8th note pattern
    for i in range(BARS * BEATS_PER_BAR * 2):  # 8th notes
        if i % 2 == 1:
            offset = beat_duration * 0.3 / 2.0
        else:
            offset = 0.0
        start_time = i * (beat_duration / 2.0) + offset
        start = int(start_time * SAMPLE_RATE)

        noise = np.random.randn(hat_samples)
        hat = apply_highpass_filter(noise, 6000.0)
        hat *= env * 0.6

        end = min(start + hat_samples, num_samples)
        audio[start:end] += hat[:end - start]

    return normalize(audio)


def generate_clap():
    audio = np.zeros(num_samples)
    clap_duration = 0.05
    clap_samples = int(clap_duration * SAMPLE_RATE)
    t = np.arange(clap_samples) / SAMPLE_RATE
    env = np.exp(-t * 40.0)

    for bar in range(BARS):
        for beat in [1, 3]:  # beats 2 and 4
            start = int((bar * BEATS_PER_BAR + beat) * beat_duration * SAMPLE_RATE)

            clap = np.zeros(clap_samples)
            for i in range(3):
                delay = int(i * 0.01 * SAMPLE_RATE)
                if delay >= clap_samples:
                    continue
                noise = np.random.randn(clap_samples - delay) * 0.5
                clap[delay:] += noise

            clap = apply_bandpass_filter(clap, 1000.0, 3000.0)
            clap *= env

            end = min(start + clap_samples, num_samples)
            audio[start:end] += clap[:end - start]

    return normalize(audio)


# ----------------------------------------------------------------------
# BASSLINE 303
# ----------------------------------------------------------------------

def generate_303_bass(note_pattern, envelope_speed='slow', octave_shift=0, portamento=False):
    """
    TB-303-style bass:
    saw oscillator -> custom resonant low-pass (SVF, Q~15) + envelope.
    """
    audio = np.zeros(num_samples)

    notes_per_bar = len(note_pattern)
    bar_duration = BEATS_PER_BAR * beat_duration
    note_duration = bar_duration / notes_per_bar

    if envelope_speed == 'slow':
        env_decay = 2.0
        env_amount = 2200.0
    elif envelope_speed == 'fast':
        env_decay = 12.0
        env_amount = 2600.0
    else:
        env_decay = 5.0
        env_amount = 1800.0
    base_cutoff = 300.0

    prev_freq = None

    for bar in range(BARS):
        for i, note_name in enumerate(note_pattern):
            start_time = (bar * notes_per_bar + i) * note_duration
            start_sample = int(start_time * SAMPLE_RATE)
            if start_sample >= num_samples:
                continue

            note_samples = int(note_duration * SAMPLE_RATE)
            end_sample = min(start_sample + note_samples, num_samples)
            this_note_samples = end_sample - start_sample

            t = np.arange(this_note_samples) / SAMPLE_RATE
            freq_nominal = NOTES[note_name] * (2 ** octave_shift)

            if portamento and prev_freq is not None:
                freq_line = np.linspace(prev_freq, freq_nominal, this_note_samples)
            else:
                freq_line = np.full(this_note_samples, freq_nominal)
            prev_freq = freq_nominal

            phase = 2.0 * np.pi * np.cumsum(freq_line) / SAMPLE_RATE
            osc = signal.sawtooth(phase)

            cutoff_env = base_cutoff + env_amount * np.exp(-env_decay * t)
            cutoff_env = np.clip(cutoff_env, 40.0, SAMPLE_RATE / 2.0 - 200.0)
            filtered = svf_filter(osc, cutoff_env, Q=15.0, mode='lp', sr=SAMPLE_RATE)
            filtered = np.tanh(1.2 * filtered)

            amp_env = generate_envelope(
                0.001,
                0.08 if envelope_speed == 'fast' else 0.12,
                0.65,
                0.05,
                this_note_samples / SAMPLE_RATE,
            )
            filtered *= amp_env

            audio[start_sample:end_sample] += filtered[:this_note_samples]

    return normalize(audio)


def generate_sub_bass():
    """Pure sine sub on A1, whole notes, no filter."""
    audio = np.zeros(num_samples)

    for bar in range(BARS):
        start = int(bar * BEATS_PER_BAR * beat_duration * SAMPLE_RATE)
        dur = BEATS_PER_BAR * beat_duration
        note_samples = int(dur * SAMPLE_RATE)
        end = min(start + note_samples, num_samples)
        this = end - start

        t = np.arange(this) / SAMPLE_RATE
        sine = np.sin(2.0 * np.pi * NOTES['A1'] * t)
        env = generate_envelope(0.01, 0.1, 0.9, 0.1, this / SAMPLE_RATE)
        sine *= env

        audio[start:end] += sine

    return normalize(audio)


# ----------------------------------------------------------------------
# PERCUSSION
# ----------------------------------------------------------------------

def generate_rimshot():
    """Brighter, snappier rimshot with a more interesting pattern."""
    audio = np.zeros(num_samples)
    rim_duration = 0.06
    rim_samples = int(rim_duration * SAMPLE_RATE)
    t = np.arange(rim_samples) / SAMPLE_RATE

    noise = np.random.randn(rim_samples)
    noise = apply_bandpass_filter(noise, 2000.0, 7000.0)
    tone = np.sin(2.0 * np.pi * 2200.0 * t) + 0.5 * np.sin(2.0 * np.pi * 3200.0 * t)
    rim = 0.7 * noise + 0.6 * tone

    env = (t / rim_duration) ** 0.3 * np.exp(-t * 60.0)
    rim *= env
    rim = np.tanh(2.0 * rim)

    pattern_times = []
    for bar in range(BARS):
        bar_start = bar * BEATS_PER_BAR * beat_duration
        pattern_times.extend([
            bar_start + 1.0 * beat_duration,      # beat 2
            bar_start + 1.75 * beat_duration,     # 16th before 3
            bar_start + 3.0 * beat_duration,      # beat 4
        ])

    for thit in pattern_times:
        start = int(thit * SAMPLE_RATE)
        end = min(start + rim_samples, num_samples)
        audio[start:end] += rim[:end - start]

    return normalize(audio)


def generate_conga():
    audio = np.zeros(num_samples)
    conga_duration = 0.15
    conga_samples = int(conga_duration * SAMPLE_RATE)
    t = np.arange(conga_samples) / SAMPLE_RATE

    freq = 200.0 * np.exp(-t * 10.0) + 150.0
    phase = 2.0 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    base = np.sin(phase)
    env = np.exp(-t * 15.0)
    base *= env

    for i in range(BARS * BEATS_PER_BAR * 2):  # 8ths, syncopated
        if i % 3 == 0:
            start = int(i * (beat_duration / 2.0) * SAMPLE_RATE)
            end = min(start + conga_samples, num_samples)
            audio[start:end] += base[:end - start]

    return normalize(audio)


def generate_cowbell():
    audio = np.zeros(num_samples)
    bell_duration = 0.1
    bell_samples = int(bell_duration * SAMPLE_RATE)
    t = np.arange(bell_samples) / SAMPLE_RATE
    bell = np.sin(2.0 * np.pi * 540.0 * t) + np.sin(2.0 * np.pi * 800.0 * t)
    env = np.exp(-t * 12.0)
    bell *= env

    for i in range(BARS * 2):  # half notes
        start = int(i * (BEATS_PER_BAR * beat_duration / 2.0) * SAMPLE_RATE)
        end = min(start + bell_samples, num_samples)
        audio[start:end] += 0.5 * bell[:end - start]

    return normalize(audio)


def generate_shaker():
    audio = np.zeros(num_samples)
    shaker_duration = 0.04
    shaker_samples = int(shaker_duration * SAMPLE_RATE)
    t = np.arange(shaker_samples) / SAMPLE_RATE
    env = np.exp(-t * 50.0)

    for i in range(BARS * BEATS_PER_BAR * 4):  # 16th notes
        start = int(i * (beat_duration / 4.0) * SAMPLE_RATE)
        noise = np.random.randn(shaker_samples)
        shaker = apply_bandpass_filter(noise, 4000.0, 10000.0)
        shaker *= env * 0.4
        end = min(start + shaker_samples, num_samples)
        audio[start:end] += shaker[:end - start]

    return normalize(audio)


# ----------------------------------------------------------------------
# SYNTH / PAD
# ----------------------------------------------------------------------

def generate_dark_pad():
    """Am pad with slow movement + reverb, less static in a 4-bar loop."""
    audio = np.zeros(num_samples)
    chord_notes = [NOTES['A2'], NOTES['C3'], NOTES['E3']]
    t = np.arange(num_samples) / SAMPLE_RATE

    for f in chord_notes:
        audio += 0.35 * np.sin(2.0 * np.pi * f * t)
        audio += 0.25 * signal.sawtooth(2.0 * np.pi * f * t)

    # Slight vibrato on one voice for movement
    vibrato = 0.1 * np.sin(2.0 * np.pi * 0.3 * t)
    audio += 0.15 * np.sin(2.0 * np.pi * (NOTES['A2'] + vibrato) * t)

    amp_env = generate_envelope(0.8, 1.0, 0.9, 0.7, loop_duration)
    audio *= amp_env

    # Slow filter LFO (one up-and-down over the loop)
    lfo = 0.5 * (1.0 - np.cos(2.0 * np.pi * t / loop_duration))
    cutoff_env = 500.0 + 2500.0 * lfo
    audio = svf_filter(audio, cutoff_env, Q=0.7, mode='lp', sr=SAMPLE_RATE)

    # Reverb (exponential IR)
    reverb_duration = 2.5
    rev_samples = int(reverb_duration * SAMPLE_RATE)
    ir_time = np.linspace(0.0, reverb_duration, rev_samples, endpoint=False)
    ir = np.exp(-ir_time * 2.5)
    ir *= (0.4 + 0.6 * np.random.rand(rev_samples))
    ir /= np.sum(ir)

    wet = np.convolve(audio, ir, mode='full')[:num_samples]
    audio = audio * 0.6 + wet * 0.9

    return normalize(audio)


def generate_acid_lead():
    audio = np.zeros(num_samples)
    lead_notes = ['A3', 'C4', 'E4', 'A3', 'C4', 'E4', 'D3', 'E3'] * BARS
    note_duration = beat_duration / 2.0  # 8ths

    for i, note_name in enumerate(lead_notes[:BARS * 8]):
        start = int(i * note_duration * SAMPLE_RATE)
        dur = note_duration * 0.7
        note_samples = int(dur * SAMPLE_RATE)
        end = min(start + note_samples, num_samples)
        this = end - start

        t = np.arange(this) / SAMPLE_RATE
        freq = NOTES[note_name]
        square = signal.square(2.0 * np.pi * freq * t)
        square = apply_lowpass_filter(square, 2000.0)
        env = generate_envelope(0.01, 0.05, 0.5, 0.1, dur)
        square *= env[:this]

        audio[start:end] += square

    return normalize(audio)


def generate_chord_stab():
    """Brighter, punchier chord stabs that cut through."""
    audio = np.zeros(num_samples)
    chord_freqs = [NOTES['A2'], NOTES['C3'], NOTES['E3']]
    stab_duration = 0.25
    stab_samples = int(stab_duration * SAMPLE_RATE)
    t = np.arange(stab_samples) / SAMPLE_RATE

    base = np.zeros(stab_samples)
    for f in chord_freqs:
        for det in [0.985, 1.0, 1.015]:
            base += signal.sawtooth(2.0 * np.pi * f * det * t)
    base /= 9.0

    noise = np.random.randn(stab_samples)
    noise = apply_highpass_filter(noise, 4000.0)
    noise_env = np.exp(-t * 80.0)
    base += 0.25 * noise * noise_env

    cutoff_env = np.linspace(3500.0, 5500.0, stab_samples)
    stab = svf_filter(base, cutoff_env, Q=0.9, mode='lp', sr=SAMPLE_RATE)

    amp_env = generate_envelope(0.005, 0.12, 0.0, 0.0, stab_duration)
    stab *= amp_env
    stab = np.tanh(1.4 * stab)

    # Pattern: beats 1, "and" of 2, and 4
    hit_positions = [0.0, 1.5, 3.0]  # in beats within bar
    for bar in range(BARS):
        bar_start = bar * BEATS_PER_BAR * beat_duration
        for hp in hit_positions:
            start = int((bar_start + hp * beat_duration) * SAMPLE_RATE)
            end = min(start + stab_samples, num_samples)
            audio[start:end] += stab[:end - start]

    return normalize(audio)


def generate_arp_synth():
    audio = np.zeros(num_samples)
    arp_pattern = ['A3', 'C4', 'E4', 'A3', 'D3', 'E3', 'A3', 'C4'] * BARS
    note_duration = beat_duration / 4.0  # 16ths

    for i, note_name in enumerate(arp_pattern[:BARS * 16]):
        start = int(i * note_duration * SAMPLE_RATE)
        dur = note_duration * 0.8
        note_samples = int(dur * SAMPLE_RATE)
        end = min(start + note_samples, num_samples)
        this = end - start

        t = np.arange(this) / SAMPLE_RATE
        freq = NOTES[note_name]
        square = signal.square(2.0 * np.pi * freq * t)
        square = apply_lowpass_filter(square, 3000.0)
        env = generate_envelope(0.005, 0.05, 0.4, 0.05, dur)
        square *= env[:this] * 0.6

        audio[start:end] += square

    return normalize(audio)


def generate_noise_sweep():
    """90s-style rising HPF noise sweep (fits 909/808 techno)."""
    t = np.arange(num_samples) / SAMPLE_RATE
    noise = np.random.randn(num_samples)

    cutoff_env = 400.0 + (9000.0 - 400.0) * (t / loop_duration)
    sweep = svf_filter(noise, cutoff_env, Q=1.2, mode='hp', sr=SAMPLE_RATE)

    amp_env = (t / loop_duration) ** 1.2  # rising volume
    sweep *= amp_env
    sweep = np.tanh(0.8 * sweep)

    return normalize(sweep)


def generate_reese_bass():
    """Reese bass with oversampling + smoothing to reduce digital harshness."""
    base_freq = NOTES['A1']
    os_factor = 2
    sr_os = SAMPLE_RATE * os_factor
    n_os = num_samples * os_factor
    t_os = np.arange(n_os) / sr_os

    lfo = np.sin(2.0 * np.pi * 0.2 * t_os) * 2.0
    detune = 5.0

    osc1 = signal.sawtooth(2.0 * np.pi * (base_freq + detune + lfo) * t_os)
    osc2 = signal.sawtooth(2.0 * np.pi * (base_freq - detune - lfo) * t_os)
    reese = 0.5 * (osc1 + osc2)

    reese = onepole_lowpass(reese, cutoff=600.0, sr=sr_os)
    reese = np.tanh(0.9 * reese)

    reese_ds = reese[::os_factor][:num_samples]

    env = generate_envelope(0.03, 0.25, 0.9, 0.25, loop_duration)
    reese_ds *= env

    return normalize(reese_ds)


# ----------------------------------------------------------------------
# Generate all loops
# ----------------------------------------------------------------------

print("Generating acid techno loops...")
print(f"Loop duration: {loop_duration:.3f}s, samples: {num_samples}")

# DRUMS
print("1. kick_909")
sf.write("01_kick_909.wav", generate_kick_909(alt=False), SAMPLE_RATE)

print("2. kick_909_alt (more punchy/short)")
sf.write("02_kick_909_alt.wav", generate_kick_909(alt=True), SAMPLE_RATE)

print("3. hihat_closed")
sf.write("03_hihat_closed.wav", generate_hihat_closed(), SAMPLE_RATE)

print("4. hihat_open")
sf.write("04_hihat_open.wav", generate_hihat_open(), SAMPLE_RATE)

print("5. clap")
sf.write("05_clap.wav", generate_clap(), SAMPLE_RATE)

# BASSLINE 303
print("6. acid_bass_slow")
slow_pattern = ['A1', 'A1', 'D2', 'E2']
sf.write("06_acid_bass_slow.wav",
         generate_303_bass(slow_pattern, envelope_speed='slow', octave_shift=0, portamento=False),
         SAMPLE_RATE)

print("7. acid_bass_fast")
fast_pattern = ['A1', 'C2', 'D2', 'E2', 'A1', 'E2', 'D2', 'C2']
sf.write("07_acid_bass_fast.wav",
         generate_303_bass(fast_pattern, envelope_speed='fast', octave_shift=0, portamento=False),
         SAMPLE_RATE)

print("8. acid_bass_high")
sf.write("08_acid_bass_high.wav",
         generate_303_bass(slow_pattern, envelope_speed='slow', octave_shift=1, portamento=False),
         SAMPLE_RATE)

print("9. acid_bass_slide")
sf.write("09_acid_bass_slide.wav",
         generate_303_bass(slow_pattern, envelope_speed='slow', octave_shift=0, portamento=True),
         SAMPLE_RATE)

print("10. sub_bass")
sf.write("10_sub_bass.wav", generate_sub_bass(), SAMPLE_RATE)

# PERCUSSION
print("11. rimshot (brighter pattern)")
sf.write("11_rimshot.wav", generate_rimshot(), SAMPLE_RATE)

print("12. conga")
sf.write("12_conga.wav", generate_conga(), SAMPLE_RATE)

print("13. cowbell")
sf.write("13_cowbell.wav", generate_cowbell(), SAMPLE_RATE)

print("14. shaker")
sf.write("14_shaker.wav", generate_shaker(), SAMPLE_RATE)

# SYNTH / PAD
print("15. dark_pad (more movement)")
sf.write("15_dark_pad.wav", generate_dark_pad(), SAMPLE_RATE)

print("16. acid_lead")
sf.write("16_acid_lead.wav", generate_acid_lead(), SAMPLE_RATE)

print("17. chord_stab (brighter, punchier)")
sf.write("17_chord_stab.wav", generate_chord_stab(), SAMPLE_RATE)

print("18. arp_synth")
sf.write("18_arp_synth.wav", generate_arp_synth(), SAMPLE_RATE)

print("19. noise_sweep (90s HPF style)")
sf.write("19_noise_sweep.wav", generate_noise_sweep(), SAMPLE_RATE)

print("20. reese_bass (smoothed)")
sf.write("20_reese_bass.wav", generate_reese_bass(), SAMPLE_RATE)

print("Done. All loops are 4 bars, 138 BPM, 44.1kHz, normalized to -3 dBFS.")