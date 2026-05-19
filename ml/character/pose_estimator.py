"""
Pose Estimation Module
Uses MediaPipe for human pose estimation and tracking
"""
import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path
from loguru import logger


@dataclass
class Keypoint:
    """Single keypoint with 3D coordinates"""
    x: float
    y: float
    z: float
    visibility: float
    name: str


@dataclass
class Pose:
    """Complete pose with all keypoints"""
    keypoints: List[Keypoint]
    frame_idx: int
    timestamp: float
    confidence: float


class PoseEstimator:
    """
    Pose estimation using MediaPipe
    """
    
    def __init__(
        self,
        model_complexity: int = 2,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        enable_segmentation: bool = False
    ):
        self.model_complexity = model_complexity
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.enable_segmentation = enable_segmentation
        
        self._init_mediapipe()
        
        logger.info("Pose estimator initialized")
    
    def _init_mediapipe(self):
        """Initialize MediaPipe Pose"""
        try:
            import mediapipe as mp
            
            self.mp_pose = mp.solutions.pose
            self.mp_drawing = mp.solutions.drawing_utils
            self.mp_drawing_styles = mp.solutions.drawing_styles
            
            self.pose = self.mp_pose.Pose(
                model_complexity=self.model_complexity,
                min_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
                enable_segmentation=self.enable_segmentation
            )
            
            # Keypoint names
            self.keypoint_names = [
                'nose', 'left_eye_inner', 'left_eye', 'left_eye_outer',
                'right_eye_inner', 'right_eye', 'right_eye_outer',
                'left_ear', 'right_ear', 'mouth_left', 'mouth_right',
                'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
                'left_wrist', 'right_wrist', 'left_pinky', 'right_pinky',
                'left_index', 'right_index', 'left_thumb', 'right_thumb',
                'left_hip', 'right_hip', 'left_knee', 'right_knee',
                'left_ankle', 'right_ankle', 'left_heel', 'right_heel',
                'left_foot_index', 'right_foot_index'
            ]
            
            logger.info("MediaPipe Pose initialized")
        except Exception as e:
            logger.error(f"Failed to initialize MediaPipe: {e}")
            raise
    
    def estimate_pose(
        self,
        image: np.ndarray,
        frame_idx: int = 0,
        timestamp: float = 0.0
    ) -> Optional[Pose]:
        """
        Estimate pose from a single image
        """
        # Convert BGR to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Process image
        results = self.pose.process(image_rgb)
        
        if not results.pose_landmarks:
            return None
        
        # Extract keypoints
        keypoints = []
        for i, landmark in enumerate(results.pose_landmarks.landmark):
            keypoint = Keypoint(
                x=landmark.x,
                y=landmark.y,
                z=landmark.z,
                visibility=landmark.visibility,
                name=self.keypoint_names[i] if i < len(self.keypoint_names) else f"point_{i}"
            )
            keypoints.append(keypoint)
        
        # Calculate overall confidence
        confidence = np.mean([kp.visibility for kp in keypoints])
        
        pose = Pose(
            keypoints=keypoints,
            frame_idx=frame_idx,
            timestamp=timestamp,
            confidence=confidence
        )
        
        return pose
    
    def process_video(
        self,
        video_path: str,
        output_dir: Optional[str] = None,
        save_visualization: bool = False
    ) -> List[Pose]:
        """
        Process entire video and extract poses
        """
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        logger.info(f"Processing video: {total_frames} frames at {fps} FPS")
        
        poses = []
        frame_idx = 0
        
        if output_dir and save_visualization:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            timestamp = frame_idx / fps
            
            # Estimate pose
            pose = self.estimate_pose(frame, frame_idx, timestamp)
            
            if pose:
                poses.append(pose)
            
            # Save visualization
            if output_dir and save_visualization and pose:
                annotated = self.draw_pose(frame, pose)
                output_file = output_path / f"pose_{frame_idx:06d}.jpg"
                cv2.imwrite(str(output_file), annotated)
            
            frame_idx += 1
            
            if frame_idx % 100 == 0:
                logger.info(f"Processed {frame_idx}/{total_frames} frames")
        
        cap.release()
        
        logger.info(f"Extracted {len(poses)} poses from {total_frames} frames")
        
        return poses
    
    def draw_pose(
        self,
        image: np.ndarray,
        pose: Pose
    ) -> np.ndarray:
        """
        Draw pose keypoints and connections on image
        """
        annotated = image.copy()
        h, w = image.shape[:2]
        
        # Draw connections
        connections = [
            # Face
            (0, 1), (1, 2), (2, 3), (0, 4), (4, 5), (5, 6),
            (0, 7), (0, 8), (9, 10),
            # Arms
            (11, 12), (11, 13), (13, 15), (15, 17), (15, 19), (15, 21),
            (12, 14), (14, 16), (16, 18), (16, 20), (16, 22),
            # Body
            (11, 23), (12, 24), (23, 24),
            # Legs
            (23, 25), (25, 27), (27, 29), (27, 31),
            (24, 26), (26, 28), (28, 30), (28, 32)
        ]
        
        # Draw connections
        for start_idx, end_idx in connections:
            if start_idx < len(pose.keypoints) and end_idx < len(pose.keypoints):
                start_kp = pose.keypoints[start_idx]
                end_kp = pose.keypoints[end_idx]
                
                if start_kp.visibility > 0.5 and end_kp.visibility > 0.5:
                    start_point = (int(start_kp.x * w), int(start_kp.y * h))
                    end_point = (int(end_kp.x * w), int(end_kp.y * h))
                    
                    cv2.line(annotated, start_point, end_point, (0, 255, 0), 2)
        
        # Draw keypoints
        for kp in pose.keypoints:
            if kp.visibility > 0.5:
                point = (int(kp.x * w), int(kp.y * h))
                cv2.circle(annotated, point, 5, (0, 0, 255), -1)
        
        return annotated
    
    def extract_skeleton_sequence(
        self,
        poses: List[Pose]
    ) -> np.ndarray:
        """
        Extract skeleton sequence as numpy array
        Returns: [num_frames, num_keypoints, 3] array
        """
        if not poses:
            return np.array([])
        
        num_keypoints = len(poses[0].keypoints)
        skeleton_sequence = np.zeros((len(poses), num_keypoints, 3))
        
        for i, pose in enumerate(poses):
            for j, kp in enumerate(pose.keypoints):
                skeleton_sequence[i, j] = [kp.x, kp.y, kp.z]
        
        return skeleton_sequence
    
    def smooth_poses(
        self,
        poses: List[Pose],
        window_size: int = 5
    ) -> List[Pose]:
        """
        Smooth pose sequence using moving average
        """
        if len(poses) < window_size:
            return poses
        
        skeleton = self.extract_skeleton_sequence(poses)
        
        # Apply moving average
        from scipy.ndimage import uniform_filter1d
        smoothed = uniform_filter1d(skeleton, size=window_size, axis=0)
        
        # Create smoothed poses
        smoothed_poses = []
        for i, pose in enumerate(poses):
            smoothed_keypoints = []
            for j, kp in enumerate(pose.keypoints):
                smoothed_kp = Keypoint(
                    x=float(smoothed[i, j, 0]),
                    y=float(smoothed[i, j, 1]),
                    z=float(smoothed[i, j, 2]),
                    visibility=kp.visibility,
                    name=kp.name
                )
                smoothed_keypoints.append(smoothed_kp)
            
            smoothed_pose = Pose(
                keypoints=smoothed_keypoints,
                frame_idx=pose.frame_idx,
                timestamp=pose.timestamp,
                confidence=pose.confidence
            )
            smoothed_poses.append(smoothed_pose)
        
        return smoothed_poses
    
    def calculate_joint_angles(
        self,
        pose: Pose
    ) -> Dict[str, float]:
        """
        Calculate joint angles from pose
        """
        angles = {}
        
        # Helper function to calculate angle
        def angle_between_points(p1, p2, p3):
            """Calculate angle at p2"""
            v1 = np.array([p1.x - p2.x, p1.y - p2.y, p1.z - p2.z])
            v2 = np.array([p3.x - p2.x, p3.y - p2.y, p3.z - p2.z])
            
            cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
            angle = np.arccos(np.clip(cos_angle, -1.0, 1.0))
            return np.degrees(angle)
        
        kps = pose.keypoints
        
        # Left elbow
        if len(kps) > 15:
            angles['left_elbow'] = angle_between_points(kps[11], kps[13], kps[15])
        
        # Right elbow
        if len(kps) > 16:
            angles['right_elbow'] = angle_between_points(kps[12], kps[14], kps[16])
        
        # Left knee
        if len(kps) > 27:
            angles['left_knee'] = angle_between_points(kps[23], kps[25], kps[27])
        
        # Right knee
        if len(kps) > 28:
            angles['right_knee'] = angle_between_points(kps[24], kps[26], kps[28])
        
        return angles
    
    def detect_action(
        self,
        poses: List[Pose],
        window_size: int = 30
    ) -> str:
        """
        Detect action from pose sequence
        Simple rule-based detection
        """
        if len(poses) < window_size:
            return "unknown"
        
        recent_poses = poses[-window_size:]
        
        # Calculate movement
        movements = []
        for i in range(1, len(recent_poses)):
            prev_pose = recent_poses[i-1]
            curr_pose = recent_poses[i]
            
            # Calculate center of mass movement
            prev_com = np.mean([[kp.x, kp.y] for kp in prev_pose.keypoints], axis=0)
            curr_com = np.mean([[kp.x, kp.y] for kp in curr_pose.keypoints], axis=0)
            
            movement = np.linalg.norm(curr_com - prev_com)
            movements.append(movement)
        
        avg_movement = np.mean(movements)
        
        # Simple classification
        if avg_movement < 0.01:
            return "standing"
        elif avg_movement < 0.05:
            return "walking"
        else:
            return "running"
    
    def export_to_bvh(
        self,
        poses: List[Pose],
        output_path: str,
        fps: float = 30.0
    ):
        """
        Export poses to BVH format for animation
        """
        # This is a simplified BVH export
        # Full implementation would require proper skeleton hierarchy
        
        logger.warning("BVH export is simplified. Use proper animation tools for production.")
        
        with open(output_path, 'w') as f:
            # Write header
            f.write("HIERARCHY\n")
            f.write("ROOT Hips\n")
            f.write("{\n")
            f.write("  OFFSET 0.0 0.0 0.0\n")
            f.write("  CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation\n")
            # ... (simplified, full BVH would have complete skeleton)
            f.write("}\n")
            
            # Write motion data
            f.write("MOTION\n")
            f.write(f"Frames: {len(poses)}\n")
            f.write(f"Frame Time: {1.0/fps}\n")
            
            for pose in poses:
                # Write frame data (simplified)
                hip = pose.keypoints[23] if len(pose.keypoints) > 23 else pose.keypoints[0]
                f.write(f"{hip.x} {hip.y} {hip.z} 0 0 0\n")
        
        logger.info(f"Exported {len(poses)} poses to {output_path}")

# Made with Bob
