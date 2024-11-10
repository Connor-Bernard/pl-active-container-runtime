import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import docker
import jinja2

from checkpoint.constants import RUNTIME_DIR

from ..models.question import CheckpointQuestion


def check_docker_auth(username: str) -> bool:
    docker_config_path = Path.home() / ".docker" / "config.json"
    
    # Step 1: Get the `credsStore` value
    if not docker_config_path.exists():
        return False
    
    with open(docker_config_path) as f:
        config = json.load(f)
        creds_store = config.get("credsStore")
    
    if not creds_store:
        return False

    # Step 2: From the credential store, extract the Docker Hub username
    command = [
        f"docker-credential-{creds_store}", "list"
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    creds = json.loads(result.stdout)

    # Step 3: Find the entry containing "docker.io"
    return any(
        "docker.io" in key and username in value
        for key, value in creds.items()
    )

class DockerBuilder:
    def __init__(self, config: CheckpointQuestion):
        self.config = config
        self.client = docker.from_env()
    
    def build(self, tag: str) -> str:
        """Build Docker image for the checkpoint"""
        with tempfile.TemporaryDirectory() as tmpdir:
            build_dir = Path(tmpdir)
            self._prepare_context(build_dir)
            
            image, _ = self.client.images.build(
                path=str(build_dir),
                tag=tag,
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
        
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(pkg_dir / "templates"),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        template = env.get_template("config.py.j2")
        config_content = template.render(
            flags=self.config.flags,
            program=self.config.runtime.program,
            program_args=self.config.runtime.program_args,
            setup_commands=self.config.runtime.setup_commands
        )
        
        (build_dir / "config.py").write_text(config_content)
    
    def _generate_dockerfile(self, build_dir: Path) -> None:
        """Generate Dockerfile content"""
        image_config = self.config.image
        runtime_config = self.config.runtime
        runtime_dir = RUNTIME_DIR.as_posix()
        port = self.config.workspace_port
        workspace_home = self.config.workspace_home
        
        # Prepare package installation commands
        package_commands = [
            "apt-get install -y python3 python3-pip"
        ]
        if runtime_config.packages:
            packages = " ".join(runtime_config.packages)
            package_commands.append(f"apt-get install -y {packages}")
        
        template = f"""
        FROM {image_config.base}

        # Install system packages
        RUN apt-get update && apt-get upgrade -y && \
            {' && '.join(package_commands)}

        # Setup working directory
        WORKDIR {runtime_dir}
        RUN chmod -R 700 {runtime_dir}

        # Install Python packages
        COPY requirements.txt .
        RUN pip3 install --no-cache-dir -r requirements.txt

        # Copy application files
        COPY . .

        # Create user
        RUN useradd -m {runtime_config.user}

        # Set entrypoint
        ENTRYPOINT ["python3", "-u", "server.py", "--port", "{port}", "--user", "{runtime_config.user}", "--workdir", "{workspace_home}"]
        """
        
        (build_dir / "Dockerfile").write_text(template)

    def push(self, tag: str):
        """Push Docker image to registry"""
        self.client.images.push(tag) # type: ignore
