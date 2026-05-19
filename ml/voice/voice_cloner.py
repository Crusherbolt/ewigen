"""
Voice Cloning Module
Handles voice cloning and text-to-speech synthesis
"""
import os
import torch
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass
from loguru import logger


@dataclass
class VoiceProfile:
    """Voice profile for a person"""
    person_id: str
    voice_samples: List[str]
    model_path: Optional[str] = None
    characteristics: Optional[Dict] = None


class VoiceCloner:
    """
    Voice cloning service using Coqui TTS or ElevenLabs
    """
    
    def __init__(
        self,
        backend: str = "coqui",
        device: str = "cuda",
        api_key: Optional[str] = None
    ):
        self.backend = backend
        self.device = device
        self.api_key = api_key
        
        if backend == "coqui":
            self._init_coqui()
        elif backend == "elevenlabs":
            self._init_elevenlabs()
        else:
            raise ValueError(f"Unknown backend: {backend}")
        
        logger.info(f"Voice cloner initialized with {backend} backend")
    
    def _init_coqui(self):
        """Initialize Coqui TTS"""
        try:
            from TTS.api import TTS
            
            # Load multi-speaker model
            self.tts = TTS(
                model_name="tts_models/multilingual/multi-dataset/xtts_v2",
                progress_bar=False,
                gpu=self.device == "cuda"
            )
            
            logger.info("Coqui TTS initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Coqui TTS: {e}")
            raise
    
    def _init_elevenlabs(self):
        """Initialize ElevenLabs API"""
        try:
            from elevenlabs import set_api_key, Voice, VoiceSettings
            
            if not self.api_key:
                raise ValueError("ElevenLabs API key required")
            
            set_api_key(self.api_key)
            self.elevenlabs_voice = Voice
            self.elevenlabs_settings = VoiceSettings
            
            logger.info("ElevenLabs API initialized")
        except Exception as e:
            logger.error(f"Failed to initialize ElevenLabs: {e}")
            raise
    
    def extract_voice_from_audio(
        self,
        audio_path: str,
        output_dir: str,
        min_duration: float = 1.0
    ) -> List[str]:
        """
        Extract clean voice segments from audio
        """
        import librosa
        import soundfile as sf
        
        logger.info(f"Extracting voice from {audio_path}")
        
        # Load audio
        y, sr = librosa.load(audio_path, sr=16000)
        
        # Voice activity detection
        intervals = librosa.effects.split(
            y,
            top_db=30,
            frame_length=2048,
            hop_length=512
        )
        
        # Extract segments
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        voice_segments = []
        
        for i, (start, end) in enumerate(intervals):
            duration = (end - start) / sr
            
            if duration < min_duration:
                continue
            
            segment = y[start:end]
            
            # Save segment
            segment_path = output_path / f"segment_{i:04d}.wav"
            sf.write(str(segment_path), segment, sr)
            voice_segments.append(str(segment_path))
        
        logger.info(f"Extracted {len(voice_segments)} voice segments")
        
        return voice_segments
    
    def train_voice_model(
        self,
        voice_samples: List[str],
        person_id: str,
        output_dir: str
    ) -> VoiceProfile:
        """
        Train voice cloning model from samples
        """
        logger.info(f"Training voice model for person {person_id}")
        
        if self.backend == "coqui":
            return self._train_coqui_voice(voice_samples, person_id, output_dir)
        elif self.backend == "elevenlabs":
            return self._train_elevenlabs_voice(voice_samples, person_id)
        else:
            raise ValueError(f"Unknown backend: {self.backend}")
    
    def _train_coqui_voice(
        self,
        voice_samples: List[str],
        person_id: str,
        output_dir: str
    ) -> VoiceProfile:
        """
        Train Coqui TTS voice model
        """
        # Coqui XTTS uses speaker embeddings, no training needed
        # Just store the reference audio
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Use first sample as reference
        reference_audio = voice_samples[0]
        
        profile = VoiceProfile(
            person_id=person_id,
            voice_samples=voice_samples,
            model_path=reference_audio,
            characteristics={
                "backend": "coqui",
                "num_samples": len(voice_samples)
            }
        )
        
        logger.info(f"Voice profile created for {person_id}")
        
        return profile
    
    def _train_elevenlabs_voice(
        self,
        voice_samples: List[str],
        person_id: str
    ) -> VoiceProfile:
        """
        Create ElevenLabs voice clone
        """
        from elevenlabs import clone
        
        # Clone voice using samples
        voice = clone(
            name=f"person_{person_id}",
            description=f"Cloned voice for person {person_id}",
            files=voice_samples
        )
        
        profile = VoiceProfile(
            person_id=person_id,
            voice_samples=voice_samples,
            model_path=voice.voice_id,
            characteristics={
                "backend": "elevenlabs",
                "voice_id": voice.voice_id,
                "num_samples": len(voice_samples)
            }
        )
        
        logger.info(f"ElevenLabs voice cloned for {person_id}")
        
        return profile
    
    def synthesize_speech(
        self,
        text: str,
        voice_profile: VoiceProfile,
        output_path: str,
        language: str = "en"
    ) -> str:
        """
        Synthesize speech from text using cloned voice
        """
        logger.info(f"Synthesizing speech for person {voice_profile.person_id}")
        
        if self.backend == "coqui":
            return self._synthesize_coqui(text, voice_profile, output_path, language)
        elif self.backend == "elevenlabs":
            return self._synthesize_elevenlabs(text, voice_profile, output_path)
        else:
            raise ValueError(f"Unknown backend: {self.backend}")
    
    def _synthesize_coqui(
        self,
        text: str,
        voice_profile: VoiceProfile,
        output_path: str,
        language: str
    ) -> str:
        """
        Synthesize speech using Coqui TTS
        """
        self.tts.tts_to_file(
            text=text,
            speaker_wav=voice_profile.model_path,
            language=language,
            file_path=output_path
        )
        
        logger.info(f"Speech synthesized to {output_path}")
        
        return output_path
    
    def _synthesize_elevenlabs(
        self,
        text: str,
        voice_profile: VoiceProfile,
        output_path: str
    ) -> str:
        """
        Synthesize speech using ElevenLabs
        """
        from elevenlabs import generate, save
        
        audio = generate(
            text=text,
            voice=voice_profile.model_path,  # voice_id
            model="eleven_multilingual_v2"
        )
        
        save(audio, output_path)
        
        logger.info(f"Speech synthesized to {output_path}")
        
        return output_path
    
    def analyze_voice_characteristics(
        self,
        audio_path: str
    ) -> Dict:
        """
        Analyze voice characteristics from audio
        """
        import librosa
        
        # Load audio
        y, sr = librosa.load(audio_path, sr=16000)
        
        # Extract features
        # Pitch
        pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
        pitch_mean = np.mean(pitches[pitches > 0]) if np.any(pitches > 0) else 0
        
        # Tempo
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        
        # Spectral features
        spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
        
        # MFCCs
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        
        characteristics = {
            "pitch_mean": float(pitch_mean),
            "tempo": float(tempo),
            "spectral_centroid_mean": float(np.mean(spectral_centroids)),
            "spectral_rolloff_mean": float(np.mean(spectral_rolloff)),
            "mfcc_mean": mfccs.mean(axis=1).tolist(),
            "duration": float(len(y) / sr)
        }
        
        return characteristics
    
    def convert_voice(
        self,
        source_audio: str,
        target_voice_profile: VoiceProfile,
        output_path: str
    ) -> str:
        """
        Convert voice in audio to target voice
        """
        # This is a placeholder for voice conversion
        # Would require a voice conversion model like RVC or So-VITS-SVC
        
        logger.warning("Voice conversion not yet implemented")
        
        # For now, just copy the source
        import shutil
        shutil.copy(source_audio, output_path)
        
        return output_path
    
    def batch_synthesize(
        self,
        texts: List[str],
        voice_profile: VoiceProfile,
        output_dir: str,
        language: str = "en"
    ) -> List[str]:
        """
        Synthesize multiple texts in batch
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        output_files = []
        
        for i, text in enumerate(texts):
            output_file = output_path / f"speech_{i:04d}.wav"
            self.synthesize_speech(
                text,
                voice_profile,
                str(output_file),
                language
            )
            output_files.append(str(output_file))
        
        logger.info(f"Batch synthesized {len(texts)} speeches")
        
        return output_files
    
    def estimate_quality(
        self,
        voice_profile: VoiceProfile
    ) -> Dict:
        """
        Estimate voice cloning quality
        """
        # Analyze voice samples
        qualities = []
        
        for sample in voice_profile.voice_samples[:5]:  # Check first 5 samples
            try:
                chars = self.analyze_voice_characteristics(sample)
                
                # Simple quality score based on duration and features
                quality = min(1.0, chars['duration'] / 10.0)  # Prefer longer samples
                qualities.append(quality)
            except Exception as e:
                logger.warning(f"Failed to analyze sample: {e}")
        
        avg_quality = np.mean(qualities) if qualities else 0.0
        
        return {
            "quality_score": float(avg_quality),
            "num_samples": len(voice_profile.voice_samples),
            "recommendation": "good" if avg_quality > 0.7 else "needs_more_samples"
        }

# Made with Bob
