"""
Video Processing Service
Handles video upload, frame extraction, and synchronization
"""
import os
import cv2
import ffmpeg
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import hashlib
from loguru import logger

from app.core.config import settings


class VideoProcessor:
    """
    Video processing service for frame extraction and synchronization
    """
    
    def __init__(self, output_dir: str = "/uploads"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def validate_video(self, video_path: str) -> Dict:
        """
        Validate video file and extract metadata
        """
        try:
            probe = ffmpeg.probe(video_path)
            video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            audio_info = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)
            
            duration = float(probe['format']['duration'])
            size_mb = float(probe['format']['size']) / (1024 * 1024)
            
            # Validate constraints
            if size_mb > settings.MAX_VIDEO_SIZE_MB:
                raise ValueError(f"Video size {size_mb:.2f}MB exceeds maximum {settings.MAX_VIDEO_SIZE_MB}MB")
            
            if duration > settings.MAX_VIDEO_DURATION_SECONDS:
                raise ValueError(f"Video duration {duration:.2f}s exceeds maximum {settings.MAX_VIDEO_DURATION_SECONDS}s")
            
            return {
                "valid": True,
                "duration": duration,
                "size_mb": size_mb,
                "width": int(video_info['width']),
                "height": int(video_info['height']),
                "fps": eval(video_info['r_frame_rate']),
                "codec": video_info['codec_name'],
                "has_audio": audio_info is not None,
                "audio_codec": audio_info['codec_name'] if audio_info else None
            }
        except Exception as e:
            logger.error(f"Video validation failed: {e}")
            return {"valid": False, "error": str(e)}
    
    def extract_frames(
        self,
        video_path: str,
        output_dir: str,
        fps: Optional[int] = None,
        start_time: float = 0,
        end_time: Optional[float] = None
    ) -> List[str]:
        """
        Extract frames from video at specified FPS
        """
        fps = fps or settings.FRAME_EXTRACTION_FPS
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Extracting frames from {video_path} at {fps} FPS")
        
        cap = cv2.VideoCapture(video_path)
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / video_fps
        
        if end_time is None:
            end_time = duration
        
        # Calculate frame interval
        frame_interval = int(video_fps / fps)
        
        frame_paths = []
        frame_count = 0
        saved_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            current_time = frame_count / video_fps
            
            if current_time < start_time:
                frame_count += 1
                continue
            
            if current_time > end_time:
                break
            
            # Save frame at specified interval
            if frame_count % frame_interval == 0:
                frame_filename = f"frame_{saved_count:06d}.png"
                frame_path = output_path / frame_filename
                cv2.imwrite(str(frame_path), frame)
                frame_paths.append(str(frame_path))
                saved_count += 1
            
            frame_count += 1
        
        cap.release()
        logger.info(f"Extracted {saved_count} frames from {total_frames} total frames")
        
        return frame_paths
    
    def extract_audio(self, video_path: str, output_path: str) -> str:
        """
        Extract audio from video
        """
        try:
            logger.info(f"Extracting audio from {video_path}")
            
            (
                ffmpeg
                .input(video_path)
                .output(output_path, acodec='pcm_s16le', ac=1, ar='16k')
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            logger.info(f"Audio extracted to {output_path}")
            return output_path
        except ffmpeg.Error as e:
            logger.error(f"Audio extraction failed: {e.stderr.decode()}")
            raise
    
    def synchronize_videos(
        self,
        video_paths: List[str],
        method: str = "audio"
    ) -> Dict[str, float]:
        """
        Synchronize multiple videos using audio or visual features
        Returns time offsets for each video
        """
        logger.info(f"Synchronizing {len(video_paths)} videos using {method} method")
        
        if method == "audio":
            return self._synchronize_by_audio(video_paths)
        elif method == "visual":
            return self._synchronize_by_visual(video_paths)
        else:
            raise ValueError(f"Unknown synchronization method: {method}")
    
    def _synchronize_by_audio(self, video_paths: List[str]) -> Dict[str, float]:
        """
        Synchronize videos by cross-correlating audio tracks
        """
        import librosa
        
        audio_signals = []
        sample_rate = 16000
        
        # Extract audio from all videos
        for video_path in video_paths:
            temp_audio = f"/tmp/audio_{hashlib.md5(video_path.encode()).hexdigest()}.wav"
            self.extract_audio(video_path, temp_audio)
            
            # Load audio
            y, sr = librosa.load(temp_audio, sr=sample_rate)
            audio_signals.append(y)
            
            # Clean up temp file
            os.remove(temp_audio)
        
        # Use first video as reference
        reference = audio_signals[0]
        offsets = {video_paths[0]: 0.0}
        
        # Calculate offsets for other videos
        for i, (video_path, signal) in enumerate(zip(video_paths[1:], audio_signals[1:]), 1):
            # Cross-correlation
            correlation = np.correlate(reference, signal, mode='full')
            lag = np.argmax(correlation) - len(signal) + 1
            offset = lag / sample_rate
            
            offsets[video_path] = offset
            logger.info(f"Video {i} offset: {offset:.3f}s")
        
        return offsets
    
    def _synchronize_by_visual(self, video_paths: List[str]) -> Dict[str, float]:
        """
        Synchronize videos by matching visual features
        """
        # TODO: Implement visual synchronization using SIFT/ORB features
        logger.warning("Visual synchronization not yet implemented, using zero offsets")
        return {path: 0.0 for path in video_paths}
    
    def create_video_metadata(
        self,
        video_path: str,
        project_id: str,
        user_id: str
    ) -> Dict:
        """
        Create metadata for uploaded video
        """
        validation = self.validate_video(video_path)
        
        if not validation['valid']:
            raise ValueError(f"Invalid video: {validation.get('error')}")
        
        file_hash = self._calculate_file_hash(video_path)
        
        metadata = {
            "project_id": project_id,
            "user_id": user_id,
            "filename": os.path.basename(video_path),
            "file_path": video_path,
            "file_hash": file_hash,
            "duration": validation['duration'],
            "size_mb": validation['size_mb'],
            "resolution": f"{validation['width']}x{validation['height']}",
            "fps": validation['fps'],
            "codec": validation['codec'],
            "has_audio": validation['has_audio'],
            "audio_codec": validation.get('audio_codec'),
            "uploaded_at": datetime.utcnow().isoformat(),
            "status": "uploaded"
        }
        
        return metadata
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """
        Calculate SHA256 hash of file
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def get_video_thumbnail(
        self,
        video_path: str,
        output_path: str,
        timestamp: float = 1.0
    ) -> str:
        """
        Extract thumbnail from video at specified timestamp
        """
        try:
            (
                ffmpeg
                .input(video_path, ss=timestamp)
                .filter('scale', 320, -1)
                .output(output_path, vframes=1)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            return output_path
        except ffmpeg.Error as e:
            logger.error(f"Thumbnail extraction failed: {e.stderr.decode()}")
            raise
    
    def estimate_processing_time(self, video_metadata: Dict) -> float:
        """
        Estimate processing time based on video properties
        """
        # Rough estimate: 2x video duration for processing
        base_time = video_metadata['duration'] * 2
        
        # Add time based on resolution
        resolution_factor = (video_metadata['width'] * video_metadata['height']) / (1920 * 1080)
        
        estimated_time = base_time * resolution_factor
        
        return estimated_time

# Made with Bob
