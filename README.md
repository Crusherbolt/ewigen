# ⏳ Ewigen - Timeless Moments

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Architecture-e94560?style=for-the-badge)](https://crusherbolt.github.io/ewigen/)
[![License](https://img.shields.io/badge/License-MIT-533483?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-1a1a2e?style=for-the-badge&logo=python)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-16213e?style=for-the-badge&logo=docker)](https://docker.com)

> **Preserve your most precious moments forever through immersive virtual reality**

---

## 🎯 [View Interactive Architecture →](https://crusherbolt.github.io/ewigen/)

---

## 🌟 Project Overview

**Ewigen** (German for "Timeless") is a cutting-edge platform that transforms multi-angle video recordings into fully interactive 3D virtual environments. Capture real-world spaces and moments, then relive them in immersive VR with AI-powered interactive characters.

### Two Revolutionary Use Cases

#### 1. **Humanoid Robot Training Datasets (B2B)** 🤖
Generate high-fidelity 3D environments and human motion datasets for training humanoid robots and autonomous systems. Export data in industry-standard formats (USD, ROS, URDF) compatible with NVIDIA Omniverse, Isaac Sim, and major robotics frameworks.

**Value Proposition:**
- Synthetic training data generation
- Realistic human motion capture
- Multi-modal sensor simulation
- Scalable dataset production

#### 2. **Immersive Memory Recreation (B2C)** 💝
Transform special moments—weddings, family gatherings, concerts—into interactive VR experiences. Walk through reconstructed spaces, interact with AI-powered avatars of people, and relive memories as if you were there.

**Value Proposition:**
- Preserve precious moments forever
- Interact with loved ones in VR
- Relive experiences from any angle
- Share memories with future generations

---

## ✨ Key Features

- **📹 Multi-View 3D Reconstruction**: Convert multiple video angles into photorealistic 3D environments using Neural Radiance Fields (NeRF) and Gaussian Splatting
- **👤 Human Avatar Generation**: Automatically detect, track, and create realistic 3D avatars from video footage
- **🎭 Motion Capture**: Extract natural human movements and gestures for animation
- **🗣️ Voice Cloning**: Replicate voices for authentic character interactions
- **🤖 AI Conversations**: Engage in natural conversations with virtual characters powered by advanced language models
- **🥽 VR Experience**: Explore reconstructed environments in immersive virtual reality
- **📊 Dataset Export**: Generate training datasets for robotics and AI research
- **☁️ Cloud Processing**: Scalable infrastructure for processing large video collections

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                       │
│              Web Dashboard + Project Management              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Backend API (FastAPI)                      │
│         Authentication │ Projects │ Processing Queue         │
└─────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┼─────────────┐
                ▼             ▼             ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │ 3D Recon     │  │ Character    │  │ AI Services  │
    │ - NeRF       │  │ - Detection  │  │ - Voice      │
    │ - Gaussian   │  │ - Avatars    │  │ - Speech     │
    │ - COLMAP     │  │ - Animation  │  │ - LLM        │
    └──────────────┘  └──────────────┘  └──────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  VR Application  │
                    │     (Unity)      │
                    └──────────────────┘
```

**[📊 View Full Interactive Architecture](https://YOUR_USERNAME.github.io/YOUR_REPO_NAME/)**

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **Docker & Docker Compose**
- **NVIDIA GPU** (recommended: RTX 3090 or better with 24GB+ VRAM)
- **CUDA 11.8+**
- **16GB+ RAM** (32GB recommended)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/YOUR_USERNAME/ewigen.git
cd ewigen
```

2. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Run with Docker (Recommended)**
```bash
# Make deployment script executable (Linux/Mac)
chmod +x deploy.sh

# Or on Windows PowerShell
# No need to chmod

# Start all services
./deploy.sh local
```

4. **Access the application**
- **API Documentation**: http://localhost:8000/api/v1/docs
- **Web Dashboard**: http://localhost:3000
- **MinIO Console**: http://localhost:9001

---

## 📖 Usage

### 1. Upload Videos

Upload multiple video recordings of your environment from different angles through the web dashboard or API.

### 2. Process Videos

The platform automatically:
- Extracts frames and synchronizes videos
- Calibrates cameras using COLMAP
- Reconstructs 3D environment with NeRF
- Detects and tracks people
- Generates 3D avatars
- Clones voices from audio
- Creates interactive AI characters

### 3. Export Results

**For Robot Training:**
```bash
# Export as USD format (NVIDIA Omniverse)
curl -X POST "http://localhost:8000/api/v1/projects/{id}/export" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"format": "usd", "include_annotations": true}'
```

**For VR Experience:**
- Download the Unity VR application
- Load your reconstructed environment
- Put on your VR headset and explore

---

## 🛠️ Technology Stack

### Backend
- **FastAPI**: High-performance async Python web framework
- **PostgreSQL**: Relational database for metadata
- **Redis**: Caching and message broker
- **Celery**: Distributed task queue for video processing
- **MinIO**: S3-compatible object storage

### Machine Learning
- **PyTorch**: Deep learning framework
- **NeRF (Instant-NGP)**: 3D scene reconstruction
- **Gaussian Splatting**: Real-time rendering (60+ FPS)
- **COLMAP**: Structure from Motion
- **YOLOv8**: Human detection
- **MediaPipe**: Pose estimation
- **SMPL-X**: Parametric human body model
- **Whisper**: Speech recognition
- **Coqui TTS**: Voice synthesis
- **GPT-4/Claude**: Conversational AI

### Frontend
- **Next.js 14**: React framework with App Router
- **TypeScript**: Type-safe JavaScript
- **Tailwind CSS**: Utility-first CSS framework
- **Three.js**: 3D visualization

### VR
- **Unity**: VR application development
- **XR Interaction Toolkit**: VR interactions
- **Universal Render Pipeline**: High-quality rendering

---

## 📊 Dataset Formats

The platform exports datasets in multiple formats:

- **USD/USDA**: NVIDIA Omniverse, Pixar formats
- **ROS Bags**: Robot Operating System
- **URDF**: Unified Robot Description Format
- **FBX/OBJ**: Standard 3D model formats
- **JSON**: Annotations and metadata

---

## 📈 Performance Metrics

- **Processing Time**: 4-7 hours for 50 minutes of video
- **VR Frame Rate**: 60+ FPS with Gaussian Splatting
- **Storage**: 10-25 GB per project
- **Scalability**: Horizontal scaling with multiple GPU workers

---

## 🎯 Use Cases

### Robotics & AI Research
- Train humanoid robots in realistic environments
- Generate synthetic training data
- Test navigation algorithms
- Simulate human-robot interactions

### Entertainment & Events
- Preserve wedding memories in VR
- Create virtual concert experiences
- Archive family gatherings
- Build interactive museum exhibits

### Real Estate & Architecture
- Virtual property tours
- Construction progress documentation
- Interior design visualization
- Historical building preservation

### Education & Training
- Immersive learning environments
- Medical procedure training
- Safety training simulations
- Historical event recreation

---

## 🔧 Configuration

Key configuration options in `.env`:

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/ewigen

# Storage
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# AI Services
OPENROUTER_API_KEY=your_key_here
ELEVENLABS_API_KEY=your_key_here

# Processing
MAX_WORKERS=4
GPU_MEMORY_FRACTION=0.8
```

---

## 🧪 Testing

```bash
# Backend tests
cd backend
pytest tests/ -v

# Frontend tests
cd frontend
npm test

# ML pipeline tests
cd ml
pytest tests/ -v
```

---

## 📦 Deployment

### Docker Deployment
```bash
./deploy.sh production
```

### Cloud Deployment
Supports deployment to:
- **AWS**: EC2, ECS, S3, RDS
- **Google Cloud**: Compute Engine, Cloud Storage, Cloud SQL
- **Azure**: Virtual Machines, Blob Storage, Azure Database

See `CLOUD_DEPLOYMENT_GUIDE.md` for detailed instructions.

---

## 📝 Documentation

- **[Architecture Visualization](https://crusherbolt.github.io/ewigen/)** - Interactive system architecture
- **[GitHub Pages Setup](GITHUB_PAGES_SETUP.md)** - How to deploy the architecture page
- **[API Documentation](http://localhost:8000/api/v1/docs)** - Swagger UI (when running)
- **[Business Name Analysis](BUSINESS_NAME_ANALYSIS.md)** - Why "Ewigen"?

---

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🆘 Support

For issues and questions:
- **GitHub Issues**: Report bugs and request features
- **Email**: support@ewigen.com
- **Documentation**: Full documentation in `/docs`

---

## 🎯 Roadmap

- [ ] Real-time collaborative VR experiences
- [ ] Mobile app for video capture
- [ ] Advanced physics simulation
- [ ] Multi-language support
- [ ] Marketplace for datasets
- [ ] Integration with major robotics platforms

---

## 💡 Why "Ewigen"?

**Ewigen** is German for "Eternal" - perfectly capturing our mission to preserve timeless moments. The name conveys:

- **Timelessness**: Moments that transcend time
- **Sophistication**: European elegance and precision
- **Technology**: Advanced engineering heritage
- **Emotion**: Deep connection to preservation

Alternative meanings:
- **E**verlasting **W**orld **I**mmersive **G**eneration **E**ngine **N**etwork
- Represents the timeless nature of digitally preserved memories

---

## 🏆 Built With

- ❤️ Passion for preserving memories
- 🧠 Cutting-edge AI and ML research
- 🎨 Beautiful design and UX
- ⚡ High-performance engineering
- 🌍 Global collaboration

---

**⏳ Ewigen - Preserve timeless moments forever**

*Where the past meets the future in immersive virtual reality*
