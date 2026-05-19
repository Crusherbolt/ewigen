"""
Human Detection and Tracking Module
Uses YOLO for detection and DeepSORT for tracking
"""
import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path
from loguru import logger


@dataclass
class Detection:
    """Single detection result"""
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    confidence: float
    class_id: int
    track_id: Optional[int] = None


@dataclass
class Person:
    """Tracked person across frames"""
    track_id: int
    detections: List[Detection]
    frames: List[int]
    bbox_history: List[Tuple[int, int, int, int]]


class HumanDetector:
    """
    Human detection and tracking using YOLO and DeepSORT
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.5,
        iou_threshold: float = 0.45,
        device: str = "cuda"
    ):
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.device = device
        
        # Initialize YOLO model
        self._init_yolo_model(model_path)
        
        # Initialize DeepSORT tracker
        self._init_tracker()
        
        logger.info("Human detector initialized")
    
    def _init_yolo_model(self, model_path: Optional[str]):
        """Initialize YOLO model"""
        try:
            from ultralytics import YOLO
            
            if model_path:
                self.model = YOLO(model_path)
            else:
                # Use pretrained YOLOv8 model
                self.model = YOLO('yolov8n.pt')
            
            logger.info("YOLO model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            raise
    
    def _init_tracker(self):
        """Initialize DeepSORT tracker"""
        try:
            from deep_sort_realtime.deepsort_tracker import DeepSort
            
            self.tracker = DeepSort(
                max_age=30,
                n_init=3,
                nms_max_overlap=1.0,
                max_cosine_distance=0.3,
                nn_budget=None,
                embedder="mobilenet",
                half=True,
                embedder_gpu=True if self.device == "cuda" else False
            )
            
            logger.info("DeepSORT tracker initialized")
        except Exception as e:
            logger.error(f"Failed to initialize tracker: {e}")
            raise
    
    def detect_humans(
        self,
        image: np.ndarray,
        return_crops: bool = False
    ) -> List[Detection]:
        """
        Detect humans in a single image
        """
        # Run YOLO detection
        results = self.model(
            image,
            conf=self.confidence_threshold,
            iou=self.iou_threshold,
            classes=[0],  # Person class
            verbose=False
        )
        
        detections = []
        
        for result in results:
            boxes = result.boxes
            
            for box in boxes:
                # Extract bbox coordinates
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                confidence = float(box.conf[0])
                class_id = int(box.cls[0])
                
                detection = Detection(
                    bbox=(int(x1), int(y1), int(x2), int(y2)),
                    confidence=confidence,
                    class_id=class_id
                )
                
                detections.append(detection)
        
        return detections
    
    def track_humans(
        self,
        image: np.ndarray,
        detections: List[Detection]
    ) -> List[Detection]:
        """
        Track detected humans across frames
        """
        # Prepare detections for tracker
        tracker_input = []
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            tracker_input.append((
                [x1, y1, x2 - x1, y2 - y1],  # [x, y, w, h]
                det.confidence,
                det.class_id
            ))
        
        # Update tracker
        tracks = self.tracker.update_tracks(tracker_input, frame=image)
        
        # Update detections with track IDs
        tracked_detections = []
        for track in tracks:
            if not track.is_confirmed():
                continue
            
            track_id = track.track_id
            ltrb = track.to_ltrb()
            
            # Find matching detection
            for det in detections:
                if self._bbox_iou(det.bbox, ltrb) > 0.5:
                    det.track_id = track_id
                    tracked_detections.append(det)
                    break
        
        return tracked_detections
    
    def process_video(
        self,
        video_path: str,
        output_dir: Optional[str] = None
    ) -> Dict[int, List[Person]]:
        """
        Process entire video and track all persons
        """
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        logger.info(f"Processing video: {total_frames} frames at {fps} FPS")
        
        # Track persons across frames
        persons_dict: Dict[int, Person] = {}
        frame_idx = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Detect humans
            detections = self.detect_humans(frame)
            
            # Track humans
            tracked_detections = self.track_humans(frame, detections)
            
            # Update person tracking
            for det in tracked_detections:
                if det.track_id is None:
                    continue
                
                if det.track_id not in persons_dict:
                    persons_dict[det.track_id] = Person(
                        track_id=det.track_id,
                        detections=[],
                        frames=[],
                        bbox_history=[]
                    )
                
                person = persons_dict[det.track_id]
                person.detections.append(det)
                person.frames.append(frame_idx)
                person.bbox_history.append(det.bbox)
            
            # Save annotated frame if output directory provided
            if output_dir:
                annotated_frame = self._draw_detections(frame, tracked_detections)
                output_path = Path(output_dir) / f"frame_{frame_idx:06d}.jpg"
                cv2.imwrite(str(output_path), annotated_frame)
            
            frame_idx += 1
            
            if frame_idx % 100 == 0:
                logger.info(f"Processed {frame_idx}/{total_frames} frames")
        
        cap.release()
        
        logger.info(f"Video processing complete. Found {len(persons_dict)} unique persons")
        
        return persons_dict
    
    def extract_person_crops(
        self,
        video_path: str,
        person: Person,
        output_dir: str,
        padding: int = 20
    ) -> List[str]:
        """
        Extract cropped images of a specific person
        """
        cap = cv2.VideoCapture(video_path)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        crop_paths = []
        
        for frame_idx, bbox in zip(person.frames, person.bbox_history):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            
            if not ret:
                continue
            
            # Extract crop with padding
            x1, y1, x2, y2 = bbox
            h, w = frame.shape[:2]
            
            x1 = max(0, x1 - padding)
            y1 = max(0, y1 - padding)
            x2 = min(w, x2 + padding)
            y2 = min(h, y2 + padding)
            
            crop = frame[y1:y2, x1:x2]
            
            # Save crop
            crop_filename = f"person_{person.track_id}_frame_{frame_idx:06d}.jpg"
            crop_path = output_path / crop_filename
            cv2.imwrite(str(crop_path), crop)
            crop_paths.append(str(crop_path))
        
        cap.release()
        
        logger.info(f"Extracted {len(crop_paths)} crops for person {person.track_id}")
        
        return crop_paths
    
    def get_person_statistics(self, person: Person) -> Dict:
        """
        Calculate statistics for a tracked person
        """
        # Calculate average bbox size
        bbox_sizes = [
            (x2 - x1) * (y2 - y1)
            for x1, y1, x2, y2 in person.bbox_history
        ]
        
        # Calculate movement
        movements = []
        for i in range(1, len(person.bbox_history)):
            prev_bbox = person.bbox_history[i-1]
            curr_bbox = person.bbox_history[i]
            
            # Calculate center movement
            prev_center = ((prev_bbox[0] + prev_bbox[2]) / 2, (prev_bbox[1] + prev_bbox[3]) / 2)
            curr_center = ((curr_bbox[0] + curr_bbox[2]) / 2, (curr_bbox[1] + curr_bbox[3]) / 2)
            
            movement = np.sqrt(
                (curr_center[0] - prev_center[0])**2 +
                (curr_center[1] - prev_center[1])**2
            )
            movements.append(movement)
        
        return {
            "track_id": person.track_id,
            "num_frames": len(person.frames),
            "first_frame": min(person.frames),
            "last_frame": max(person.frames),
            "avg_bbox_size": np.mean(bbox_sizes),
            "avg_confidence": np.mean([d.confidence for d in person.detections]),
            "avg_movement": np.mean(movements) if movements else 0,
            "total_movement": np.sum(movements) if movements else 0
        }
    
    def _bbox_iou(
        self,
        bbox1: Tuple[int, int, int, int],
        bbox2: Tuple[int, int, int, int]
    ) -> float:
        """
        Calculate IoU between two bounding boxes
        """
        x1_1, y1_1, x2_1, y2_1 = bbox1
        x1_2, y1_2, x2_2, y2_2 = bbox2
        
        # Calculate intersection
        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)
        
        if x2_i < x1_i or y2_i < y1_i:
            return 0.0
        
        intersection = (x2_i - x1_i) * (y2_i - y1_i)
        
        # Calculate union
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0
    
    def _draw_detections(
        self,
        image: np.ndarray,
        detections: List[Detection]
    ) -> np.ndarray:
        """
        Draw bounding boxes and track IDs on image
        """
        annotated = image.copy()
        
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            
            # Draw bbox
            color = (0, 255, 0) if det.track_id else (255, 0, 0)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            
            # Draw track ID
            if det.track_id:
                label = f"ID: {det.track_id}"
                cv2.putText(
                    annotated,
                    label,
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    2
                )
        
        return annotated

# Made with Bob
