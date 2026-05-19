"""
Camera Calibration Module
Uses COLMAP for Structure from Motion and camera calibration
"""
import os
import subprocess
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import json
from loguru import logger


@dataclass
class CameraIntrinsics:
    """Camera intrinsic parameters"""
    fx: float  # Focal length x
    fy: float  # Focal length y
    cx: float  # Principal point x
    cy: float  # Principal point y
    width: int
    height: int
    distortion: List[float]  # Distortion coefficients


@dataclass
class CameraExtrinsics:
    """Camera extrinsic parameters"""
    rotation: np.ndarray  # 3x3 rotation matrix
    translation: np.ndarray  # 3x1 translation vector
    camera_id: int
    image_name: str


class CameraCalibrator:
    """
    Camera calibration using COLMAP
    """
    
    def __init__(self, colmap_path: str = "colmap"):
        self.colmap_path = colmap_path
        self._check_colmap()
        
        logger.info("Camera calibrator initialized")
    
    def _check_colmap(self):
        """Check if COLMAP is installed"""
        try:
            result = subprocess.run(
                [self.colmap_path, "--version"],
                capture_output=True,
                text=True
            )
            logger.info(f"COLMAP version: {result.stdout.strip()}")
        except FileNotFoundError:
            logger.error("COLMAP not found. Please install COLMAP.")
            raise
    
    def calibrate_from_images(
        self,
        image_dir: str,
        output_dir: str,
        camera_model: str = "OPENCV"
    ) -> Dict:
        """
        Calibrate cameras from images using COLMAP
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        database_path = output_path / "database.db"
        sparse_path = output_path / "sparse"
        sparse_path.mkdir(exist_ok=True)
        
        logger.info(f"Starting COLMAP calibration for {image_dir}")
        
        # Step 1: Feature extraction
        self._run_feature_extraction(image_dir, database_path, camera_model)
        
        # Step 2: Feature matching
        self._run_feature_matching(database_path)
        
        # Step 3: Sparse reconstruction
        self._run_sparse_reconstruction(database_path, image_dir, sparse_path)
        
        # Step 4: Parse results
        cameras, images, points = self._parse_colmap_output(sparse_path / "0")
        
        logger.info(f"Calibration complete: {len(cameras)} cameras, {len(images)} images")
        
        return {
            "cameras": cameras,
            "images": images,
            "points": points,
            "output_dir": str(output_path)
        }
    
    def _run_feature_extraction(
        self,
        image_dir: str,
        database_path: Path,
        camera_model: str
    ):
        """Run COLMAP feature extraction"""
        logger.info("Extracting features...")
        
        cmd = [
            self.colmap_path, "feature_extractor",
            "--database_path", str(database_path),
            "--image_path", image_dir,
            "--ImageReader.camera_model", camera_model,
            "--ImageReader.single_camera", "0"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Feature extraction failed: {result.stderr}")
            raise RuntimeError("Feature extraction failed")
        
        logger.info("Feature extraction complete")
    
    def _run_feature_matching(self, database_path: Path):
        """Run COLMAP feature matching"""
        logger.info("Matching features...")
        
        cmd = [
            self.colmap_path, "exhaustive_matcher",
            "--database_path", str(database_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Feature matching failed: {result.stderr}")
            raise RuntimeError("Feature matching failed")
        
        logger.info("Feature matching complete")
    
    def _run_sparse_reconstruction(
        self,
        database_path: Path,
        image_dir: str,
        sparse_path: Path
    ):
        """Run COLMAP sparse reconstruction"""
        logger.info("Running sparse reconstruction...")
        
        cmd = [
            self.colmap_path, "mapper",
            "--database_path", str(database_path),
            "--image_path", image_dir,
            "--output_path", str(sparse_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Sparse reconstruction failed: {result.stderr}")
            raise RuntimeError("Sparse reconstruction failed")
        
        logger.info("Sparse reconstruction complete")
    
    def _parse_colmap_output(
        self,
        sparse_dir: Path
    ) -> Tuple[Dict, Dict, np.ndarray]:
        """Parse COLMAP output files"""
        cameras = self._read_cameras(sparse_dir / "cameras.txt")
        images = self._read_images(sparse_dir / "images.txt")
        points = self._read_points(sparse_dir / "points3D.txt")
        
        return cameras, images, points
    
    def _read_cameras(self, cameras_file: Path) -> Dict[int, CameraIntrinsics]:
        """Read cameras.txt file"""
        cameras = {}
        
        if not cameras_file.exists():
            logger.warning(f"Cameras file not found: {cameras_file}")
            return cameras
        
        with open(cameras_file, 'r') as f:
            for line in f:
                if line.startswith('#'):
                    continue
                
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                
                camera_id = int(parts[0])
                model = parts[1]
                width = int(parts[2])
                height = int(parts[3])
                params = [float(p) for p in parts[4:]]
                
                # Parse based on model
                if model == "PINHOLE":
                    fx, fy, cx, cy = params[:4]
                    distortion = []
                elif model == "OPENCV":
                    fx, fy, cx, cy = params[:4]
                    distortion = params[4:] if len(params) > 4 else []
                else:
                    fx = fy = params[0] if params else 0
                    cx = width / 2
                    cy = height / 2
                    distortion = params[1:] if len(params) > 1 else []
                
                cameras[camera_id] = CameraIntrinsics(
                    fx=fx, fy=fy, cx=cx, cy=cy,
                    width=width, height=height,
                    distortion=distortion
                )
        
        return cameras
    
    def _read_images(self, images_file: Path) -> Dict[int, CameraExtrinsics]:
        """Read images.txt file"""
        images = {}
        
        if not images_file.exists():
            logger.warning(f"Images file not found: {images_file}")
            return images
        
        with open(images_file, 'r') as f:
            lines = f.readlines()
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith('#') or not line:
                i += 1
                continue
            
            parts = line.split()
            if len(parts) < 10:
                i += 1
                continue
            
            image_id = int(parts[0])
            qw, qx, qy, qz = [float(p) for p in parts[1:5]]
            tx, ty, tz = [float(p) for p in parts[5:8]]
            camera_id = int(parts[8])
            image_name = parts[9]
            
            # Convert quaternion to rotation matrix
            rotation = self._quat_to_rotation(qw, qx, qy, qz)
            translation = np.array([tx, ty, tz])
            
            images[image_id] = CameraExtrinsics(
                rotation=rotation,
                translation=translation,
                camera_id=camera_id,
                image_name=image_name
            )
            
            i += 2  # Skip points line
        
        return images
    
    def _read_points(self, points_file: Path) -> np.ndarray:
        """Read points3D.txt file"""
        points = []
        
        if not points_file.exists():
            logger.warning(f"Points file not found: {points_file}")
            return np.array([])
        
        with open(points_file, 'r') as f:
            for line in f:
                if line.startswith('#'):
                    continue
                
                parts = line.strip().split()
                if len(parts) < 6:
                    continue
                
                x, y, z = [float(p) for p in parts[1:4]]
                points.append([x, y, z])
        
        return np.array(points)
    
    def _quat_to_rotation(
        self,
        qw: float,
        qx: float,
        qy: float,
        qz: float
    ) -> np.ndarray:
        """Convert quaternion to rotation matrix"""
        R = np.array([
            [1 - 2*qy**2 - 2*qz**2, 2*qx*qy - 2*qz*qw, 2*qx*qz + 2*qy*qw],
            [2*qx*qy + 2*qz*qw, 1 - 2*qx**2 - 2*qz**2, 2*qy*qz - 2*qx*qw],
            [2*qx*qz - 2*qy*qw, 2*qy*qz + 2*qx*qw, 1 - 2*qx**2 - 2*qy**2]
        ])
        return R
    
    def export_to_json(
        self,
        cameras: Dict,
        images: Dict,
        output_path: str
    ):
        """Export calibration to JSON"""
        data = {
            "cameras": {},
            "images": {}
        }
        
        # Export cameras
        for cam_id, cam in cameras.items():
            data["cameras"][str(cam_id)] = {
                "fx": cam.fx,
                "fy": cam.fy,
                "cx": cam.cx,
                "cy": cam.cy,
                "width": cam.width,
                "height": cam.height,
                "distortion": cam.distortion
            }
        
        # Export images
        for img_id, img in images.items():
            data["images"][str(img_id)] = {
                "camera_id": img.camera_id,
                "image_name": img.image_name,
                "rotation": img.rotation.tolist(),
                "translation": img.translation.tolist()
            }
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Calibration exported to {output_path}")
    
    def undistort_images(
        self,
        image_dir: str,
        output_dir: str,
        sparse_dir: str
    ):
        """Undistort images using COLMAP"""
        logger.info("Undistorting images...")
        
        cmd = [
            self.colmap_path, "image_undistorter",
            "--image_path", image_dir,
            "--input_path", sparse_dir,
            "--output_path", output_dir,
            "--output_type", "COLMAP"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Image undistortion failed: {result.stderr}")
            raise RuntimeError("Image undistortion failed")
        
        logger.info("Image undistortion complete")
    
    def calculate_scene_bounds(
        self,
        points: np.ndarray,
        percentile: float = 5.0
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Calculate scene bounds from 3D points"""
        if len(points) == 0:
            return np.array([0, 0, 0]), np.array([1, 1, 1])
        
        # Use percentiles to remove outliers
        min_bounds = np.percentile(points, percentile, axis=0)
        max_bounds = np.percentile(points, 100 - percentile, axis=0)
        
        return min_bounds, max_bounds

# Made with Bob
