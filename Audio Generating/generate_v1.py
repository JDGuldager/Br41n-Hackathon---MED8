import numpy as np
from scipy import signal
import soundfile as sf

# Global settings
BPM = 138
SAMPLE_RATE = 44100
BARS = 4
BEATS_PER_BAR = 4
KEY = 'A_minor'

# Calculate loop duration
beat_duration = 60.0 / BPM
loop_duration = BARS * BEATS_PER_BAR * beat_duration
num_samples = int(loop_duration * SAMPLE_RATE)

# A minor scale notes (frequencies in Hz)
NOTES = {
    'A1': 55.0, 'B1': 61.74, 'C2': 65.41, 'D2': 73.42, 'E2': 82.41,
    'A2': 110.0, 'B2': 123.47, 'C3': 130.81, 'D3': 146.83, 'E3': 164.81,
    'A3': 220.0, 'C4': 261.63, 'E4': 329.63,
    'A0': 27.5
}

# Utility functions
def normalize(audio, db=-3):
    """Normalize audio to target dB"""
    target_amplitude = 10 ** (db / 20)
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio * (target_amplitude / max_val)
    return audio

def generate_envelope(attack, decay, sustain, release, duration, sr=SAMPLE_RATE):
    """Generate ADSR envelope"""
    num_samples = int(duration * sr)
    envelope = np.zeros(num_samples)
    
    attack_samples = int(attack * sr)
    decay_samples = int(decay * sr)
    release_samples = int(release * sr)
    
    attack_samples = min(attack_samples, num_samples)
    decay_samples = min(decay_samples, num_samples - attack_samples)
    release_samples = min(release_samples, num_samples)
    
    sustain_samples = num_samples - attack_samples - decay_samples - release_samples
    sustain_samples = max(0, sustain_samples)
    
    # Attack
    if attack_samples > 0:
        envelope[:attack_samples] = np.linspace(0, 1, attack_samples)
    
    # Decay
    if decay_samples > 0:
        envelope[attack_samples:attack_samples+decay_samples] = np.linspace(1, sustain, decay_samples)
    
    # Sustain
    if sustain_samples > 0:
        envelope[attack_samples+decay_samples:attack_samples+decay_samples+sustain_samples] = sustain
    
    # Release
    if release_samples > 0:
        envelope[-release_samples:] = np.linspace(sustain, 0, release_samples)
    
    return envelope

def apply_lowpass_filter(audio, cutoff, q=1.0, sr=SAMPLE_RATE):
    """Apply resonant lowpass filter"""
    nyq = sr / 2.0
    cutoff = min(cutoff, nyq - 1)
    sos = signal.butter(2, cutoff / nyq, btype='low', output='sos')
    return signal.sosfilt(sos, audio)

def apply_highpass_filter(audio, cutoff, sr=SAMPLE_RATE):
    """Apply highpass filter"""
    nyq = sr / 2.0
    cutoff = min(cutoff, nyq - 1)
    sos = signal.butter(4, cutoff / nyq, btype='high', output='sos')
    return signal.sosfilt(sos, audio)

def apply_bandpass_filter(audio, lowcut, highcut, sr=SAMPLE_RATE):
    """Apply bandpass filter"""
    nyq = sr / 2.0
    low = lowcut / nyq
    high = min(highcut / nyq, 0.99)
    sos = signal.butter(4, [low, high], btype='band', output='sos')
    return signal.sosfilt(sos, audio)

# DRUMS (5 loops)
def generate_kick_909(short=False):
    """Generate 909-style kick with pitch drop"""
    audio = np.zeros(num_samples)
    kick_duration = 0.5 if not short else 0.25
    
    for beat in range(BARS * BEATS_PER_BAR):
        start_sample = int(beat * beat_duration * SAMPLE_RATE)
        kick_samples = int(kick_duration * SAMPLE_RATE)
        
        t = np.linspace(0, kick_duration, kick_samples)
        
        # Pitch envelope: 80Hz -> 30Hz
        freq = 80 * np.exp(-t * 8) + 30
        phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
        kick = np.sin(phase)
        
        # Exponential decay
        decay = 8 if not short else 15
        envelope = np.exp(-decay * t)
        kick *= envelope
        
        end_sample = min(start_sample + kick_samples, num_samples)
        audio[start_sample:end_sample] += kick[:end_sample-start_sample]
    
    return normalize(audio)

def generate_hihat_closed():
    """Generate closed hi-hat"""
    audio = np.zeros(num_samples)
    hat_duration = 0.03
    
    for i in range(BARS * 4 * 4):  # 16th notes
        start_sample = int(i * beat_duration / 4 * SAMPLE_RATE)
        hat_samples = int(hat_duration * SAMPLE_RATE)
        
        t = np.linspace(0, hat_duration, hat_samples)
        
        # White noise
        hat = np.random.randn(hat_samples)
        
        # HPF at 8000Hz
        hat = apply_highpass_filter(hat, 8000)
        
        # Exponential decay
        envelope = np.exp(-t * 100)
        hat *= envelope
        
        end_sample = min(start_sample + hat_samples, num_samples)
        audio[start_sample:end_sample] += hat[:end_sample-start_sample]
    
    return normalize(audio)

def generate_hihat_open():
    """Generate open hi-hat with shuffle"""
    audio = np.zeros(num_samples)
    hat_duration = 0.2
    
    # Shuffled 8th note pattern (swing)
    for i in range(BARS * 4 * 2):  # 8th notes
        # Add swing (shuffle)
        if i % 2 == 1:
            offset = beat_duration / 8 * 0.3
        else:
            offset = 0
            
        start_sample = int((i * beat_duration / 2 + offset) * SAMPLE_RATE)
        hat_samples = int(hat_duration * SAMPLE_RATE)
        
        t = np.linspace(0, hat_duration, hat_samples)
        
        # White noise
        hat = np.random.randn(hat_samples)
        
        # HPF at 6000Hz
        hat = apply_highpass_filter(hat, 6000)
        
        # Exponential decay
        envelope = np.exp(-t * 15)
        hat *= envelope * 0.6
        
        end_sample = min(start_sample + hat_samples, num_samples)
        audio[start_sample:end_sample] += hat[:end_sample-start_sample]
    
    return normalize(audio)

def generate_clap():
    """Generate clap on beats 2 and 4"""
    audio = np.zeros(num_samples)
    clap_duration = 0.05
    
    for bar in range(BARS):
        for beat in [1, 3]:  # Beats 2 and 4 (0-indexed)
            start_sample = int((bar * BEATS_PER_BAR + beat) * beat_duration * SAMPLE_RATE)
            clap_samples = int(clap_duration * SAMPLE_RATE)
            
            t = np.linspace(0, clap_duration, clap_samples)
            
            # Multiple noise bursts for clap effect
            clap = np.zeros(clap_samples)
            for i in range(3):
                delay = int(i * 0.01 * SAMPLE_RATE)
                noise = np.random.randn(clap_samples - delay) * 0.5
                clap[delay:] += noise
            
            # Bandpass 1000-3000Hz
            clap = apply_bandpass_filter(clap, 1000, 3000)
            
            # Decay
            envelope = np.exp(-t * 40)
            clap *= envelope
            
            end_sample = min(start_sample + clap_samples, num_samples)
            audio[start_sample:end_sample] += clap[:end_sample-start_sample]
    
    return normalize(audio)

# BASSLINE 303 (5 loops)
def generate_303_bass(note_pattern, envelope_speed='slow', octave_shift=0, portamento=False):
    """Generate TB-303 style acid bass"""
    audio = np.zeros(num_samples)
    
    notes_per_bar = len(note_pattern)
    note_duration = (BARS * BEATS_PER_BAR * beat_duration) / (BARS * notes_per_bar)
    
    prev_freq = None
    
    for bar in range(BARS):
        for i, note_name in enumerate(note_pattern):
            start_time = (bar * notes_per_bar + i) * note_duration
            start_sample = int(start_time * SAMPLE_RATE)
            note_samples = int(note_duration * SAMPLE_RATE)
            
            if start_sample >= num_samples:
                break
            
            t = np.linspace(0, note_duration, note_samples)
            
            # Get frequency with octave shift
            base_freq = NOTES[note_name]
            freq = base_freq * (2 ** octave_shift)
            
            # Portamento
            if portamento and prev_freq is not None:
                freq_sweep = np.linspace(prev_freq, freq, note_samples)
                phase = 2 * np.pi * np.cumsum(freq_sweep) / SAMPLE_RATE
            else:
                phase = 2 * np.pi * freq * t
            
            prev_freq = freq
            
            # Sawtooth oscillator
            osc = signal.sawtooth(phase)
            
            # Filter envelope
            if envelope_speed == 'slow':
                filter_env = 200 + 800 * np.exp(-t * 3)
            elif envelope_speed == 'fast':
                filter_env = 200 + 1500 * np.exp(-t * 15)
            else:
                filter_env = 200 + 600 * np.exp(-t * 5)
            
            # Apply resonant filter sweep
            filtered = np.zeros(note_samples)
            chunk_size = 512
            for j in range(0, note_samples, chunk_size):
                end = min(j + chunk_size, note_samples)
                cutoff = filter_env[j]
                filtered[j:end] = apply_lowpass_filter(osc[j:end], cutoff)
            
            # Amplitude envelope
            amp_env = generate_envelope(0.001, 0.1, 0.7, 0.05, note_duration)
            filtered *= amp_env
            
            end_sample = min(start_sample + note_samples, num_samples)
            audio[start_sample:end_sample] += filtered[:end_sample-start_sample]
    
    return normalize(audio)

def generate_sub_bass():
    """Generate pure sub bass"""
    audio = np.zeros(num_samples)
    
    for bar in range(BARS):
        start_sample = int(bar * BEATS_PER_BAR * beat_duration * SAMPLE_RATE)
        note_samples = int(BEATS_PER_BAR * beat_duration * SAMPLE_RATE)
        
        t = np.linspace(0, BEATS_PER_BAR * beat_duration, note_samples)
        
        # Pure sine wave at A1
        sine = np.sin(2 * np.pi * NOTES['A1'] * t)
        
        # Gentle envelope
        env_dur = BEATS_PER_BAR * beat_duration
        envelope = generate_envelope(0.01, 0.1, 0.9, 0.1, env_dur)
        sine *= envelope
        
        end_sample = min(start_sample + note_samples, num_samples)
        audio[start_sample:end_sample] += sine[:end_sample-start_sample]
    
    return normalize(audio)

# PERCUSSION (4 loops)
def generate_rimshot():
    """Generate rimshot"""
    audio = np.zeros(num_samples)
    rim_duration = 0.05
    
    for i in range(BARS * 4):  # Quarter notes offset
        start_sample = int((i * beat_duration + beat_duration/2) * SAMPLE_RATE)
        rim_samples = int(rim_duration * SAMPLE_RATE)
        
        t = np.linspace(0, rim_duration, rim_samples)
        
        # Noise burst
        rim = np.random.randn(rim_samples)
        
        # Bandpass around 400Hz
        rim = apply_bandpass_filter(rim, 300, 600)
        
        # Sharp decay
        envelope = np.exp(-t * 80)
        rim *= envelope
        
        end_sample = min(start_sample + rim_samples, num_samples)
        audio[start_sample:end_sample] += rim[:end_sample-start_sample] * 0.7
    
    return normalize(audio)

def generate_conga():
    """Generate conga"""
    audio = np.zeros(num_samples)
    conga_duration = 0.15
    
    for i in range(BARS * 4 * 2):  # 8th notes
        if i % 3 == 0:  # Syncopated pattern
            start_sample = int(i * beat_duration / 2 * SAMPLE_RATE)
            conga_samples = int(conga_duration * SAMPLE_RATE)
            
            t = np.linspace(0, conga_duration, conga_samples)
            
            # Sine wave with pitch drop
            freq = 200 * np.exp(-t * 10) + 150
            phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
            conga = np.sin(phase)
            
            # Decay
            envelope = np.exp(-t * 15)
            conga *= envelope
            
            end_sample = min(start_sample + conga_samples, num_samples)
            audio[start_sample:end_sample] += conga[:end_sample-start_sample]
    
    return normalize(audio)

def generate_cowbell():
    """Generate cowbell"""
    audio = np.zeros(num_samples)
    bell_duration = 0.1
    
    for i in range(BARS * 2):  # Half notes
        start_sample = int(i * BEATS_PER_BAR * beat_duration / 2 * SAMPLE_RATE)
        bell_samples = int(bell_duration * SAMPLE_RATE)
        
        t = np.linspace(0, bell_duration, bell_samples)
        
        # Two detuned sines for metallic sound
        bell = np.sin(2 * np.pi * 540 * t) + np.sin(2 * np.pi * 800 * t)
        
        # Decay
        envelope = np.exp(-t * 12)
        bell *= envelope
        
        end_sample = min(start_sample + bell_samples, num_samples)
        audio[start_sample:end_sample] += bell[:end_sample-start_sample] * 0.5
    
    return normalize(audio)

def generate_shaker():
    """Generate shaker with 16th note pattern"""
    audio = np.zeros(num_samples)
    shaker_duration = 0.04
    
    for i in range(BARS * 4 * 4):  # 16th notes
        start_sample = int(i * beat_duration / 4 * SAMPLE_RATE)
        shaker_samples = int(shaker_duration * SAMPLE_RATE)
        
        t = np.linspace(0, shaker_duration, shaker_samples)
        
        # White noise
        shaker = np.random.randn(shaker_samples)
        
        # Bandpass filter
        shaker = apply_bandpass_filter(shaker, 4000, 10000)
        
        # Decay
        envelope = np.exp(-t * 50)
        shaker *= envelope * 0.4
        
        end_sample = min(start_sample + shaker_samples, num_samples)
        audio[start_sample:end_sample] += shaker[:end_sample-start_sample]
    
    return normalize(audio)

# SYNTH/PAD (6 loops)
def generate_dark_pad():
    """Generate dark pad with reverb"""
    audio = np.zeros(num_samples)
    
    # Am chord: A, C, E
    chord_notes = [NOTES['A2'], NOTES['C3'], NOTES['E3']]
    
    pad_duration = loop_duration
    t = np.linspace(0, pad_duration, num_samples)
    
    # Combine sine and saw for each note
    for freq in chord_notes:
        audio += np.sin(2 * np.pi * freq * t) * 0.3
        audio += signal.sawtooth(2 * np.pi * freq * t) * 0.2
    
    # Slow attack/release envelope
    envelope = generate_envelope(0.5, 0.3, 0.8, 0.5, pad_duration)
    audio *= envelope
    
    # Simple reverb using convolution with exponential decay IR
    reverb_duration = 2.0
    reverb_samples = int(reverb_duration * SAMPLE_RATE)
    reverb_ir = np.exp(-np.linspace(0, 10, reverb_samples)) * np.random.randn(reverb_samples) * 0.1
    
    # Convolve and trim to original length
    audio_reverb = np.convolve(audio, reverb_ir, mode='full')[:num_samples]
    
    return normalize(audio_reverb)

def generate_acid_lead():
    """Generate acid lead with square wave"""
    audio = np.zeros(num_samples)
    
    lead_notes = ['A3', 'C4', 'E4', 'A3', 'C4', 'E4', 'D3', 'E3'] * BARS
    note_duration = beat_duration / 2  # 8th notes
    
    for i, note_name in enumerate(lead_notes[:BARS*8]):
        start_sample = int(i * note_duration * SAMPLE_RATE)
        note_samples = int(note_duration * 0.7 * SAMPLE_RATE)  # Staccato
        
        t = np.linspace(0, note_duration * 0.7, note_samples)
        
        # Square wave
        freq = NOTES[note_name]
        square = signal.square(2 * np.pi * freq * t)
        
        # Filter
        square = apply_lowpass_filter(square, 2000)
        
        # Short envelope
        envelope = generate_envelope(0.01, 0.05, 0.5, 0.1, note_duration * 0.7)
        square *= envelope
        
        end_sample = min(start_sample + note_samples, num_samples)
        audio[start_sample:end_sample] += square[:end_sample-start_sample]
    
    return normalize(audio)

def generate_chord_stab():
    """Generate chord stab"""
    audio = np.zeros(num_samples)
    
    # Am chord with detuned saws
    chord_freqs = [NOTES['A2'], NOTES['C3'], NOTES['E3']]
    stab_duration = 0.2
    
    for bar in range(BARS):
        for beat in [0, 2]:  # Beats 1 and 3
            start_sample = int((bar * BEATS_PER_BAR + beat) * beat_duration * SAMPLE_RATE)
            stab_samples = int(stab_duration * SAMPLE_RATE)
            
            t = np.linspace(0, stab_duration, stab_samples)
            stab = np.zeros(stab_samples)
            
            for freq in chord_freqs:
                # Three detuned saws per note
                stab += signal.sawtooth(2 * np.pi * freq * 0.99 * t)
                stab += signal.sawtooth(2 * np.pi * freq * t)
                stab += signal.sawtooth(2 * np.pi * freq * 1.01 * t)
            
            # Fast decay
            envelope = np.exp(-t * 15)
            stab *= envelope
            
            # Filter
            stab = apply_lowpass_filter(stab, 2500)
            
            end_sample = min(start_sample + stab_samples, num_samples)
            audio[start_sample:end_sample] += stab[:end_sample-start_sample]
    
    return normalize(audio)

def generate_arp_synth():
    """Generate arpeggiated synth"""
    audio = np.zeros(num_samples)
    
    # Am pentatonic: A, C, D, E
    arp_pattern = ['A3', 'C4', 'E4', 'A3', 'D3', 'E3', 'A3', 'C4'] * BARS
    note_duration = beat_duration / 4  # 16th notes
    
    for i, note_name in enumerate(arp_pattern[:BARS*16]):
        start_sample = int(i * note_duration * SAMPLE_RATE)
        note_samples = int(note_duration * 0.8 * SAMPLE_RATE)
        
        t = np.linspace(0, note_duration * 0.8, note_samples)
        
        # Square wave
        freq = NOTES[note_name]
        square = signal.square(2 * np.pi * freq * t)
        
        # Filter
        square = apply_lowpass_filter(square, 3000)
        
        # Envelope
        envelope = generate_envelope(0.005, 0.05, 0.4, 0.05, note_duration * 0.8)
        square *= envelope * 0.6
        
        end_sample = min(start_sample + note_samples, num_samples)
        audio[start_sample:end_sample] += square[:end_sample-start_sample]
    
    return normalize(audio)

def generate_noise_sweep():
    """Generate noise sweep"""
    audio = np.zeros(num_samples)
    
    t = np.linspace(0, loop_duration, num_samples)
    
    # White noise
    noise = np.random.randn(num_samples)
    
    # LPF sweep from 200Hz to 8000Hz over 4 bars
    cutoff_freq = 200 + (8000 - 200) * (t / loop_duration)
    
    # Apply time-varying filter
    filtered = np.zeros(num_samples)
    chunk_size = 2048
    for i in range(0, num_samples, chunk_size):
        end = min(i + chunk_size, num_samples)
        cutoff = cutoff_freq[i]
        filtered[i:end] = apply_lowpass_filter(noise[i:end], cutoff)
    
    # Envelope
    envelope = generate_envelope(0.1, 0.2, 0.8, 0.5, loop_duration)
    filtered *= envelope
    
    return normalize(filtered)

def generate_reese_bass():
    """Generate Reese bass"""
    audio = np.zeros(num_samples)
    
    t = np.linspace(0, loop_duration, num_samples)
    
    # Base frequency
    base_freq = NOTES['A1']
    
    # LFO for detune (slow modulation)
    lfo = np.sin(2 * np.pi * 0.2 * t) * 2  # ±2 Hz modulation
    
    # Two detuned sawtooth waves
    saw1 = signal.sawtooth(2 * np.pi * (base_freq + 5 + lfo) * t)
    saw2 = signal.sawtooth(2 * np.pi * (base_freq - 5 - lfo) * t)
    
    audio = (saw1 + saw2) / 2
    
    # Filter
    audio = apply_lowpass_filter(audio, 600)
    
    # Envelope
    envelope = generate_envelope(0.05, 0.2, 0.8, 0.2, loop_duration)
    audio *= envelope
    
    return normalize(audio)

# Generate all loops
print("Generating acid techno loops...")
print(f"Loop duration: {loop_duration:.3f}s ({num_samples} samples)")

# DRUMS
print("\n1. Generating kick_909...")
sf.write("01_kick_909.wav", generate_kick_909(short=False), SAMPLE_RATE)

print("2. Generating kick_909_alt...")
sf.write("02_kick_909_alt.wav", generate_kick_909(short=True), SAMPLE_RATE)

print("3. Generating hihat_closed...")
sf.write("03_hihat_closed.wav", generate_hihat_closed(), SAMPLE_RATE)

print("4. Generating hihat_open...")
sf.write("04_hihat_open.wav", generate_hihat_open(), SAMPLE_RATE)

print("5. Generating clap...")
sf.write("05_clap.wav", generate_clap(), SAMPLE_RATE)

# BASSLINE 303
print("\n6. Generating acid_bass_slow...")
slow_pattern = ['A1', 'A1', 'D2', 'E2']
sf.write("06_acid_bass_slow.wav", generate_303_bass(slow_pattern, 'slow'), SAMPLE_RATE)

print("7. Generating acid_bass_fast...")
fast_pattern = ['A1', 'C2', 'D2', 'E2', 'A1', 'E2', 'D2', 'C2']
sf.write("07_acid_bass_fast.wav", generate_303_bass(fast_pattern, 'fast'), SAMPLE_RATE)

print("8. Generating acid_bass_high...")
sf.write("08_acid_bass_high.wav", generate_303_bass(slow_pattern, 'slow', octave_shift=1), SAMPLE_RATE)

print("9. Generating acid_bass_slide...")
sf.write("09_acid_bass_slide.wav", generate_303_bass(slow_pattern, 'slow', portamento=True), SAMPLE_RATE)

print("10. Generating sub_bass...")
sf.write("10_sub_bass.wav", generate_sub_bass(), SAMPLE_RATE)

# PERCUSSION
print("\n11. Generating rimshot...")
sf.write("11_rimshot.wav", generate_rimshot(), SAMPLE_RATE)

print("12. Generating conga...")
sf.write("12_conga.wav", generate_conga(), SAMPLE_RATE)

print("13. Generating cowbell...")
sf.write("13_cowbell.wav", generate_cowbell(), SAMPLE_RATE)

print("14. Generating shaker...")
sf.write("14_shaker.wav", generate_shaker(), SAMPLE_RATE)

# SYNTH/PAD
print("\n15. Generating dark_pad...")
sf.write("15_dark_pad.wav", generate_dark_pad(), SAMPLE_RATE)

print("16. Generating acid_lead...")
sf.write("16_acid_lead.wav", generate_acid_lead(), SAMPLE_RATE)

print("17. Generating chord_stab...")
sf.write("17_chord_stab.wav", generate_chord_stab(), SAMPLE_RATE)

print("18. Generating arp_synth...")
sf.write("18_arp_synth.wav", generate_arp_synth(), SAMPLE_RATE)

print("19. Generating noise_sweep...")
sf.write("19_noise_sweep.wav", generate_noise_sweep(), SAMPLE_RATE)

print("20. Generating reese_bass...")
sf.write("20_reese_bass.wav", generate_reese_bass(), SAMPLE_RATE)

print(f"\n✓ All 20 loops generated successfully!")
print(f"✓ Each loop is exactly {num_samples} samples ({loop_duration:.3f}s)")
print(f"✓ Normalized to -3dBFS")
print(f"✓ BPM: {BPM}, Key: A minor, 4 bars")