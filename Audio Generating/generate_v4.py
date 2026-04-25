import numpy as np
from scipy import signal
import soundfile as sf

BPM = 138
SAMPLE_RATE = 44100
BARS = 4
beat_duration = 60.0 / BPM
loop_duration = BARS * 4 * beat_duration
num_samples = int(loop_duration * SAMPLE_RATE)

NOTES = {
    'A1': 55.00, 'A#1': 58.27, 'B1': 61.74, 'C2': 65.41, 'C#2': 69.30,
    'D2': 73.42, 'D#2': 77.78, 'E2': 82.41, 'F2': 87.31, 'F#2': 92.50,
    'G2': 98.00, 'G#2': 103.83, 'A2': 110.00, 'A#2': 116.54, 'B2': 123.47,
    'C3': 130.81, 'C#3': 138.59, 'D3': 146.83, 'D#3': 155.56, 'E3': 164.81,
    'F3': 174.61, 'G3': 196.00, 'A3': 220.00, None: None
}

def normalize(audio, db=-3):
    target = 10 ** (db / 20)
    m = np.max(np.abs(audio))
    return audio * (target / m) if m > 0 else audio

def soft_clip(x, drive=2.0):
    return np.tanh(x * drive) / np.tanh(drive)

def time_varying_resonant_lp(audio, cutoff_array, resonance=5.0, sr=SAMPLE_RATE):
    nyq = sr / 2.0
    output = np.zeros_like(audio)
    x1 = x2 = y1 = y2 = 0.0
    smoothed = np.zeros_like(cutoff_array)
    smoothed[0] = cutoff_array[0]
    sc = 0.0008
    for i in range(1, len(cutoff_array)):
        smoothed[i] = smoothed[i-1] + sc * (cutoff_array[i] - smoothed[i-1])
    update_rate = 16
    b0 = b1 = b2 = a1 = a2 = 0.0
    for i in range(len(audio)):
        if i % update_rate == 0:
            cutoff = np.clip(smoothed[i], 30, nyq * 0.95)
            w0 = 2 * np.pi * cutoff / sr
            cos_w0 = np.cos(w0); sin_w0 = np.sin(w0)
            alpha = sin_w0 / (2 * resonance)
            a0_inv = 1.0 / (1 + alpha)
            b0 = (1 - cos_w0) / 2 * a0_inv
            b1 = (1 - cos_w0) * a0_inv
            b2 = b0
            a1 = -2 * cos_w0 * a0_inv
            a2 = (1 - alpha) * a0_inv
        x0 = audio[i]
        y0 = b0 * x0 + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2 = x1; x1 = x0; y2 = y1; y1 = y0
        output[i] = y0
    return output

def polyblep_saw(freq_array, sr=SAMPLE_RATE):
    n = len(freq_array)
    output = np.zeros(n)
    phase = 0.0
    for i in range(n):
        dt = freq_array[i] / sr
        t = phase
        val = 2.0 * t - 1.0
        if t < dt:
            tn = t / dt
            val -= (tn + tn - tn * tn - 1.0)
        elif t > 1.0 - dt:
            tn = (t - 1.0) / dt
            val -= (tn * tn + tn + tn + 1.0)
        output[i] = val
        phase += dt
        if phase >= 1.0:
            phase -= 1.0
    return output

def acid_303_multibar(bar_patterns, env_speed='med', octave_shift=0):
    """
    bar_patterns: list of BARS x (notes16, accents16, slides16) tuples
    Allows different patterns per bar for evolution!
    """
    sixteenth = beat_duration / 4
    step_samples = int(sixteenth * SAMPLE_RATE)
    
    if env_speed == 'slow':
        decay_rate, env_amount, base_cutoff, resonance = 5.0, 2400, 200, 6.5
    elif env_speed == 'fast':
        decay_rate, env_amount, base_cutoff, resonance = 22.0, 3200, 180, 8.0
    else:
        decay_rate, env_amount, base_cutoff, resonance = 11.0, 2800, 200, 7.0
    
    freq_array = np.zeros(num_samples)
    gate_array = np.zeros(num_samples)
    retrigger_array = np.zeros(num_samples, dtype=bool)
    accent_array = np.zeros(num_samples)
    
    prev_freq = None
    
    # Flatten bar patterns into 64-step sequence
    all_notes, all_accents, all_slides = [], [], []
    for bar_idx in range(BARS):
        notes, accents, slides = bar_patterns[bar_idx % len(bar_patterns)]
        all_notes.extend(notes)
        all_accents.extend(accents)
        all_slides.extend(slides)
    
    total_steps = len(all_notes)
    
    for step_idx in range(total_steps):
        note = all_notes[step_idx]
        is_accent = all_accents[step_idx]
        
        start = step_idx * step_samples
        end = min(start + step_samples, num_samples)
        if start >= num_samples:
            break
        
        if note is None:
            gate_array[start:end] = 0.0
            prev_freq = None
            continue
        
        freq = NOTES[note] * (2 ** octave_shift)
        prev_was_slide = (step_idx > 0 and all_slides[step_idx-1] 
                         and all_notes[step_idx-1] is not None)
        
        if prev_was_slide and prev_freq is not None:
            slide_n = min(int(0.035 * SAMPLE_RATE), end - start)
            glide = prev_freq * np.power(freq / prev_freq, np.linspace(0, 1, slide_n))
            freq_array[start:start+slide_n] = glide
            freq_array[start+slide_n:end] = freq
            gate_array[start:end] = 1.0
        else:
            freq_array[start:end] = freq
            gate_array[start:end] = 1.0
            retrigger_array[start] = True
        
        if is_accent:
            accent_array[start:end] = 1.0
        prev_freq = freq
    
    # Fill rest gaps
    last_f = NOTES['A1']
    for i in range(num_samples):
        if freq_array[i] == 0:
            freq_array[i] = last_f
        else:
            last_f = freq_array[i]
    
    osc = polyblep_saw(freq_array)
    
    # Filter envelope
    filter_env = np.zeros(num_samples)
    env_val = 0.0; accent_env = 0.0
    for i in range(num_samples):
        if retrigger_array[i]:
            env_val = 1.0
            if accent_array[i] > 0:
                accent_env = 1.0
        env_val *= np.exp(-decay_rate / SAMPLE_RATE)
        accent_env *= np.exp(-15.0 / SAMPLE_RATE)
        accent_boost = 1.0 + accent_env * 0.8
        filter_env[i] = base_cutoff + env_amount * env_val * accent_boost
    
    filtered = time_varying_resonant_lp(osc, filter_env, resonance=resonance)
    
    # Amp envelope
    amp_env = np.zeros(num_samples)
    amp_val = 0.0; accent_amp = 0.0
    for i in range(num_samples):
        if retrigger_array[i]:
            amp_val = 1.0
            if accent_array[i] > 0:
                accent_amp = 1.0
        if gate_array[i] > 0:
            amp_val *= np.exp(-1.5 / SAMPLE_RATE)
        else:
            amp_val *= np.exp(-80.0 / SAMPLE_RATE)
        accent_amp *= np.exp(-8.0 / SAMPLE_RATE)
        amp_env[i] = amp_val * (1.0 + accent_amp * 0.5)
    
    sos = signal.butter(2, 1200/(SAMPLE_RATE/2), output='sos')
    amp_env = signal.sosfilt(sos, amp_env)
    
    audio = filtered * amp_env
    audio = soft_clip(audio * 1.5, 2.5)
    return normalize(audio)


# ============================================================
# 06: ACID_BASS_SLOW
# Vibe: dark, dubby, brooding. Spacious with rests.
# Uses C#2 (chromatic), F2 (b6), G2 (b7) for tension
# Two-bar pattern that varies between bars
# ============================================================
slow_bar_A = (
    ['A1', None,'A1','C#2', None,'A1','F2','E2', None,'A1', None,'A1','G2','F2','E2','C#2'],
    [ 1,   0,   0,   1,   0,   0,   1,   0,   0,   1,   0,   0,   1,   0,   0,   0 ],
    [ 0,   0,   0,   1,   0,   0,   1,   1,   0,   0,   0,   0,   1,   1,   1,   0 ]
)
slow_bar_B = (
    ['A1','A2','A1', None,'F2','E2','A1','C#2','A1', None,'A2','A1','G2','F2','D#2','C2'],
    [ 1,   0,   0,   0,   1,   0,   0,   1,   1,   0,   0,   0,   1,   0,   0,   1 ],
    [ 1,   0,   0,   0,   1,   0,   0,   1,   1,   0,   0,   0,   1,   1,   1,   0 ]
)

# ============================================================
# 07: ACID_BASS_FAST  
# Vibe: relentless, wonky, punky. Heavy syncopation, octave jumps everywhere
# Each bar different - building intensity
# ============================================================
fast_bar_A = (
    ['A1','A2','C2','A2','A1','A2','D#2','A2','A1','A2','F2','A2','A1','A2','G#2','A2'],
    [ 1,   0,   1,   0,   1,   0,   1,   0,   1,   0,   1,   0,   1,   0,   1,   0 ],
    [ 0,   1,   1,   1,   0,   1,   1,   1,   0,   1,   1,   1,   0,   1,   1,   1 ]
)
fast_bar_B = (
    ['A1','C3','A2','C2','A1','D3','A2','D#2','A1','C3','A2','F2','A1','D3','A2','A2'],
    [ 1,   1,   0,   1,   0,   1,   0,   1,   1,   0,   0,   1,   0,   1,   1,   0 ],
    [ 1,   1,   1,   0,   1,   1,   1,   0,   1,   1,   1,   0,   1,   1,   0,   0 ]
)
fast_bar_C = (
    ['A1','A1','A2','C2','D#2','C2','A2','A1','F2','E2','D#2','D2','C#2','C2','B1','A1'],
    [ 1,   0,   1,   0,   1,   0,   0,   1,   1,   0,   0,   0,   1,   0,   0,   1 ],
    [ 0,   1,   0,   1,   1,   1,   0,   0,   1,   1,   1,   1,   1,   1,   1,   0 ]
)

# ============================================================
# 08: ACID_BASS_HIGH
# Vibe: squelchy, lead-like, screaming. Wide range, lots of slides
# Octave shifted up - feels like an acid lead
# ============================================================
high_bar_A = (
    ['A1','E2','A2','D2','C#2','A1','F2','A2','D#2','A1','E2','G2','A2','C#2','A1','F#2'],
    [ 1,   0,   1,   0,   1,   0,   1,   0,   0,   1,   0,   1,   0,   1,   0,   1 ],
    [ 1,   1,   1,   1,   0,   1,   1,   1,   1,   0,   1,   1,   1,   0,   1,   1 ]
)
high_bar_B = (
    ['A1','A2',None,'C2','D2','E2', None,'F2','G2','A2','G2','F2','E2','D2','C2','B1'],
    [ 1,   1,   0,   0,   1,   0,   0,   1,   0,   1,   0,   0,   1,   0,   0,   1 ],
    [ 1,   0,   0,   0,   1,   1,   0,   1,   1,   1,   1,   1,   1,   1,   1,   0 ]
)

# ============================================================
# 09: ACID_BASS_SLIDE
# Vibe: oozing, snake-like, almost every note slides
# Long held notes with slides - that classic "uuuuiiiiiooo" sound
# ============================================================
slide_bar_A = (
    ['A1', None, None,'C2', None, None,'F2', None,'D#2', None, None,'A1', None,'G2', None,'E2'],
    [ 1,   0,   0,   1,   0,   0,   1,   0,   1,   0,   0,   0,   0,   1,   0,   1 ],
    [ 0,   0,   0,   1,   0,   0,   1,   0,   1,   0,   0,   0,   0,   1,   0,   0 ]
)
slide_bar_B = (
    ['A1','A1','C2','D#2','F2','G2','A2','G2','F2','D#2','C2','A1','C2','D#2','C2','A1'],
    [ 1,   0,   0,   1,   0,   0,   1,   0,   0,   1,   0,   0,   0,   1,   0,   0 ],
    [ 0,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   0,   1,   1,   1,   0 ]
)


print("Generating REALLY different acid basslines...")

print("06. acid_bass_slow - dark/dubby with rests, chromatic tension...")
sf.write("06_acid_bass_slow.wav",
         acid_303_multibar([slow_bar_A, slow_bar_B, slow_bar_A, slow_bar_B], 'slow'),
         SAMPLE_RATE)

print("07. acid_bass_fast - relentless wonky, 3 different bars cycling...")
sf.write("07_acid_bass_fast.wav",
         acid_303_multibar([fast_bar_A, fast_bar_B, fast_bar_A, fast_bar_C], 'fast'),
         SAMPLE_RATE)

print("08. acid_bass_high - squelchy lead-like with wide range...")
sf.write("08_acid_bass_high.wav",
         acid_303_multibar([high_bar_A, high_bar_B, high_bar_A, high_bar_B], 'med', octave_shift=1),
         SAMPLE_RATE)

print("09. acid_bass_slide - oozing snake-like, almost everything slides...")
sf.write("09_acid_bass_slide.wav",
         acid_303_multibar([slide_bar_A, slide_bar_B, slide_bar_A, slide_bar_B], 'med'),
         SAMPLE_RATE)

print("\n✓ Done - 4 totally different acid patterns!")