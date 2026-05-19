"""
Dataset Export Module
Export 3D scenes to various formats for robot training
"""
import os
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from loguru import logger


@dataclass
class DatasetMetadata:
    """Dataset metadata"""
    name: str
    description: str
    format: str
    num_frames: int
    num_objects: int
    has_depth: bool
    has_normals: bool
    has_semantics: bool
    scene_bounds: Tuple[List[float], List[float]]


class DatasetExporter:
    """
    Export 3D scenes to robot training formats
    """
    
    def __init__(self):
        logger.info("Dataset exporter initialized")
    
    def export_to_usd(
        self,
        scene_data: Dict,
        output_path: str,
        include_animations: bool = True
    ):
        """
        Export scene to USD (Universal Scene Description) format
        Compatible with NVIDIA Omniverse and Isaac Sim
        """
        logger.info(f"Exporting to USD: {output_path}")
        
        try:
            from pxr import Usd, UsdGeom, Gf, Sdf
            
            # Create USD stage
            stage = Usd.Stage.CreateNew(output_path)
            
            # Set up axis and units
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
            UsdGeom.SetStageMetersPerUnit(stage, 1.0)
            
            # Create root prim
            root_prim = stage.DefinePrim("/World", "Xform")
            stage.SetDefaultPrim(root_prim)
            
            # Export meshes
            if "meshes" in scene_data:
                self._export_meshes_to_usd(stage, scene_data["meshes"])
            
            # Export cameras
            if "cameras" in scene_data:
                self._export_cameras_to_usd(stage, scene_data["cameras"])
            
            # Export lights
            if "lights" in scene_data:
                self._export_lights_to_usd(stage, scene_data["lights"])
            
            # Export animations
            if include_animations and "animations" in scene_data:
                self._export_animations_to_usd(stage, scene_data["animations"])
            
            # Save stage
            stage.Save()
            
            logger.info(f"USD export complete: {output_path}")
            
        except ImportError:
            logger.error("USD library not found. Install with: pip install usd-core")
            raise
        except Exception as e:
            logger.error(f"USD export failed: {e}")
            raise
    
    def _export_meshes_to_usd(self, stage, meshes: List[Dict]):
        """Export meshes to USD"""
        from pxr import UsdGeom, Gf
        
        for i, mesh_data in enumerate(meshes):
            mesh_path = f"/World/Mesh_{i}"
            mesh = UsdGeom.Mesh.Define(stage, mesh_path)
            
            # Set vertices
            vertices = mesh_data.get("vertices", [])
            mesh.CreatePointsAttr(vertices)
            
            # Set faces
            faces = mesh_data.get("faces", [])
            face_vertex_counts = [len(f) for f in faces]
            face_vertex_indices = [idx for face in faces for idx in face]
            
            mesh.CreateFaceVertexCountsAttr(face_vertex_counts)
            mesh.CreateFaceVertexIndicesAttr(face_vertex_indices)
            
            # Set normals
            if "normals" in mesh_data:
                mesh.CreateNormalsAttr(mesh_data["normals"])
            
            # Set UVs
            if "uvs" in mesh_data:
                texCoords = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar(
                    "st",
                    Sdf.ValueTypeNames.TexCoord2fArray
                )
                texCoords.Set(mesh_data["uvs"])
    
    def _export_cameras_to_usd(self, stage, cameras: List[Dict]):
        """Export cameras to USD"""
        from pxr import UsdGeom, Gf
        
        for i, cam_data in enumerate(cameras):
            cam_path = f"/World/Camera_{i}"
            camera = UsdGeom.Camera.Define(stage, cam_path)
            
            # Set camera parameters
            camera.CreateFocalLengthAttr(cam_data.get("focal_length", 50.0))
            camera.CreateHorizontalApertureAttr(cam_data.get("sensor_width", 36.0))
            camera.CreateVerticalApertureAttr(cam_data.get("sensor_height", 24.0))
            
            # Set transform
            if "transform" in cam_data:
                xform = UsdGeom.Xformable(camera)
                xform.AddTransformOp().Set(Gf.Matrix4d(cam_data["transform"]))
    
    def _export_lights_to_usd(self, stage, lights: List[Dict]):
        """Export lights to USD"""
        from pxr import UsdLux
        
        for i, light_data in enumerate(lights):
            light_type = light_data.get("type", "distant")
            light_path = f"/World/Light_{i}"
            
            if light_type == "distant":
                light = UsdLux.DistantLight.Define(stage, light_path)
            elif light_type == "sphere":
                light = UsdLux.SphereLight.Define(stage, light_path)
            else:
                light = UsdLux.DomeLight.Define(stage, light_path)
            
            # Set intensity
            light.CreateIntensityAttr(light_data.get("intensity", 1.0))
    
    def _export_animations_to_usd(self, stage, animations: List[Dict]):
        """Export animations to USD"""
        # Placeholder for animation export
        logger.info("Animation export to USD not fully implemented")
    
    def export_to_ros_bag(
        self,
        scene_data: Dict,
        output_path: str,
        fps: float = 30.0
    ):
        """
        Export scene to ROS bag format
        """
        logger.info(f"Exporting to ROS bag: {output_path}")
        
        try:
            import rosbag
            from sensor_msgs.msg import Image, CameraInfo, PointCloud2
            from geometry_msgs.msg import TransformStamped
            import cv_bridge
            
            bridge = cv_bridge.CvBridge()
            
            with rosbag.Bag(output_path, 'w') as bag:
                # Export images
                if "images" in scene_data:
                    for i, img_data in enumerate(scene_data["images"]):
                        timestamp = rospy.Time.from_sec(i / fps)
                        
                        # RGB image
                        if "rgb" in img_data:
                            img_msg = bridge.cv2_to_imgmsg(img_data["rgb"], "bgr8")
                            img_msg.header.stamp = timestamp
                            bag.write("/camera/rgb/image_raw", img_msg, timestamp)
                        
                        # Depth image
                        if "depth" in img_data:
                            depth_msg = bridge.cv2_to_imgmsg(img_data["depth"], "32FC1")
                            depth_msg.header.stamp = timestamp
                            bag.write("/camera/depth/image_raw", depth_msg, timestamp)
                
                # Export camera info
                if "camera_info" in scene_data:
                    cam_info = self._create_camera_info_msg(scene_data["camera_info"])
                    bag.write("/camera/camera_info", cam_info)
                
                # Export point clouds
                if "point_clouds" in scene_data:
                    for i, pc_data in enumerate(scene_data["point_clouds"]):
                        timestamp = rospy.Time.from_sec(i / fps)
                        pc_msg = self._create_pointcloud2_msg(pc_data)
                        pc_msg.header.stamp = timestamp
                        bag.write("/point_cloud", pc_msg, timestamp)
            
            logger.info(f"ROS bag export complete: {output_path}")
            
        except ImportError:
            logger.error("ROS libraries not found. Install ROS or rosbag.")
            raise
        except Exception as e:
            logger.error(f"ROS bag export failed: {e}")
            raise
    
    def _create_camera_info_msg(self, cam_info: Dict):
        """Create ROS CameraInfo message"""
        from sensor_msgs.msg import CameraInfo
        
        msg = CameraInfo()
        msg.width = cam_info.get("width", 640)
        msg.height = cam_info.get("height", 480)
        msg.K = cam_info.get("K", [0] * 9)
        msg.D = cam_info.get("D", [0] * 5)
        msg.R = cam_info.get("R", [1, 0, 0, 0, 1, 0, 0, 0, 1])
        msg.P = cam_info.get("P", [0] * 12)
        
        return msg
    
    def _create_pointcloud2_msg(self, pc_data: Dict):
        """Create ROS PointCloud2 message"""
        from sensor_msgs.msg import PointCloud2, PointField
        import struct
        
        msg = PointCloud2()
        msg.header.frame_id = "world"
        msg.height = 1
        msg.width = len(pc_data["points"])
        
        # Define fields
        msg.fields = [
            PointField('x', 0, PointField.FLOAT32, 1),
            PointField('y', 4, PointField.FLOAT32, 1),
            PointField('z', 8, PointField.FLOAT32, 1),
        ]
        
        if "colors" in pc_data:
            msg.fields.append(PointField('rgb', 12, PointField.FLOAT32, 1))
        
        msg.is_bigendian = False
        msg.point_step = 12 if "colors" not in pc_data else 16
        msg.row_step = msg.point_step * msg.width
        msg.is_dense = True
        
        # Pack data
        buffer = []
        for i, point in enumerate(pc_data["points"]):
            buffer.append(struct.pack('fff', *point))
            if "colors" in pc_data:
                rgb = struct.unpack('I', struct.pack('BBBB', *pc_data["colors"][i], 0))[0]
                buffer.append(struct.pack('f', rgb))
        
        msg.data = b''.join(buffer)
        
        return msg
    
    def export_metadata(
        self,
        metadata: DatasetMetadata,
        output_path: str
    ):
        """Export dataset metadata to JSON"""
        data = {
            "name": metadata.name,
            "description": metadata.description,
            "format": metadata.format,
            "num_frames": metadata.num_frames,
            "num_objects": metadata.num_objects,
            "has_depth": metadata.has_depth,
            "has_normals": metadata.has_normals,
            "has_semantics": metadata.has_semantics,
            "scene_bounds": {
                "min": metadata.scene_bounds[0],
                "max": metadata.scene_bounds[1]
            }
        }
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Metadata exported to {output_path}")
    
    def create_dataset_package(
        self,
        scene_data: Dict,
        output_dir: str,
        formats: List[str] = ["usd", "json"]
    ):
        """
        Create complete dataset package with multiple formats
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Creating dataset package in {output_dir}")
        
        # Export to requested formats
        if "usd" in formats:
            usd_path = output_path / "scene.usd"
            self.export_to_usd(scene_data, str(usd_path))
        
        if "ros" in formats:
            bag_path = output_path / "scene.bag"
            self.export_to_ros_bag(scene_data, str(bag_path))
        
        if "json" in formats:
            json_path = output_path / "scene.json"
            with open(json_path, 'w') as f:
                json.dump(scene_data, f, indent=2, default=str)
        
        # Export metadata
        metadata = DatasetMetadata(
            name=scene_data.get("name", "scene"),
            description=scene_data.get("description", ""),
            format=",".join(formats),
            num_frames=len(scene_data.get("images", [])),
            num_objects=len(scene_data.get("objects", [])),
            has_depth=scene_data.get("has_depth", False),
            has_normals=scene_data.get("has_normals", False),
            has_semantics=scene_data.get("has_semantics", False),
            scene_bounds=scene_data.get("bounds", ([0, 0, 0], [1, 1, 1]))
        )
        
        self.export_metadata(metadata, str(output_path / "metadata.json"))
        
        # Create README
        self._create_readme(output_path, metadata)
        
        logger.info(f"Dataset package created: {output_dir}")
    
    def _create_readme(self, output_path: Path, metadata: DatasetMetadata):
        """Create README for dataset"""
        readme_content = f"""# {metadata.name}

{metadata.description}

## Dataset Information

- **Format:** {metadata.format}
- **Number of Frames:** {metadata.num_frames}
- **Number of Objects:** {metadata.num_objects}
- **Has Depth:** {metadata.has_depth}
- **Has Normals:** {metadata.has_normals}
- **Has Semantics:** {metadata.has_semantics}

## Scene Bounds

- **Min:** {metadata.scene_bounds[0]}
- **Max:** {metadata.scene_bounds[1]}

## Usage

### USD Format
```python
from pxr import Usd
stage = Usd.Stage.Open("scene.usd")
```

### ROS Bag Format
```bash
rosbag play scene.bag
```

### JSON Format
```python
import json
with open("scene.json") as f:
    data = json.load(f)
```

## License

Please refer to the main project license.
"""
        
        with open(output_path / "README.md", 'w') as f:
            f.write(readme_content)

# Made with Bob
