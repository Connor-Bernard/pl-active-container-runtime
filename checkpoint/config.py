import json
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class DockerConfig(BaseModel):
    """Docker configuration"""
    base_image: str = "python:3.11-slim"
    workdir: str = "/app"
    user: str = "student"
    extra_packages: List[str] = Field(default_factory=list)
    extra_commands: List[str] = Field(default_factory=list)
    volumes: Dict[str, str] = Field(default_factory=dict)

    @field_validator('base_image')
    def validate_base_image(cls, v):
        if ':' not in v:
            raise ValueError("base_image must include a tag (e.g., python:3.11-slim)")
        return v

class ListenerConfig(BaseModel):
    """Flag listener configuration"""
    buffer: str
    type: str = "regex"
    match: str
    timeout: Optional[int] = None

    @field_validator('buffer')
    def validate_buffer(cls, v):
        valid_buffers = ['STDIN', 'STDOUT', 'STDERR']
        if v not in valid_buffers and not v.startswith('/'):
            raise ValueError(f"buffer must be one of {valid_buffers} or a file path")
        return v

    @field_validator('type')
    def validate_type(cls, v):
        valid_types = ['regex', 'exact', 'hash']
        if v not in valid_types:
            raise ValueError(f"type must be one of {valid_types}")
        return v

class FlagConfig(BaseModel):
    """Flag configuration"""
    title: str
    prompt: str
    description: str
    points: float = 1.0
    listener: ListenerConfig

class AssessmentConfig(BaseModel):
    """Main assessment configuration"""
    assignment: str
    container: str
    docker: DockerConfig = Field(default_factory=DockerConfig)
    flags: List[FlagConfig]

    @classmethod
    def from_file(cls, path: Path) -> "AssessmentConfig":
        content = json.loads(path.read_text())
        return cls.model_validate(content)

    @field_validator('flags')
    def validate_flags(cls, v):
        if not v:
            raise ValueError("At least one flag must be defined")
        return v
