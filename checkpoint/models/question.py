from enum import Enum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from .docker import DockerConfig


class CheckpointFile(BaseModel):
    source: str
    target: str
    graded: bool = True

class ListenerType(str, Enum):
    REGEX = "regex"
    EXACT = "exact"

class ListenerTarget(str, Enum):
    COMMAND = "command"
    OUTPUT = "output"

class CheckpointListener(BaseModel):
    type: ListenerType
    target: ListenerTarget
    match: str

class CheckpointFlag(BaseModel):
    title: str
    prompt: str
    description: str
    listener: CheckpointListener
    files: list[CheckpointFile] = Field(default_factory=list)

class CheckpointQuestion(BaseModel):
    uuid: str
    title: str
    topic: str
    tags: list[str] = Field(default_factory=list)
    docker: DockerConfig
    flags: list[CheckpointFlag]
    workspace_port: int = 8080
    workspace_home: str = "/home/student"

    @classmethod
    def from_yaml(cls, path: Path) -> "CheckpointQuestion":
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)

    def get_all_files(self) -> dict[str, str]:
        """Get the mapping of all files"""
        return {file.source : file.target for flag in self.flags for file in flag.files}
    
    def generate_info_json(self, image_name: str) -> dict[str, Any]:
        return {
            "uuid": self.uuid,
            "title": self.title,
            "topic": self.topic,
            "tags": self.tags,
            "type": "v3",
            "singleVariant": True,
            "gradingMethod": "Internal",
            "showCorrectAnswer": False,
            "partialCredit": False,
            "workspaceOptions": {
                "image": image_name,
                "port": self.workspace_port,
                "home": self.workspace_home,
                "gradedFiles": self._collect_graded_files()
            }
        }
    
    def _collect_graded_files(self) -> list[str]:
        graded_files: set[str] = set(["/checkpoint_grade/*"])
        for flag in self.flags:
            for file in flag.files:
                if file.graded:
                    graded_files.add(file.target)
        return sorted(list(graded_files))

