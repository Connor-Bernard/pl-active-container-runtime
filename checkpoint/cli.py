import uuid
from pathlib import Path
from typing import Any

import click
import docker
import yaml

from .builders.docker import DockerBuilder, check_docker_auth
from .builders.question import QuestionBuilder
from .constants import (
    DEFAULT_CONFIG_PATH,
    QUESTION_HTML_PATH,
    WORKSPACE_TEMPLATES_PATH,
)
from .models.question import CheckpointQuestion


@click.group()
def cli():
    """Checkpoint CLI tool for PrairieLearn"""
    pass

@cli.command()
def init():
    """Initialize a new checkpoint question"""
    if Path(DEFAULT_CONFIG_PATH).exists():
        if not click.confirm(f"{DEFAULT_CONFIG_PATH} already exists. Overwrite?"):
            return
    
    config: dict[str, Any] = {
        "uuid": str(uuid.uuid4()),
        "title": "My Checkpoint",
        "topic": "Topic",
        "tags": ["checkpoint"],
        "docker": {
            "registry": "username",
            "image": "my-checkpoint"
        },
        "flags": [
            {
                "title": "Example Flag",
                "prompt": "Your first checkpoint",
                "description": "Description of what to do",
                "listener": {
                    "target": "output",
                    "type": "regex",
                    "match": "example"
                },
                "files": []
            }
        ]
    }
    
    DEFAULT_CONFIG_PATH.write_text(yaml.dump(config, sort_keys=False))
    WORKSPACE_TEMPLATES_PATH.mkdir(exist_ok=True)

    question_html = """<pl-question-panel>
  <p>This is a workspace question with an interactive terminal for GDB tutorial.</p>
  <pl-workspace></pl-workspace>
</pl-question-panel>

<pl-submission-panel>
  <pl-file-preview>
  </pl-file-preview>
</pl-submission-panel>"""

    QUESTION_HTML_PATH.write_text(question_html)

    click.echo(f"✨ Created {DEFAULT_CONFIG_PATH} template")
    click.echo("Next steps:")
    click.echo(f"1. Edit {DEFAULT_CONFIG_PATH}")
    click.echo("2. Add your source files")
    click.echo("3. Run: checkpoint deploy")

@cli.command()
def login():
    """Configure Docker registry credentials"""
    username = click.prompt("Docker Hub username")
    password = click.prompt("Docker Hub password", hide_input=True)
    
    client = docker.from_env()
    client.login(username=username, password=password)
    click.echo("✨ Successfully logged in to Docker Hub")

@cli.command()
def build():
    """Build Docker image only"""
    if not DEFAULT_CONFIG_PATH.exists():
        click.echo(f"❌ {DEFAULT_CONFIG_PATH} not found")
        click.echo("Run 'checkpoint init' to create a new checkpoint")
        return
    
    config = CheckpointQuestion.from_yaml(DEFAULT_CONFIG_PATH)
    image_name = config.docker.get_image_name()
    
    click.echo(f"🔨 Building image: {image_name}")
    builder = DockerBuilder(config)
    image_id = builder.build(image_name)
    click.echo(f"✨ Built image: {image_id}")

@cli.command()
def push():
    """Push existing Docker image"""
    if not DEFAULT_CONFIG_PATH.exists():
        click.echo(f"❌ {DEFAULT_CONFIG_PATH} not found")
        return
    
    config = CheckpointQuestion.from_yaml(DEFAULT_CONFIG_PATH)
    image_name = config.docker.get_image_name()
    username = config.docker.registry
    if not check_docker_auth(username):
        click.echo(f"❌ Docker Hub credentials not found for {username!r}")
        return
    
    click.echo(f"🚀 Pushing image {image_name} to Docker Hub")
    builder = DockerBuilder(config)
    builder.push(image_name)
    click.echo("✨ Image pushed")

@cli.command()
def generate():
    """Generate question info.json only"""
    if not DEFAULT_CONFIG_PATH.exists():
        click.echo(f"❌ {DEFAULT_CONFIG_PATH} not found")
        return
    
    config = CheckpointQuestion.from_yaml(DEFAULT_CONFIG_PATH)
    image_name = config.docker.get_image_name()
    
    click.echo("📝 Generating question files...")
    question_builder = QuestionBuilder(config)
    question_builder.build(image_name)
    click.echo("✨ Generated info.json and question.html")

@cli.command()
def deploy():
    """Full deployment: build, push and generate"""
    if not DEFAULT_CONFIG_PATH.exists():
        click.echo(f"❌ {DEFAULT_CONFIG_PATH} not found")
        click.echo("Run 'checkpoint init' to create a new checkpoint")
        return
    
    config = CheckpointQuestion.from_yaml(DEFAULT_CONFIG_PATH)
    image_name = config.docker.get_image_name()
    username = config.docker.registry
    if not check_docker_auth(username):
        click.echo(f"❌ Docker Hub credentials not found for {username!r}")
        return
    
    # 1. Build Docker image
    click.echo(f"🔨 Building image: {image_name}")
    docker_builder = DockerBuilder(config)
    docker_builder.build(image_name)
    
    # 2. Push to registry
    click.echo(f"🚀 Pushing image {image_name} to Docker Hub")
    docker_builder.push(image_name)
    
    # 3. Generate question files
    click.echo("📝 Generating question files...")
    question_builder = QuestionBuilder(config)
    question_builder.build(image_name)
    
    click.echo("✨ Deployment complete!")
