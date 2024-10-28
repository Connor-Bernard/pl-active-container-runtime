import shutil
import tempfile
from pathlib import Path
from typing import Optional

import docker
import jinja2

from .config import AssessmentConfig


class DockerBuilder:
    """Builds Docker images for terminal-based assessments"""
    
    def __init__(self, config: AssessmentConfig):
        self.config = config
        self.client = docker.from_env()
        
    def build(self, tag: Optional[str] = None) -> str:
        """Build Docker image and return image ID"""
        with tempfile.TemporaryDirectory() as tmpdir:
            build_dir = Path(tmpdir)
            self._prepare_context(build_dir)
            
            image_tag = tag or f"checkpoint-{self.config.assignment.lower().replace(' ', '-')}"
            
            image, _ = self.client.images.build(
                path=str(build_dir),
                tag=image_tag,
                dockerfile=str(build_dir / "Dockerfile"),
            )
            if not image.id:
                raise ValueError("Docker build failed: no image ID returned")
            return image.id
            
    def _prepare_context(self, build_dir: Path) -> None:
        """Prepare Docker build context"""
        self._copy_templates(build_dir)
        self._generate_config(build_dir)
        self._generate_dockerfile(build_dir)
    
    def _copy_templates(self, build_dir: Path) -> None:
        """Copy template files to build directory"""
        pkg_dir = Path(__file__).parent
        templates_dir = pkg_dir / "templates"
        
        for item in ["index.html", "server.py", "requirements.txt"]:
            shutil.copy2(templates_dir / item, build_dir / item)
    
    def _generate_config(self, build_dir: Path) -> None:
        """Generate config.py from assessment config"""
        pkg_dir = Path(__file__).parent
        template = (pkg_dir / "templates" / "config.py.j2").read_text()
        
        config_content = jinja2.Template(template).render(
            flags=self.config.flags
        )
        (build_dir / "config.py").write_text(config_content)
    
    def _generate_dockerfile(self, build_dir: Path) -> None:
        """Generate Dockerfile for the assessment"""
        docker_config = self.config.docker
        
        template = f"""
        FROM {docker_config.base_image}

        # Install system packages
        RUN apt-get update && apt-get upgrade -y
        RUN apt-get install -y gdb {"".join(docker_config.extra_packages)}

        # Install Python packages
        COPY requirements.txt .
        RUN pip install --no-cache-dir -r requirements.txt

        # Setup working directory
        WORKDIR {docker_config.workdir}
        COPY . .

        # Create user
        RUN useradd -m {docker_config.user}
        
        # Extra commands
        {chr(10).join(docker_config.extra_commands)}

        # Set entrypoint
        ENTRYPOINT ["python", "-u", "server.py"]
        """
        
        (build_dir / "Dockerfile").write_text(template)