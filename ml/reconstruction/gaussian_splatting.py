"""
Gaussian Splatting for Real-time 3D Rendering
Based on "3D Gaussian Splatting for Real-Time Radiance Field Rendering"
"""
import torch
import torch.nn as nn
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class GaussianParams:
    """Parameters for a 3D Gaussian"""
    position: torch.Tensor  # (3,) - xyz position
    rotation: torch.Tensor  # (4,) - quaternion
    scale: torch.Tensor     # (3,) - xyz scale
    opacity: torch.Tensor   # (1,) - alpha value
    color: torch.Tensor     # (3,) or (48,) - RGB or SH coefficients


class GaussianModel(nn.Module):
    """
    3D Gaussian Splatting Model
    """
    
    def __init__(
        self,
        num_gaussians: int = 100000,
        sh_degree: int = 3,
        device: str = "cuda"
    ):
        """
        Initialize Gaussian model
        
        Args:
            num_gaussians: Number of 3D Gaussians
            sh_degree: Spherical harmonics degree for view-dependent color
            device: Device to use
        """
        super().__init__()
        
        self.num_gaussians = num_gaussians
        self.sh_degree = sh_degree
        self.device = device
        
        # Initialize Gaussian parameters
        self._init_gaussians()
        
        logger.info(f"Initialized Gaussian model with {num_gaussians} gaussians")
    
    def _init_gaussians(self):
        """Initialize Gaussian parameters"""
        # Positions - random initialization in unit cube
        self.positions = nn.Parameter(
            torch.randn(self.num_gaussians, 3, device=self.device) * 0.1
        )
        
        # Rotations - identity quaternions
        self.rotations = nn.Parameter(
            torch.zeros(self.num_gaussians, 4, device=self.device)
        )
        self.rotations.data[:, 0] = 1.0  # w component
        
        # Scales - small initial scales
        self.scales = nn.Parameter(
            torch.ones(self.num_gaussians, 3, device=self.device) * 0.01
        )
        
        # Opacities - sigmoid inverse of 0.1
        self.opacities = nn.Parameter(
            torch.logit(torch.ones(self.num_gaussians, 1, device=self.device) * 0.1)
        )
        
        # Colors - spherical harmonics coefficients
        # DC component (3) + SH components (sh_degree^2 - 1) * 3
        num_sh_coeffs = (self.sh_degree + 1) ** 2
        self.sh_coeffs = nn.Parameter(
            torch.zeros(self.num_gaussians, num_sh_coeffs, 3, device=self.device)
        )
    
    def get_rotation_matrix(self, quaternions: torch.Tensor) -> torch.Tensor:
        """
        Convert quaternions to rotation matrices
        
        Args:
            quaternions: (N, 4) quaternions [w, x, y, z]
            
        Returns:
            (N, 3, 3) rotation matrices
        """
        w, x, y, z = quaternions[:, 0], quaternions[:, 1], quaternions[:, 2], quaternions[:, 3]
        
        # Normalize quaternions
        norm = torch.sqrt(w**2 + x**2 + y**2 + z**2)
        w, x, y, z = w/norm, x/norm, y/norm, z/norm
        
        # Build rotation matrix
        R = torch.zeros(quaternions.shape[0], 3, 3, device=self.device)
        
        R[:, 0, 0] = 1 - 2*(y**2 + z**2)
        R[:, 0, 1] = 2*(x*y - w*z)
        R[:, 0, 2] = 2*(x*z + w*y)
        
        R[:, 1, 0] = 2*(x*y + w*z)
        R[:, 1, 1] = 1 - 2*(x**2 + z**2)
        R[:, 1, 2] = 2*(y*z - w*x)
        
        R[:, 2, 0] = 2*(x*z - w*y)
        R[:, 2, 1] = 2*(y*z + w*x)
        R[:, 2, 2] = 1 - 2*(x**2 + y**2)
        
        return R
    
    def get_covariance_matrix(self) -> torch.Tensor:
        """
        Compute 3D covariance matrices from scale and rotation
        
        Returns:
            (N, 3, 3) covariance matrices
        """
        # Get rotation matrices
        R = self.get_rotation_matrix(self.rotations)
        
        # Scale matrix
        S = torch.diag_embed(torch.exp(self.scales))
        
        # Covariance = R * S * S^T * R^T
        RS = torch.bmm(R, S)
        cov = torch.bmm(RS, RS.transpose(1, 2))
        
        return cov
    
    def project_gaussians(
        self,
        camera_matrix: torch.Tensor,
        image_size: Tuple[int, int]
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Project 3D Gaussians to 2D
        
        Args:
            camera_matrix: (3, 4) camera projection matrix
            image_size: (height, width)
            
        Returns:
            - 2D positions (N, 2)
            - 2D covariances (N, 2, 2)
            - depths (N,)
        """
        # Transform positions to camera space
        positions_homo = torch.cat([
            self.positions,
            torch.ones(self.num_gaussians, 1, device=self.device)
        ], dim=1)
        
        positions_cam = torch.matmul(camera_matrix, positions_homo.T).T
        
        # Project to image plane
        depths = positions_cam[:, 2]
        positions_2d = positions_cam[:, :2] / depths.unsqueeze(1)
        
        # Convert to pixel coordinates
        h, w = image_size
        positions_2d[:, 0] = (positions_2d[:, 0] + 1) * w / 2
        positions_2d[:, 1] = (positions_2d[:, 1] + 1) * h / 2
        
        # Project covariance to 2D
        cov_3d = self.get_covariance_matrix()
        
        # Jacobian of projection
        J = torch.zeros(self.num_gaussians, 2, 3, device=self.device)
        J[:, 0, 0] = 1 / depths
        J[:, 1, 1] = 1 / depths
        J[:, 0, 2] = -positions_cam[:, 0] / (depths ** 2)
        J[:, 1, 2] = -positions_cam[:, 1] / (depths ** 2)
        
        # Transform covariance: J * cov_3d * J^T
        cov_2d = torch.bmm(torch.bmm(J, cov_3d), J.transpose(1, 2))
        
        return positions_2d, cov_2d, depths
    
    def eval_sh(self, directions: torch.Tensor) -> torch.Tensor:
        """
        Evaluate spherical harmonics for view-dependent color
        
        Args:
            directions: (N, 3) viewing directions
            
        Returns:
            (N, 3) RGB colors
        """
        # DC component
        colors = self.sh_coeffs[:, 0, :]
        
        # Add higher order SH components
        if self.sh_degree > 0:
            # Normalize directions
            dirs = directions / (torch.norm(directions, dim=1, keepdim=True) + 1e-8)
            
            x, y, z = dirs[:, 0], dirs[:, 1], dirs[:, 2]
            
            # First order SH
            if self.sh_degree >= 1:
                colors = colors + self.sh_coeffs[:, 1, :] * y
                colors = colors + self.sh_coeffs[:, 2, :] * z
                colors = colors + self.sh_coeffs[:, 3, :] * x
            
            # Second order SH
            if self.sh_degree >= 2:
                colors = colors + self.sh_coeffs[:, 4, :] * (x * y)
                colors = colors + self.sh_coeffs[:, 5, :] * (y * z)
                colors = colors + self.sh_coeffs[:, 6, :] * (3 * z**2 - 1)
                colors = colors + self.sh_coeffs[:, 7, :] * (x * z)
                colors = colors + self.sh_coeffs[:, 8, :] * (x**2 - y**2)
        
        return torch.sigmoid(colors)
    
    def render(
        self,
        camera_matrix: torch.Tensor,
        camera_position: torch.Tensor,
        image_size: Tuple[int, int],
        background: torch.Tensor = None
    ) -> torch.Tensor:
        """
        Render image using Gaussian splatting
        
        Args:
            camera_matrix: (3, 4) camera projection matrix
            camera_position: (3,) camera position
            image_size: (height, width)
            background: (3,) background color
            
        Returns:
            (H, W, 3) rendered image
        """
        h, w = image_size
        
        if background is None:
            background = torch.zeros(3, device=self.device)
        
        # Project Gaussians to 2D
        positions_2d, cov_2d, depths = self.project_gaussians(camera_matrix, image_size)
        
        # Sort by depth (back to front)
        depth_order = torch.argsort(depths, descending=True)
        
        # Compute viewing directions
        view_dirs = self.positions - camera_position.unsqueeze(0)
        view_dirs = view_dirs / (torch.norm(view_dirs, dim=1, keepdim=True) + 1e-8)
        
        # Evaluate colors
        colors = self.eval_sh(view_dirs)
        
        # Get opacities
        opacities = torch.sigmoid(self.opacities)
        
        # Initialize output image
        image = torch.zeros(h, w, 3, device=self.device)
        alpha_acc = torch.zeros(h, w, 1, device=self.device)
        
        # Render each Gaussian (sorted by depth)
        for idx in depth_order:
            pos = positions_2d[idx]
            cov = cov_2d[idx]
            color = colors[idx]
            alpha = opacities[idx]
            
            # Skip if outside image
            if pos[0] < 0 or pos[0] >= w or pos[1] < 0 or pos[1] >= h:
                continue
            
            # Compute Gaussian weights for nearby pixels
            # For efficiency, only compute in a local window
            radius = 3 * torch.sqrt(torch.max(torch.diag(cov)))
            x_min = max(0, int(pos[0] - radius))
            x_max = min(w, int(pos[0] + radius) + 1)
            y_min = max(0, int(pos[1] - radius))
            y_max = min(h, int(pos[1] + radius) + 1)
            
            if x_max <= x_min or y_max <= y_min:
                continue
            
            # Create pixel grid
            y_grid, x_grid = torch.meshgrid(
                torch.arange(y_min, y_max, device=self.device),
                torch.arange(x_min, x_max, device=self.device),
                indexing='ij'
            )
            
            # Compute offset from Gaussian center
            dx = x_grid - pos[0]
            dy = y_grid - pos[1]
            offset = torch.stack([dx, dy], dim=-1)
            
            # Compute Gaussian weight
            # weight = exp(-0.5 * offset^T * cov^-1 * offset)
            cov_inv = torch.inverse(cov + torch.eye(2, device=self.device) * 1e-6)
            mahalanobis = torch.sum(
                offset @ cov_inv * offset,
                dim=-1
            )
            weight = torch.exp(-0.5 * mahalanobis) * alpha
            
            # Alpha blending
            weight = weight.unsqueeze(-1)
            current_alpha = alpha_acc[y_min:y_max, x_min:x_max]
            
            # Blend color
            image[y_min:y_max, x_min:x_max] += (
                color * weight * (1 - current_alpha)
            )
            
            # Update accumulated alpha
            alpha_acc[y_min:y_max, x_min:x_max] += weight * (1 - current_alpha)
        
        # Add background
        image = image + background * (1 - alpha_acc)
        
        return torch.clamp(image, 0, 1)
    
    def densify(self, grad_threshold: float = 0.0002):
        """
        Densify Gaussians by splitting/cloning based on gradients
        
        Args:
            grad_threshold: Gradient threshold for densification
        """
        # TODO: Implement adaptive densification
        # - Clone Gaussians with high gradients
        # - Split large Gaussians
        # - Remove transparent Gaussians
        pass
    
    def prune(self, opacity_threshold: float = 0.005):
        """
        Remove transparent Gaussians
        
        Args:
            opacity_threshold: Opacity threshold for pruning
        """
        opacities = torch.sigmoid(self.opacities)
        mask = opacities.squeeze() > opacity_threshold
        
        self.positions = nn.Parameter(self.positions[mask])
        self.rotations = nn.Parameter(self.rotations[mask])
        self.scales = nn.Parameter(self.scales[mask])
        self.opacities = nn.Parameter(self.opacities[mask])
        self.sh_coeffs = nn.Parameter(self.sh_coeffs[mask])
        
        self.num_gaussians = self.positions.shape[0]
        
        logger.info(f"Pruned to {self.num_gaussians} gaussians")


class GaussianSplattingTrainer:
    """
    Trainer for Gaussian Splatting
    """
    
    def __init__(
        self,
        model: GaussianModel,
        learning_rate: float = 0.001,
        device: str = "cuda"
    ):
        """
        Initialize trainer
        
        Args:
            model: Gaussian model
            learning_rate: Learning rate
            device: Device to use
        """
        self.model = model
        self.device = device
        
        # Optimizer with different learning rates for different parameters
        self.optimizer = torch.optim.Adam([
            {'params': [model.positions], 'lr': learning_rate * 0.1},
            {'params': [model.rotations], 'lr': learning_rate},
            {'params': [model.scales], 'lr': learning_rate},
            {'params': [model.opacities], 'lr': learning_rate},
            {'params': [model.sh_coeffs], 'lr': learning_rate * 0.1}
        ])
        
        logger.info("Initialized Gaussian Splatting trainer")
    
    def train_step(
        self,
        images: torch.Tensor,
        camera_matrices: torch.Tensor,
        camera_positions: torch.Tensor
    ) -> Dict[str, float]:
        """
        Single training step
        
        Args:
            images: (B, H, W, 3) ground truth images
            camera_matrices: (B, 3, 4) camera matrices
            camera_positions: (B, 3) camera positions
            
        Returns:
            Loss dictionary
        """
        self.optimizer.zero_grad()
        
        batch_size = images.shape[0]
        total_loss = 0
        
        for i in range(batch_size):
            # Render image
            rendered = self.model.render(
                camera_matrices[i],
                camera_positions[i],
                (images.shape[1], images.shape[2])
            )
            
            # Compute loss
            l1_loss = torch.abs(rendered - images[i]).mean()
            ssim_loss = 1 - self._ssim(rendered, images[i])
            
            loss = 0.8 * l1_loss + 0.2 * ssim_loss
            total_loss += loss
        
        # Backward pass
        total_loss.backward()
        self.optimizer.step()
        
        return {
            'loss': total_loss.item() / batch_size,
            'l1_loss': l1_loss.item(),
            'ssim_loss': ssim_loss.item()
        }
    
    def _ssim(self, img1: torch.Tensor, img2: torch.Tensor) -> torch.Tensor:
        """
        Compute SSIM between two images
        
        Args:
            img1: (H, W, 3) image 1
            img2: (H, W, 3) image 2
            
        Returns:
            SSIM value
        """
        # Simple SSIM implementation
        C1 = 0.01 ** 2
        C2 = 0.03 ** 2
        
        mu1 = img1.mean()
        mu2 = img2.mean()
        
        sigma1_sq = ((img1 - mu1) ** 2).mean()
        sigma2_sq = ((img2 - mu2) ** 2).mean()
        sigma12 = ((img1 - mu1) * (img2 - mu2)).mean()
        
        ssim = ((2 * mu1 * mu2 + C1) * (2 * sigma12 + C2)) / \
               ((mu1 ** 2 + mu2 ** 2 + C1) * (sigma1_sq + sigma2_sq + C2))
        
        return ssim
    
    def save_model(self, path: str):
        """Save model checkpoint"""
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'num_gaussians': self.model.num_gaussians
        }, path)
        
        logger.info(f"Saved model to {path}")
    
    def load_model(self, path: str):
        """Load model checkpoint"""
        checkpoint = torch.load(path)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        
        logger.info(f"Loaded model from {path}")

# Made with Bob
