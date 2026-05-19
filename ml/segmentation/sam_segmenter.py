"""
Object Detection and Segmentation using SAM (Segment Anything Model)
For robot training dataset annotations
"""
import torch
import numpy as np
from typing import List, Dict, Tuple, Optional
import cv2
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class SAMSegmenter:
    """
    Segment Anything Model for object detection and segmentation
    """
    
    def __init__(
        self,
        model_type: str = "vit_h",
        checkpoint_path: Optional[str] = None,
        device: str = "cuda"
    ):
        """
        Initialize SAM segmenter
        
        Args:
            model_type: Model type (vit_h, vit_l, vit_b)
            checkpoint_path: Path to model checkpoint
            device: Device to use
        """
        self.model_type = model_type
        self.device = device
        
        # Load SAM model
        self._load_model(checkpoint_path)
        
        logger.info(f"Initialized SAM segmenter with {model_type}")
    
    def _load_model(self, checkpoint_path: Optional[str]):
        """Load SAM model"""
        try:
            from segment_anything import sam_model_registry, SamAutomaticMaskGenerator, SamPredictor
            
            if checkpoint_path is None:
                checkpoint_path = f"models/sam_{self.model_type}.pth"
            
            # Load model
            sam = sam_model_registry[self.model_type](checkpoint=checkpoint_path)
            sam.to(device=self.device)
            
            # Create mask generator
            self.mask_generator = SamAutomaticMaskGenerator(
                model=sam,
                points_per_side=32,
                pred_iou_thresh=0.86,
                stability_score_thresh=0.92,
                crop_n_layers=1,
                crop_n_points_downscale_factor=2,
                min_mask_region_area=100,
            )
            
            # Create predictor for interactive segmentation
            self.predictor = SamPredictor(sam)
            
            logger.info("SAM model loaded successfully")
            
        except ImportError:
            logger.error("segment-anything not installed. Install with: pip install segment-anything")
            # Create dummy objects for testing
            self.mask_generator = None
            self.predictor = None
    
    def segment_image(
        self,
        image: np.ndarray,
        return_masks: bool = True
    ) -> List[Dict]:
        """
        Segment all objects in image automatically
        
        Args:
            image: Input image (H, W, 3)
            return_masks: Whether to return mask arrays
            
        Returns:
            List of segmentation results
        """
        if self.mask_generator is None:
            logger.warning("SAM model not loaded, returning empty results")
            return []
        
        # Generate masks
        masks = self.mask_generator.generate(image)
        
        # Sort by area (largest first)
        masks = sorted(masks, key=lambda x: x['area'], reverse=True)
        
        # Process results
        results = []
        for i, mask_data in enumerate(masks):
            result = {
                'id': i,
                'area': mask_data['area'],
                'bbox': mask_data['bbox'],  # [x, y, w, h]
                'predicted_iou': mask_data['predicted_iou'],
                'stability_score': mask_data['stability_score'],
                'crop_box': mask_data['crop_box']
            }
            
            if return_masks:
                result['mask'] = mask_data['segmentation']
            
            results.append(result)
        
        logger.info(f"Segmented {len(results)} objects")
        return results
    
    def segment_with_points(
        self,
        image: np.ndarray,
        points: np.ndarray,
        labels: np.ndarray
    ) -> Dict:
        """
        Segment object using point prompts
        
        Args:
            image: Input image (H, W, 3)
            points: Point coordinates (N, 2) [x, y]
            labels: Point labels (N,) 1=foreground, 0=background
            
        Returns:
            Segmentation result
        """
        if self.predictor is None:
            logger.warning("SAM predictor not loaded")
            return {}
        
        # Set image
        self.predictor.set_image(image)
        
        # Predict mask
        masks, scores, logits = self.predictor.predict(
            point_coords=points,
            point_labels=labels,
            multimask_output=True
        )
        
        # Return best mask
        best_idx = np.argmax(scores)
        
        return {
            'mask': masks[best_idx],
            'score': scores[best_idx],
            'logits': logits[best_idx]
        }
    
    def segment_with_box(
        self,
        image: np.ndarray,
        box: np.ndarray
    ) -> Dict:
        """
        Segment object using bounding box prompt
        
        Args:
            image: Input image (H, W, 3)
            box: Bounding box [x1, y1, x2, y2]
            
        Returns:
            Segmentation result
        """
        if self.predictor is None:
            logger.warning("SAM predictor not loaded")
            return {}
        
        # Set image
        self.predictor.set_image(image)
        
        # Predict mask
        masks, scores, logits = self.predictor.predict(
            box=box,
            multimask_output=False
        )
        
        return {
            'mask': masks[0],
            'score': scores[0],
            'logits': logits[0]
        }
    
    def annotate_for_robot_training(
        self,
        image: np.ndarray,
        depth_map: Optional[np.ndarray] = None
    ) -> Dict:
        """
        Create annotations for robot training dataset
        
        Args:
            image: Input image (H, W, 3)
            depth_map: Optional depth map (H, W)
            
        Returns:
            Annotation data
        """
        # Segment all objects
        segments = self.segment_image(image, return_masks=True)
        
        # Create annotations
        annotations = {
            'image_shape': image.shape,
            'num_objects': len(segments),
            'objects': []
        }
        
        for seg in segments:
            mask = seg['mask']
            
            # Calculate object properties
            obj_annotation = {
                'id': seg['id'],
                'bbox': seg['bbox'],
                'area': seg['area'],
                'mask': mask.tolist() if isinstance(mask, np.ndarray) else mask,
                'center': self._calculate_center(mask),
                'confidence': float(seg['predicted_iou'])
            }
            
            # Add depth information if available
            if depth_map is not None:
                obj_annotation['depth_stats'] = self._calculate_depth_stats(mask, depth_map)
            
            # Classify object type (placeholder)
            obj_annotation['category'] = self._classify_object(image, mask)
            
            annotations['objects'].append(obj_annotation)
        
        return annotations
    
    def _calculate_center(self, mask: np.ndarray) -> Tuple[float, float]:
        """Calculate center of mass of mask"""
        y_coords, x_coords = np.where(mask)
        if len(x_coords) == 0:
            return (0.0, 0.0)
        return (float(np.mean(x_coords)), float(np.mean(y_coords)))
    
    def _calculate_depth_stats(
        self,
        mask: np.ndarray,
        depth_map: np.ndarray
    ) -> Dict:
        """Calculate depth statistics for masked region"""
        masked_depth = depth_map[mask]
        
        if len(masked_depth) == 0:
            return {'mean': 0.0, 'std': 0.0, 'min': 0.0, 'max': 0.0}
        
        return {
            'mean': float(np.mean(masked_depth)),
            'std': float(np.std(masked_depth)),
            'min': float(np.min(masked_depth)),
            'max': float(np.max(masked_depth))
        }
    
    def _classify_object(
        self,
        image: np.ndarray,
        mask: np.ndarray
    ) -> str:
        """
        Classify object type (placeholder)
        In production, use CLIP or similar
        """
        # TODO: Implement actual classification
        # For now, return generic category based on size
        area = np.sum(mask)
        total_area = mask.shape[0] * mask.shape[1]
        ratio = area / total_area
        
        if ratio > 0.3:
            return "large_object"
        elif ratio > 0.1:
            return "medium_object"
        else:
            return "small_object"
    
    def visualize_segmentation(
        self,
        image: np.ndarray,
        segments: List[Dict],
        output_path: str
    ):
        """
        Visualize segmentation results
        
        Args:
            image: Input image
            segments: Segmentation results
            output_path: Output image path
        """
        # Create visualization
        vis_image = image.copy()
        
        # Generate random colors for each segment
        np.random.seed(42)
        colors = np.random.randint(0, 255, size=(len(segments), 3))
        
        # Draw masks
        for i, seg in enumerate(segments):
            if 'mask' not in seg:
                continue
            
            mask = seg['mask']
            color = colors[i]
            
            # Apply colored mask
            vis_image[mask] = vis_image[mask] * 0.5 + color * 0.5
            
            # Draw bounding box
            x, y, w, h = seg['bbox']
            cv2.rectangle(
                vis_image,
                (int(x), int(y)),
                (int(x + w), int(y + h)),
                color.tolist(),
                2
            )
            
            # Add label
            label = f"#{i} ({seg['area']}px)"
            cv2.putText(
                vis_image,
                label,
                (int(x), int(y) - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color.tolist(),
                2
            )
        
        # Save visualization
        cv2.imwrite(output_path, cv2.cvtColor(vis_image.astype(np.uint8), cv2.COLOR_RGB2BGR))
        logger.info(f"Saved visualization to {output_path}")
    
    def export_coco_annotations(
        self,
        annotations: Dict,
        output_path: str
    ):
        """
        Export annotations in COCO format
        
        Args:
            annotations: Annotation data
            output_path: Output JSON path
        """
        import json
        
        # Convert to COCO format
        coco_data = {
            'images': [{
                'id': 1,
                'width': annotations['image_shape'][1],
                'height': annotations['image_shape'][0],
                'file_name': 'image.jpg'
            }],
            'annotations': [],
            'categories': [
                {'id': 1, 'name': 'object', 'supercategory': 'thing'}
            ]
        }
        
        for obj in annotations['objects']:
            x, y, w, h = obj['bbox']
            
            coco_annotation = {
                'id': obj['id'],
                'image_id': 1,
                'category_id': 1,
                'bbox': [float(x), float(y), float(w), float(h)],
                'area': float(obj['area']),
                'iscrowd': 0,
                'segmentation': []  # RLE format would go here
            }
            
            coco_data['annotations'].append(coco_annotation)
        
        # Save to file
        with open(output_path, 'w') as f:
            json.dump(coco_data, f, indent=2)
        
        logger.info(f"Exported COCO annotations to {output_path}")


class ObjectTracker:
    """
    Track objects across video frames
    """
    
    def __init__(self):
        """Initialize object tracker"""
        self.tracks = {}
        self.next_track_id = 0
        
        logger.info("Initialized object tracker")
    
    def update(
        self,
        frame_id: int,
        detections: List[Dict]
    ) -> List[Dict]:
        """
        Update tracks with new detections
        
        Args:
            frame_id: Current frame ID
            detections: List of detections with 'bbox' and 'mask'
            
        Returns:
            List of tracked objects with track IDs
        """
        tracked_objects = []
        
        for detection in detections:
            # Find matching track
            track_id = self._match_detection(detection)
            
            if track_id is None:
                # Create new track
                track_id = self.next_track_id
                self.next_track_id += 1
                self.tracks[track_id] = []
            
            # Add to track
            self.tracks[track_id].append({
                'frame_id': frame_id,
                'bbox': detection['bbox'],
                'center': detection.get('center', (0, 0))
            })
            
            # Add track ID to detection
            detection['track_id'] = track_id
            tracked_objects.append(detection)
        
        return tracked_objects
    
    def _match_detection(self, detection: Dict) -> Optional[int]:
        """
        Match detection to existing track using IoU
        
        Args:
            detection: Detection with 'bbox'
            
        Returns:
            Track ID or None
        """
        if not self.tracks:
            return None
        
        best_iou = 0.3  # Minimum IoU threshold
        best_track_id = None
        
        det_bbox = detection['bbox']
        
        for track_id, track_history in self.tracks.items():
            if not track_history:
                continue
            
            # Get last detection in track
            last_det = track_history[-1]
            last_bbox = last_det['bbox']
            
            # Calculate IoU
            iou = self._calculate_iou(det_bbox, last_bbox)
            
            if iou > best_iou:
                best_iou = iou
                best_track_id = track_id
        
        return best_track_id
    
    def _calculate_iou(
        self,
        bbox1: List[float],
        bbox2: List[float]
    ) -> float:
        """Calculate IoU between two bounding boxes"""
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2
        
        # Calculate intersection
        x_left = max(x1, x2)
        y_top = max(y1, y2)
        x_right = min(x1 + w1, x2 + w2)
        y_bottom = min(y1 + h1, y2 + h2)
        
        if x_right < x_left or y_bottom < y_top:
            return 0.0
        
        intersection = (x_right - x_left) * (y_bottom - y_top)
        
        # Calculate union
        area1 = w1 * h1
        area2 = w2 * h2
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0


# Example usage
if __name__ == "__main__":
    # Initialize segmenter
    segmenter = SAMSegmenter(model_type="vit_h")
    
    # Load test image
    image = cv2.imread("test_image.jpg")
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # Segment image
    segments = segmenter.segment_image(image)
    
    # Create annotations
    annotations = segmenter.annotate_for_robot_training(image)
    
    # Visualize
    segmenter.visualize_segmentation(image, segments, "segmentation_result.jpg")
    
    # Export annotations
    segmenter.export_coco_annotations(annotations, "annotations.json")
    
    print(f"Segmented {len(segments)} objects")

# Made with Bob
