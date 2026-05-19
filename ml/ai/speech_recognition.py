"""
Speech Recognition Module
Uses OpenAI Whisper for speech-to-text
"""
import os
import torch
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from loguru import logger


@dataclass
class Transcription:
    """Transcription result"""
    text: str
    language: str
    segments: List[Dict]
    duration: float
    confidence: float


class SpeechRecognizer:
    """
    Speech recognition using OpenAI Whisper
    """
    
    def __init__(
        self,
        model_size: str = "base",
        device: str = "cuda",
        language: Optional[str] = None
    ):
        self.model_size = model_size
        self.device = device
        self.language = language
        
        self._load_model()
        
        logger.info(f"Speech recognizer initialized with {model_size} model")
    
    def _load_model(self):
        """Load Whisper model"""
        try:
            import whisper
            
            self.model = whisper.load_model(
                self.model_size,
                device=self.device
            )
            
            logger.info(f"Whisper {self.model_size} model loaded")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise
    
    def transcribe_audio(
        self,
        audio_path: str,
        language: Optional[str] = None,
        task: str = "transcribe"
    ) -> Transcription:
        """
        Transcribe audio file to text
        
        Args:
            audio_path: Path to audio file
            language: Language code (e.g., 'en', 'es')
            task: 'transcribe' or 'translate'
        """
        logger.info(f"Transcribing audio: {audio_path}")
        
        # Transcribe
        result = self.model.transcribe(
            audio_path,
            language=language or self.language,
            task=task,
            verbose=False
        )
        
        # Calculate average confidence
        confidences = [seg.get('confidence', 0.0) for seg in result.get('segments', [])]
        avg_confidence = np.mean(confidences) if confidences else 0.0
        
        transcription = Transcription(
            text=result['text'].strip(),
            language=result.get('language', 'unknown'),
            segments=result.get('segments', []),
            duration=result.get('duration', 0.0),
            confidence=avg_confidence
        )
        
        logger.info(f"Transcription complete: {len(transcription.text)} characters")
        
        return transcription
    
    def transcribe_with_timestamps(
        self,
        audio_path: str,
        language: Optional[str] = None
    ) -> List[Dict]:
        """
        Transcribe with word-level timestamps
        """
        result = self.model.transcribe(
            audio_path,
            language=language or self.language,
            word_timestamps=True,
            verbose=False
        )
        
        segments_with_words = []
        
        for segment in result.get('segments', []):
            segment_data = {
                'start': segment['start'],
                'end': segment['end'],
                'text': segment['text'],
                'words': segment.get('words', [])
            }
            segments_with_words.append(segment_data)
        
        return segments_with_words
    
    def detect_language(
        self,
        audio_path: str
    ) -> Tuple[str, float]:
        """
        Detect language from audio
        Returns: (language_code, confidence)
        """
        import whisper
        
        # Load audio
        audio = whisper.load_audio(audio_path)
        audio = whisper.pad_or_trim(audio)
        
        # Make log-Mel spectrogram
        mel = whisper.log_mel_spectrogram(audio).to(self.model.device)
        
        # Detect language
        _, probs = self.model.detect_language(mel)
        
        # Get top language
        language = max(probs, key=probs.get)
        confidence = probs[language]
        
        logger.info(f"Detected language: {language} (confidence: {confidence:.2f})")
        
        return language, confidence
    
    def transcribe_realtime(
        self,
        audio_stream,
        chunk_duration: float = 5.0
    ):
        """
        Transcribe audio stream in real-time
        This is a placeholder for streaming implementation
        """
        logger.warning("Real-time transcription not fully implemented")
        
        # Would require:
        # 1. Audio chunking
        # 2. VAD (Voice Activity Detection)
        # 3. Streaming inference
        # 4. Result buffering
        
        pass
    
    def extract_speaker_segments(
        self,
        audio_path: str,
        num_speakers: Optional[int] = None
    ) -> List[Dict]:
        """
        Extract speaker segments using diarization
        """
        try:
            from pyannote.audio import Pipeline
            
            # Load diarization pipeline
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization",
                use_auth_token=os.getenv("HUGGINGFACE_TOKEN")
            )
            
            # Run diarization
            diarization = pipeline(audio_path, num_speakers=num_speakers)
            
            # Extract segments
            segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segments.append({
                    'start': turn.start,
                    'end': turn.end,
                    'speaker': speaker
                })
            
            logger.info(f"Extracted {len(segments)} speaker segments")
            
            return segments
        except Exception as e:
            logger.error(f"Speaker diarization failed: {e}")
            return []
    
    def transcribe_with_speakers(
        self,
        audio_path: str,
        num_speakers: Optional[int] = None
    ) -> List[Dict]:
        """
        Transcribe with speaker labels
        """
        # Get speaker segments
        speaker_segments = self.extract_speaker_segments(audio_path, num_speakers)
        
        # Get transcription with timestamps
        transcription_segments = self.transcribe_with_timestamps(audio_path)
        
        # Merge speaker info with transcription
        result = []
        
        for trans_seg in transcription_segments:
            # Find overlapping speaker
            speaker = "unknown"
            max_overlap = 0
            
            for spk_seg in speaker_segments:
                overlap = min(trans_seg['end'], spk_seg['end']) - \
                         max(trans_seg['start'], spk_seg['start'])
                
                if overlap > max_overlap:
                    max_overlap = overlap
                    speaker = spk_seg['speaker']
            
            result.append({
                'start': trans_seg['start'],
                'end': trans_seg['end'],
                'text': trans_seg['text'],
                'speaker': speaker,
                'words': trans_seg.get('words', [])
            })
        
        return result
    
    def generate_subtitles(
        self,
        audio_path: str,
        output_path: str,
        format: str = "srt"
    ):
        """
        Generate subtitle file from audio
        """
        transcription = self.transcribe_with_timestamps(audio_path)
        
        if format == "srt":
            self._write_srt(transcription, output_path)
        elif format == "vtt":
            self._write_vtt(transcription, output_path)
        else:
            raise ValueError(f"Unknown subtitle format: {format}")
        
        logger.info(f"Subtitles saved to {output_path}")
    
    def _write_srt(self, segments: List[Dict], output_path: str):
        """Write SRT subtitle file"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, seg in enumerate(segments, 1):
                start = self._format_timestamp(seg['start'])
                end = self._format_timestamp(seg['end'])
                
                f.write(f"{i}\n")
                f.write(f"{start} --> {end}\n")
                f.write(f"{seg['text'].strip()}\n\n")
    
    def _write_vtt(self, segments: List[Dict], output_path: str):
        """Write WebVTT subtitle file"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("WEBVTT\n\n")
            
            for seg in segments:
                start = self._format_timestamp(seg['start'], vtt=True)
                end = self._format_timestamp(seg['end'], vtt=True)
                
                f.write(f"{start} --> {end}\n")
                f.write(f"{seg['text'].strip()}\n\n")
    
    def _format_timestamp(self, seconds: float, vtt: bool = False) -> str:
        """Format timestamp for subtitles"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        
        if vtt:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
        else:
            return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def batch_transcribe(
        self,
        audio_files: List[str],
        output_dir: str
    ) -> List[Transcription]:
        """
        Transcribe multiple audio files
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        transcriptions = []
        
        for audio_file in audio_files:
            try:
                transcription = self.transcribe_audio(audio_file)
                transcriptions.append(transcription)
                
                # Save transcription
                filename = Path(audio_file).stem
                output_file = output_path / f"{filename}.txt"
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(transcription.text)
                
            except Exception as e:
                logger.error(f"Failed to transcribe {audio_file}: {e}")
        
        logger.info(f"Batch transcribed {len(transcriptions)} files")
        
        return transcriptions
    
    def extract_keywords(
        self,
        transcription: Transcription,
        top_k: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Extract keywords from transcription
        """
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            
            # Simple TF-IDF based keyword extraction
            vectorizer = TfidfVectorizer(
                max_features=top_k,
                stop_words='english'
            )
            
            # Fit on transcription
            tfidf_matrix = vectorizer.fit_transform([transcription.text])
            
            # Get feature names and scores
            feature_names = vectorizer.get_feature_names_out()
            scores = tfidf_matrix.toarray()[0]
            
            # Sort by score
            keywords = sorted(
                zip(feature_names, scores),
                key=lambda x: x[1],
                reverse=True
            )
            
            return keywords
        except Exception as e:
            logger.error(f"Keyword extraction failed: {e}")
            return []
    
    def summarize_transcription(
        self,
        transcription: Transcription,
        max_length: int = 100
    ) -> str:
        """
        Generate summary of transcription
        This is a placeholder - would use LLM for better results
        """
        # Simple extractive summary - take first sentences
        sentences = transcription.text.split('.')
        summary = '. '.join(sentences[:3]) + '.'
        
        if len(summary) > max_length:
            summary = summary[:max_length] + '...'
        
        return summary
    
    def calculate_speaking_rate(
        self,
        transcription: Transcription
    ) -> float:
        """
        Calculate words per minute
        """
        words = transcription.text.split()
        duration_minutes = transcription.duration / 60.0
        
        if duration_minutes > 0:
            wpm = len(words) / duration_minutes
            return wpm
        
        return 0.0

# Made with Bob
