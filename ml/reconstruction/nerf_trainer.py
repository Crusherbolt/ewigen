"""
NeRF Training Module
Handles Neural Radiance Fields training for 3D scene reconstruction
"""
import torch
import torch.nn as nn
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from loguru import logger
import json


@dataclass
class NeRFConfig:
    """Configuration for NeRF training"""
    num_iterations: int = 30000
    batch_size: int = 4096
    learning_rate: float = 5e-4
    num_layers: int = 8
    hidden_dim: int = 256
    num_encoding_functions: int = 10
    use_viewdirs: bool = True
    near: float = 2.0
    far: float = 6.0
    num_samples: int = 64
    num_importance_samples: int = 128
    chunk_size: int = 1024 * 32
    white_background: bool = False


class PositionalEncoding(nn.Module):
    """
    Positional encoding for input coordinates
    """
    def __init__(self, num_encoding_functions: int = 10):
        super().__init__()
        self.num_encoding_functions = num_encoding_functions
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Apply positional encoding to input
        x: [batch_size, 3] coordinates
        returns: [batch_size, 3 + 3*2*num_encoding_functions] encoded coordinates
        """
        encoding = [x]
        for i in range(self.num_encoding_functions):
            for fn in [torch.sin, torch.cos]:
                encoding.append(fn(2.0 ** i * np.pi * x))
        return torch.cat(encoding, dim=-1)


class NeRFModel(nn.Module):
    """
    Neural Radiance Field model
    """
    def __init__(self, config: NeRFConfig):
        super().__init__()
        self.config = config
        
        # Positional encoding
        self.pos_encoding = PositionalEncoding(config.num_encoding_functions)
        
        # Calculate input dimensions
        pos_dim = 3 + 3 * 2 * config.num_encoding_functions
        dir_dim = 3 + 3 * 2 * config.num_encoding_functions if config.use_viewdirs else 0
        
        # MLP layers
        layers = []
        in_dim = pos_dim
        
        for i in range(config.num_layers):
            out_dim = config.hidden_dim if i < config.num_layers - 1 else config.hidden_dim + 1
            layers.append(nn.Linear(in_dim, out_dim))
            
            if i < config.num_layers - 1:
                layers.append(nn.ReLU())
            
            # Skip connection at layer 4
            if i == 3:
                in_dim = config.hidden_dim + pos_dim
            else:
                in_dim = config.hidden_dim
        
        self.mlp = nn.Sequential(*layers)
        
        # View-dependent color network
        if config.use_viewdirs:
            self.color_mlp = nn.Sequential(
                nn.Linear(config.hidden_dim + dir_dim, config.hidden_dim // 2),
                nn.ReLU(),
                nn.Linear(config.hidden_dim // 2, 3),
                nn.Sigmoid()
            )
        else:
            self.color_mlp = nn.Sequential(
                nn.Linear(config.hidden_dim, 3),
                nn.Sigmoid()
            )
    
    def forward(
        self,
        positions: torch.Tensor,
        view_dirs: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass through NeRF
        positions: [batch_size, 3] 3D positions
        view_dirs: [batch_size, 3] viewing directions (optional)
        returns: (rgb, density) each [batch_size, 3/1]
        """
        # Encode positions
        pos_encoded = self.pos_encoding(positions)
        
        # Pass through MLP
        x = pos_encoded
        for i, layer in enumerate(self.mlp):
            x = layer(x)
            # Skip connection
            if i == 6:  # After 4th layer
                x = torch.cat([x, pos_encoded], dim=-1)
        
        # Extract density and features
        density = torch.relu(x[..., 0:1])
        features = x[..., 1:]
        
        # Compute color
        if self.config.use_viewdirs and view_dirs is not None:
            dir_encoded = self.pos_encoding(view_dirs)
            color_input = torch.cat([features, dir_encoded], dim=-1)
        else:
            color_input = features
        
        rgb = self.color_mlp(color_input)
        
        return rgb, density


class NeRFTrainer:
    """
    NeRF training pipeline
    """
    def __init__(self, config: NeRFConfig, device: str = "cuda"):
        self.config = config
        self.device = device
        
        # Initialize model
        self.model = NeRFModel(config).to(device)
        self.optimizer = torch.optim.Adam(
            self.model.parameters(),
            lr=config.learning_rate
        )
        
        # Learning rate scheduler
        self.scheduler = torch.optim.lr_scheduler.ExponentialLR(
            self.optimizer,
            gamma=0.1 ** (1 / config.num_iterations)
        )
        
        logger.info(f"NeRF model initialized on {device}")
    
    def volume_rendering(
        self,
        rgb: torch.Tensor,
        density: torch.Tensor,
        z_vals: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Perform volume rendering
        """
        # Calculate distances between samples
        dists = z_vals[..., 1:] - z_vals[..., :-1]
        dists = torch.cat([
            dists,
            torch.full_like(dists[..., :1], 1e10)
        ], dim=-1)
        
        # Calculate alpha values
        alpha = 1.0 - torch.exp(-density[..., 0] * dists)
        
        # Calculate transmittance
        transmittance = torch.cumprod(
            torch.cat([
                torch.ones_like(alpha[..., :1]),
                1.0 - alpha[..., :-1] + 1e-10
            ], dim=-1),
            dim=-1
        )
        
        # Calculate weights
        weights = alpha * transmittance
        
        # Composite RGB
        rgb_map = torch.sum(weights[..., None] * rgb, dim=-2)
        
        # Calculate depth
        depth_map = torch.sum(weights * z_vals, dim=-1)
        
        # Calculate accumulated alpha
        acc_map = torch.sum(weights, dim=-1)
        
        # Add white background if configured
        if self.config.white_background:
            rgb_map = rgb_map + (1.0 - acc_map[..., None])
        
        return rgb_map, depth_map, weights
    
    def render_rays(
        self,
        ray_origins: torch.Tensor,
        ray_directions: torch.Tensor
    ) -> Dict[str, torch.Tensor]:
        """
        Render rays through the scene
        """
        # Sample points along rays
        z_vals = torch.linspace(
            self.config.near,
            self.config.far,
            self.config.num_samples,
            device=self.device
        )
        
        # Add noise to sample positions
        if self.model.training:
            z_vals = z_vals + torch.rand_like(z_vals) * (
                self.config.far - self.config.near
            ) / self.config.num_samples
        
        # Calculate 3D positions
        positions = ray_origins[..., None, :] + \
                   ray_directions[..., None, :] * z_vals[..., :, None]
        
        # Flatten for network
        positions_flat = positions.reshape(-1, 3)
        directions_flat = ray_directions[..., None, :].expand_as(positions).reshape(-1, 3)
        
        # Forward pass through network
        rgb, density = self.model(positions_flat, directions_flat)
        
        # Reshape back
        rgb = rgb.reshape(*positions.shape[:-1], 3)
        density = density.reshape(*positions.shape[:-1], 1)
        
        # Volume rendering
        rgb_map, depth_map, weights = self.volume_rendering(rgb, density, z_vals)
        
        return {
            "rgb": rgb_map,
            "depth": depth_map,
            "weights": weights
        }
    
    def train_step(
        self,
        ray_batch: Dict[str, torch.Tensor]
    ) -> Dict[str, float]:
        """
        Single training step
        """
        self.model.train()
        self.optimizer.zero_grad()
        
        # Render rays
        outputs = self.render_rays(
            ray_batch["origins"],
            ray_batch["directions"]
        )
        
        # Calculate loss
        rgb_loss = torch.mean((outputs["rgb"] - ray_batch["rgb"]) ** 2)
        
        # Backward pass
        rgb_loss.backward()
        self.optimizer.step()
        self.scheduler.step()
        
        return {
            "loss": rgb_loss.item(),
            "psnr": -10.0 * torch.log10(rgb_loss).item()
        }
    
    def train(
        self,
        train_data: Dict,
        val_data: Optional[Dict] = None,
        checkpoint_dir: Optional[str] = None
    ):
        """
        Full training loop
        """
        logger.info("Starting NeRF training...")
        
        if checkpoint_dir:
            checkpoint_path = Path(checkpoint_dir)
            checkpoint_path.mkdir(parents=True, exist_ok=True)
        
        for iteration in range(self.config.num_iterations):
            # Sample random rays
            ray_batch = self._sample_rays(train_data, self.config.batch_size)
            
            # Training step
            metrics = self.train_step(ray_batch)
            
            # Logging
            if iteration % 100 == 0:
                logger.info(
                    f"Iteration {iteration}/{self.config.num_iterations} | "
                    f"Loss: {metrics['loss']:.4f} | PSNR: {metrics['psnr']:.2f}"
                )
            
            # Validation
            if val_data and iteration % 1000 == 0:
                val_metrics = self.validate(val_data)
                logger.info(f"Validation PSNR: {val_metrics['psnr']:.2f}")
            
            # Save checkpoint
            if checkpoint_dir and iteration % 5000 == 0:
                self.save_checkpoint(
                    checkpoint_path / f"checkpoint_{iteration}.pth",
                    iteration
                )
        
        logger.info("Training complete!")
    
    def _sample_rays(self, data: Dict, num_rays: int) -> Dict[str, torch.Tensor]:
        """
        Sample random rays from dataset
        """
        # TODO: Implement proper ray sampling from camera data
        # This is a placeholder
        return {
            "origins": torch.randn(num_rays, 3, device=self.device),
            "directions": torch.randn(num_rays, 3, device=self.device),
            "rgb": torch.rand(num_rays, 3, device=self.device)
        }
    
    def validate(self, val_data: Dict) -> Dict[str, float]:
        """
        Validation step
        """
        self.model.eval()
        
        with torch.no_grad():
            ray_batch = self._sample_rays(val_data, 1024)
            outputs = self.render_rays(
                ray_batch["origins"],
                ray_batch["directions"]
            )
            
            mse = torch.mean((outputs["rgb"] - ray_batch["rgb"]) ** 2)
            psnr = -10.0 * torch.log10(mse)
        
        return {"psnr": psnr.item()}
    
    def save_checkpoint(self, path: str, iteration: int):
        """
        Save model checkpoint
        """
        torch.save({
            "iteration": iteration,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "config": self.config.__dict__
        }, path)
        
        logger.info(f"Checkpoint saved to {path}")
    
    def load_checkpoint(self, path: str):
        """
        Load model checkpoint
        """
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        
        logger.info(f"Checkpoint loaded from {path}")
        return checkpoint["iteration"]

# Made with Bob
