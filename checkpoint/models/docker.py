from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class DockerConfig(BaseModel):
    """Docker configuration"""
    base_image: str = "python:3.11-slim"
    workdir: str = "/app"
    user: str = "student"
    extra_packages: List[str] = Field(default_factory=list)
    extra_commands: List[str] = Field(default_factory=list)
    volumes: Dict[str, str] = Field(default_factory=dict)

    registry: str
    image: str
    image_name: Optional[str] = None
    
    def get_image_name(self) -> str:
        if self.image_name:
            return self.image_name
        return f"{self.registry}/checkpoint-{self.image}"

