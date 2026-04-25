import numpy as np
from scipy import signal
import soundfile as sf

# Global settings
BPM = 138
SAMPLE_RATE = 44100
BARS = 4
BEATS_PER_BAR = 4

beat_duration = 60.0 / BPM
loop_duration = BARS * BEATS_PER_BAR * beat_duration
num_samples = int(loop_duration * SAMPLE_RATE)

NOTES = {
    'A1': 55.0, 'B1': 61.74, 'C2': 65.41, 'D2': 73.42, 'E2': 82.41,
    'A2': 110.0, 'B2': 123.47, 'C3': 130.81, 'D3': 146.83, 'E3': 164.81,
    'A3': 220.0, 'C4': 261.63, 'E4': 329.63, 'A0': 27.5
}

def normalize(audio, db=-3):
    target = 10 ** (db / 20)
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio * (target / max_val)
    return audio

def soft_clip(x, drive=1.0):
    """Tanh soft clipping for analog warmth"""
    return np.tanh(x * drive) / np.tanh(drive) if drive > 0 else x

def generate_envelope(attack, decay, sustain, release, duration, sr=SAMPLE_RATE):
    n = int(duration * sr)
    env = np.zeros(n)
    a = min(int(attack * sr), n)
    d = min(int(decay * sr), n - a)
    r = min(int(release * sr), n)
    s = max(0, n - a - d - r)
    if a > 0: env[:a] = np.linspace(0, 1, a)
    if d > 0: env[a:a+d] = np.linspace(1, sustain, d)
    if s > 0: env[a+d:a+d+s] = sustain
    if r > 0: env[-r:] = np.linspace(sustain, 0, r)
    return env

# ============================================================
# IMPROVED FILTERS
# ============================================================

def time_varying_resonant_lp(audio, cutoff_array, resonance=4.0, sr=SAMPLE_RATE):
    """
    Smooth time-varying resonant lowpass using biquad with state continuity.
    This is the KEY fix for the acid bass digital distortion.
    """
    nyq = sr / 2.0
    output = np.zeros_like(audio)
    
    # State variables (z^-1 and z^-2)
    x1 = x2 = y1 = y2 = 0.0
    
    # Smooth the cutoff to avoid zipper noise
    # Apply one-pole smoother to cutoff array
    smoothed_cutoff = np.zeros_like(cutoff_array)
    smoothed_cutoff[0] = cutoff_array[0]
    smooth_coef = 0.0005
    for i in range(1, len(cutoff_array)):
        smoothed_cutoff[i] = smoothed_cutoff[i-1] + smooth_coef * (cutoff_array[i] - smoothed_cutoff[i-1])
    
    # Update coefficients every N samples (cheap optimization)
    update_rate = 32
    b0 = b1 = b2 = a1 = a2 = 0.0
    
    for i in range(len(audio)):
        if i % update_rate == 0:
            cutoff = np.clip(smoothed_cutoff[i], 30, nyq * 0.95)
            w0 = 2 * np.pi * cutoff / sr
            cos_w0 = np.cos(w0)
            sin_w0 = np.sin(w0)
            alpha = sin_w0 / (2 * resonance)
            
            a0_inv = 1.0 / (1 + alpha)
            b0 = (1 - cos_w0) / 2 * a0_inv
            b1 = (1 - cos_w0) * a0_inv
            b2 = b0
            a1 = -2 * cos_w0 * a0_inv
            a2 = (1 - alpha) * a0_inv
        
        x0 = audio[i]
        y0 = b0 * x0 + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2 = x1; x1 = x0
        y2 = y1; y1 = y0
        output[i] = y0
    
    return output

def apply_highpass_filter(audio, cutoff, sr=SAMPLE_RATE):
    nyq = sr / 2.0
    sos = signal.butter(4, min(cutoff, nyq-1) / nyq, btype='high', output='sos')
    return signal.sosfilt(sos, audio)

def apply_bandpass_filter(audio, lowcut, highcut, sr=SAMPLE_RATE, order=4):
    nyq = sr / 2.0
    sos = signal.butter(order, [lowcut/nyq, min(highcut/nyq, 0.99)], btype='band', output='sos')
    return signal.sosfilt(sos, audio)

def apply_lowpass_filter(audio, cutoff, sr=SAMPLE_RATE):
    nyq = sr / 2.0
    sos = signal.butter(4, min(cutoff, nyq-1) / nyq, btype='low', output='sos')
    return signal.sosfilt(sos, audio)

def polyblep_saw(freq_array, sr=SAMPLE_RATE):
    """Anti-aliased sawtooth using PolyBLEP - cleaner than scipy.signal.sawtooth"""
    n = len(freq_array)
    output = np.zeros(n)
    phase = 0.0
    for i in range(n):
        dt = freq_array[i] / sr
        t = phase
        # Naive saw: 2*phase - 1
        val = 2.0 * t - 1.0
        # PolyBLEP correction at discontinuities
        if t < dt:
            t_norm = t / dt
            val -= (t_norm + t_norm - t_norm * t_norm - 1.0)
        elif t > 1.0 - dt:
            t_norm = (t - 1.0) / dt
            val -= (t_norm * t_norm + t_norm + t_norm + 1.0)
        output[i] = val
        phase += dt
        if phase >= 1.0:
            phase -= 1.0
    return output

# ============================================================
# FIX 02: kick_909_alt - punchier, shorter, with click attack
# ============================================================
def generate_kick_909_alt():
    audio = np.zeros(num_samples)
    kick_duration = 0.18  # much shorter
    
    for beat in range(BARS * BEATS_PER_BAR):
        start = int(beat * beat_duration * SAMPLE_RATE)
        n = int(kick_duration * SAMPLE_RATE)
        t = np.linspace(0, kick_duration, n)
        
        # Sharper pitch drop, higher start
        freq = 120 * np.exp(-t * 25) + 45
        phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
        kick = np.sin(phase)
        
        # Click transient at start
        click_n = int(0.003 * SAMPLE_RATE)
        click = np.random.randn(click_n) * np.exp(-np.linspace(0, 8, click_n))
        click = apply_highpass_filter(click, 2000)
        kick[:click_n] += click * 1.5
        
        # Faster, punchier decay
        envelope = np.exp(-t * 22)
        kick *= envelope
        kick = soft_clip(kick * 1.3, 1.5)
        
        end = min(start + n, num_samples)
        audio[start:end] += kick[:end-start]
    
    return normalize(audio)

# ============================================================
# FIX 06-09: Acid basses - smooth time-varying filter
# ============================================================
def generate_303_bass_v2(note_pattern, env_speed='slow', octave_shift=0, 
                         portamento=False, accent_pattern=None):
    audio_out = np.zeros(num_samples)
    
    notes_per_bar = len(note_pattern)
    note_duration = beat_duration * BEATS_PER_BAR / notes_per_bar
    note_samples = int(note_duration * SAMPLE_RATE)
    
    # Build full freq array for the entire loop (for portamento continuity)
    total_notes = BARS * notes_per_bar
    freq_array = np.zeros(num_samples)
    accent_array = np.zeros(num_samples)
    gate_array = np.zeros(num_samples)
    note_start_array = np.zeros(num_samples, dtype=bool)
    
    prev_freq = NOTES[note_pattern[0]] * (2 ** octave_shift)
    
    for idx in range(total_notes):
        note_name = note_pattern[idx % notes_per_bar]
        freq = NOTES[note_name] * (2 ** octave_shift)
        start = idx * note_samples
        end = min(start + note_samples, num_samples)
        
        if portamento and idx > 0:
            slide_samples = min(int(0.04 * SAMPLE_RATE), end - start)
            freq_array[start:start+slide_samples] = np.linspace(prev_freq, freq, slide_samples)
            freq_array[start+slide_samples:end] = freq
        else:
            freq_array[start:end] = freq
        
        gate_array[start:end] = 1.0
        if start < num_samples:
            note_start_array[start] = True
        if accent_pattern is not None and accent_pattern[idx % len(accent_pattern)]:
            accent_array[start:end] = 1.0
        
        prev_freq = freq
    
    # Generate band-limited sawtooth
    osc = polyblep_saw(freq_array)
    
    # Build smooth filter envelope (re-triggered per note)
    filter_env = np.zeros(num_samples)
    if env_speed == 'slow':
        decay_rate = 4.0
        env_amount = 2200
        base_cutoff = 180
        resonance = 5.0
    elif env_speed == 'fast':
        decay_rate = 18.0
        env_amount = 3000
        base_cutoff = 150
        resonance = 7.0
    else:
        decay_rate = 8.0
        env_amount = 2500
        base_cutoff = 200
        resonance = 6.0
    
    env_val = 0.0
    for i in range(num_samples):
        if note_start_array[i]:
            env_val = 1.0
        # Exponential decay
        env_val *= np.exp(-decay_rate / SAMPLE_RATE)
        accent_boost = 1.5 if accent_array[i] > 0 else 1.0
        filter_env[i] = base_cutoff + env_amount * env_val * accent_boost
    
    # Apply smooth time-varying resonant filter
    filtered = time_varying_resonant_lp(osc, filter_env, resonance=resonance)
    
    # Amplitude envelope per note
    amp_env = np.zeros(num_samples)
    amp_val = 0.0
    for i in range(num_samples):
        if note_start_array[i]:
            amp_val = 1.0
        if gate_array[i] > 0:
            amp_val *= np.exp(-2.5 / SAMPLE_RATE)
        else:
            amp_val *= np.exp(-50.0 / SAMPLE_RATE)
        amp_env[i] = amp_val
    
    # Smooth amp env to avoid clicks
    amp_env = signal.sosfilt(signal.butter(2, 800/(SAMPLE_RATE/2), output='sos'), amp_env)
    
    audio_out = filtered * amp_env
    
    # Soft saturation for analog warmth (instead of harsh digital clipping)
    audio_out = soft_clip(audio_out * 1.2, 2.0)
    
    return normalize(audio_out)

# ============================================================
# FIX 11: rimshot - sharper, brighter, louder, more click
# ============================================================
def generate_rimshot_v2():
    audio = np.zeros(num_samples)
    rim_duration = 0.08
    
    # Pattern: offbeats with some variation (more interesting)
    hits = []
    for bar in range(BARS):
        # Beat 2.5, 3.5, 4 (the "and" of 2, "and" of 3, beat 4)
        hits.append(bar * 4 + 1.5)
        hits.append(bar * 4 + 2.75)
        hits.append(bar * 4 + 3.5)
    
    for hit_beat in hits:
        start = int(hit_beat * beat_duration * SAMPLE_RATE)
        n = int(rim_duration * SAMPLE_RATE)
        t = np.linspace(0, rim_duration, n)
        
        # Layer 1: sharp tonal click (sine ping at 1700Hz)
        tone = np.sin(2 * np.pi * 1700 * t) * np.exp(-t * 60)
        
        # Layer 2: noise transient (bright)
        noise = np.random.randn(n)
        noise = apply_bandpass_filter(noise, 2000, 6000)
        noise *= np.exp(-t * 80)
        
        # Layer 3: body resonance
        body = np.sin(2 * np.pi * 400 * t) * np.exp(-t * 50)
        
        rim = tone * 0.6 + noise * 0.8 + body * 0.3
        rim = soft_clip(rim * 1.5, 1.5)
        
        end = min(start + n, num_samples)
        audio[start:end] += rim[:end-start]
    
    return normalize(audio)

# ============================================================
# FIX 15: dark_pad - more movement, filter sweep, chord changes
# ============================================================
def generate_dark_pad_v2():
    audio = np.zeros(num_samples)
    t = np.linspace(0, loop_duration, num_samples)
    
    # Chord progression: Am -> Am -> F(maj7) -> E(min) over 4 bars
    progressions = [
        [NOTES['A2'], NOTES['C3'], NOTES['E3'], NOTES['A3']],  # Am
        [NOTES['A2'], NOTES['C3'], NOTES['E3'], NOTES['A3']],  # Am
        [NOTES['A2'] * 0.794, NOTES['C3'], NOTES['E3'], NOTES['A3']],  # F-ish
        [NOTES['B2'], NOTES['E3'], NOTES['A3'], NOTES['E4'] * 0.5],  # Em-ish
    ]
    
    bar_samples = num_samples // BARS
    
    for bar_idx, chord in enumerate(progressions):
        bar_start = bar_idx * bar_samples
        bar_end = min(bar_start + bar_samples, num_samples)
        bar_t = t[bar_start:bar_end]
        bar_n = bar_end - bar_start
        
        bar_audio = np.zeros(bar_n)
        
        for freq in chord:
            # Slow detune LFO for movement
            lfo1 = np.sin(2 * np.pi * 0.3 * bar_t) * 0.3
            lfo2 = np.sin(2 * np.pi * 0.21 * bar_t + 1.0) * 0.4
            
            # Multiple detuned saws + sine sub
            saw1 = signal.sawtooth(2 * np.pi * (freq + lfo1) * bar_t)
            saw2 = signal.sawtooth(2 * np.pi * (freq * 1.005 + lfo2) * bar_t)
            saw3 = signal.sawtooth(2 * np.pi * (freq * 0.995 - lfo1) * bar_t)
            sine = np.sin(2 * np.pi * freq * bar_t)
            
            voice = (saw1 + saw2 + saw3) * 0.15 + sine * 0.2
            bar_audio += voice
        
        audio[bar_start:bar_end] += bar_audio
    
    # Slow filter sweep across whole loop (movement!)
    sweep = 400 + 1800 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.25 * t))
    audio = time_varying_resonant_lp(audio, sweep, resonance=2.0)
    
    # Slow attack/release envelope
    envelope = generate_envelope(0.4, 0.5, 0.85, 0.6, loop_duration)
    audio *= envelope
    
    # Reverb
    rev_n = int(1.5 * SAMPLE_RATE)
    rev_ir = np.exp(-np.linspace(0, 6, rev_n)) * np.random.randn(rev_n) * 0.15
    rev_ir[0] = 1.0  # dry signal
    audio = np.convolve(audio, rev_ir, mode='full')[:num_samples]
    
    # Stereo-ish chorus effect via slight delay (still mono)
    delay_samples = int(0.012 * SAMPLE_RATE)
    delayed = np.zeros_like(audio)
    delayed[delay_samples:] = audio[:-delay_samples] * 0.4
    audio = audio + delayed
    
    return normalize(audio)

# ============================================================
# FIX 17: chord_stab - louder, brighter, more present
# ============================================================
def generate_chord_stab_v2():
    audio = np.zeros(num_samples)
    chord_freqs = [NOTES['A2'], NOTES['C3'], NOTES['E3'], NOTES['A3']]
    stab_duration = 0.25
    
    # More hits: every offbeat (8th note offbeats)
    hit_positions = []
    for bar in range(BARS):
        # The "and" of every beat
        for beat in range(BEATS_PER_BAR):
            hit_positions.append(bar * BEATS_PER_BAR + beat + 0.5)
    
    for pos in hit_positions:
        start = int(pos * beat_duration * SAMPLE_RATE)
        n = int(stab_duration * SAMPLE_RATE)
        t = np.linspace(0, stab_duration, n)
        
        stab = np.zeros(n)
        for freq in chord_freqs:
            # 3 detuned saws per note
            for detune in [0.993, 1.0, 1.007]:
                stab += signal.sawtooth(2 * np.pi * freq * detune * t)
            # Add square for bite
            stab += signal.square(2 * np.pi * freq * t) * 0.3
        
        stab /= len(chord_freqs)
        
        # Snappy envelope (very fast attack)
        envelope = np.exp(-t * 18)
        # Add small attack ramp to avoid clicks
        attack_n = int(0.003 * SAMPLE_RATE)
        envelope[:attack_n] *= np.linspace(0, 1, attack_n)
        stab *= envelope
        
        # Brighter filter for presence
        stab = apply_lowpass_filter(stab, 4500)
        # High shelf-ish boost via highpass parallel
        bright = apply_highpass_filter(stab, 2000) * 0.3
        stab = stab + bright
        
        # Saturate for energy
        stab = soft_clip(stab * 1.8, 2.0)
        
        end = min(start + n, num_samples)
        audio[start:end] += stab[:end-start] * 1.2
    
    return normalize(audio)

# ============================================================
# FIX 19: noise_sweep - rhythmic 90s techno style riser/sweep
# ============================================================
def generate_noise_sweep_v2():
    """Classic techno-style filtered noise with rhythmic gating + sweep up over 4 bars"""
    audio = np.zeros(num_samples)
    t = np.linspace(0, loop_duration, num_samples)
    
    # White noise base
    noise = np.random.randn(num_samples)
    
    # Exponential sweep from 200Hz to 8000Hz over 4 bars (more dramatic)
    cutoff = 200 * np.power(8000.0/200.0, t / loop_duration)
    
    # Apply smooth time-varying filter with resonance for that classic riser whistle
    filtered = time_varying_resonant_lp(noise, cutoff, resonance=3.5)
    
    # Rhythmic 16th note gating (ducked sidechain feel)
    gate = np.ones(num_samples)
    sixteenth = beat_duration / 4
    for i in range(BARS * BEATS_PER_BAR * 4):
        gate_start = int(i * sixteenth * SAMPLE_RATE)
        gate_n = int(sixteenth * SAMPLE_RATE)
        # Each 16th: quick fade in, decay
        env_local = np.exp(-np.linspace(0, 4, gate_n))
        # Add small attack
        att = int(0.002 * SAMPLE_RATE)
        env_local[:att] *= np.linspace(0, 1, att)
        end = min(gate_start + gate_n, num_samples)
        gate[gate_start:end] = env_local[:end-gate_start]
    
    filtered *= gate
    
    # Overall riser envelope (gets louder toward the end)
    riser = np.power(t / loop_duration, 1.5) * 0.7 + 0.3
    filtered *= riser
    
    return normalize(filtered)

# ============================================================
# FIX 20: reese_bass - smooth filter like acid bass
# ============================================================
def generate_reese_bass_v2():
    t = np.linspace(0, loop_duration, num_samples)
    base_freq = NOTES['A1']
    
    # Slow LFO modulating detune amount
    lfo = np.sin(2 * np.pi * 0.25 * t) * 3.0
    lfo2 = np.sin(2 * np.pi * 0.18 * t + 0.7) * 2.0
    
    # Build freq arrays for band-limited oscillators
    freq1 = np.full(num_samples, base_freq) + lfo
    freq2 = np.full(num_samples, base_freq) - lfo
    freq3 = np.full(num_samples, base_freq * 1.005) + lfo2
    
    saw1 = polyblep_saw(freq1)
    saw2 = polyblep_saw(freq2)
    saw3 = polyblep_saw(freq3)
    
    audio = (saw1 + saw2 + saw3) / 3.0
    
    # Slow filter sweep for movement (like acid bass smooth filter)
    cutoff = 400 + 300 * np.sin(2 * np.pi * 0.5 * t)
    audio = time_varying_resonant_lp(audio, cutoff, resonance=3.0)
    
    # Sub layer
    sub = np.sin(2 * np.pi * base_freq * t) * 0.4
    audio = audio + sub
    
    # Soft saturation for analog warmth
    audio = soft_clip(audio * 1.4, 2.0)
    
    # Smooth envelope (no clicks)
    envelope = generate_envelope(0.05, 0.2, 0.9, 0.2, loop_duration)
    audio *= envelope
    
    return normalize(audio)

# ============================================================
# REGENERATE FIXED LOOPS
# ============================================================
print("Regenerating fixed loops...")

print("02. kick_909_alt (punchier, shorter)...")
sf.write("02_kick_909_alt.wav", generate_kick_909_alt(), SAMPLE_RATE)

print("06. acid_bass_slow (smooth filter)...")
slow_pattern = ['A1', 'A1', 'D2', 'E2']
accent_slow = [1, 0, 1, 0]
sf.write("06_acid_bass_slow.wav", 
         generate_303_bass_v2(slow_pattern, 'slow', accent_pattern=accent_slow), SAMPLE_RATE)

print("07. acid_bass_fast (smooth filter)...")
fast_pattern = ['A1', 'A2', 'A1', 'C2', 'D2', 'A1', 'E2', 'C2',
                'A1', 'A2', 'D2', 'A1', 'E2', 'D2', 'C2', 'B1']
accent_fast = [1,0,0,1,0,0,1,0,1,0,0,1,0,0,1,0]
sf.write("07_acid_bass_fast.wav", 
         generate_303_bass_v2(fast_pattern, 'fast', accent_pattern=accent_fast), SAMPLE_RATE)

print("08. acid_bass_high (smooth filter)...")
sf.write("08_acid_bass_high.wav",
         generate_303_bass_v2(slow_pattern, 'slow', octave_shift=1, 
                              accent_pattern=accent_slow), SAMPLE_RATE)

print("09. acid_bass_slide (smooth filter + portamento)...")
sf.write("09_acid_bass_slide.wav",
         generate_303_bass_v2(slow_pattern, 'slow', portamento=True,
                              accent_pattern=accent_slow), SAMPLE_RATE)

print("11. rimshot (sharper, brighter)...")
sf.write("11_rimshot.wav", generate_rimshot_v2(), SAMPLE_RATE)

print("15. dark_pad (chord changes + sweep + chorus)...")
sf.write("15_dark_pad.wav", generate_dark_pad_v2(), SAMPLE_RATE)

print("17. chord_stab (louder, brighter, more hits)...")
sf.write("17_chord_stab.wav", generate_chord_stab_v2(), SAMPLE_RATE)

print("19. noise_sweep (rhythmic 90s techno riser)...")
sf.write("19_noise_sweep.wav", generate_noise_sweep_v2(), SAMPLE_RATE)

print("20. reese_bass (smooth filter)...")
sf.write("20_reese_bass.wav", generate_reese_bass_v2(), SAMPLE_RATE)

print("\n✓ All fixes applied!")