"""
API v1 Router - Main router for all API endpoints
"""
from fastapi import APIRouter

# Import endpoint routers (will be created)
# from app.api.v1.endpoints import auth, projects, videos, scenes, characters, datasets

api_router = APIRouter()

# Include endpoint routers
# api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
# api_router.include_router(projects.router, prefix="/projects", tags=["Projects"])
# api_router.include_router(videos.router, prefix="/videos", tags=["Videos"])
# api_router.include_router(scenes.router, prefix="/scenes", tags=["Scenes"])
# api_router.include_router(characters.router, prefix="/characters", tags=["Characters"])
# api_router.include_router(datasets.router, prefix="/datasets", tags=["Datasets"])


@api_router.get("/")
async def api_root():
    """
    API v1 root endpoint
    """
    return {
        "message": "Virtual Environment Platform API v1",
        "endpoints": {
            "auth": "/auth",
            "projects": "/projects",
            "videos": "/videos",
            "scenes": "/scenes",
            "characters": "/characters",
            "datasets": "/datasets"
        }
    }

# Made with Bob
