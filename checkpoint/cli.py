import json
from pathlib import Path

import click

from .builder import DockerBuilder
from .config import AssessmentConfig


@click.group()
def cli():
    """Checkpoint - A tool for terminal-based capture-the-flag assessments"""
    pass

@cli.command()
@click.argument('config_path', type=click.Path(exists=True, path_type=Path))
@click.option('--tag', '-t', help='Docker image tag (defaults to assignment name)')
def build(config_path: Path, tag: str):
    """Build a Docker image for your terminal-based assessment"""
    config = AssessmentConfig.from_file(config_path)
    tag = tag or f"checkpoint-{config.assignment.lower().replace(' ', '-')}"
    
    click.echo(f"Building assessment: {config.assignment}")
    builder = DockerBuilder(config)
    image_id = builder.build(tag)
    click.echo(f"✨ Successfully built image: {tag} ({image_id})")

@cli.command()
def init():
    """Initialize a new assessment configuration"""
    click.echo("Creating example config.json...")
    example_config = {
        "assignment": "GDB Tutorial",
        "container": "gdb-tutorial",
        "flags": [
            {
                "title": "Start Program",
                "prompt": "Start your program",
                "description": "Start your program at the first line in main",
                "listener": {
                    "buffer": "STDOUT",
                    "type": "regex",
                    "match": "^main\\s*\\(\\)\\s*at\\s*test"
                }
            }
        ]
    }
    
    output_path = Path("config.json")
    if output_path.exists():
        if not click.confirm("config.json already exists. Overwrite?"):
            return
            
    output_path.write_text(json.dumps(example_config, indent=2))
    click.echo("✨ Created example config.json")
    click.echo("\nNext steps:")
    click.echo("1. Edit config.json to customize your assessment")
    click.echo("2. Run 'checkpoint build config.json' to build the Docker image")

@cli.command()
def validate():
    """Validate your assessment configuration"""
    config_path = Path("config.json")
    if not config_path.exists():
        click.echo("❌ No config.json found in current directory")
        return
        
    try:
        config = AssessmentConfig.from_file(config_path)
        click.echo("✅ Configuration is valid!")
        click.echo(f"\nAssessment: {config.assignment}")
        click.echo(f"Flags: {len(config.flags)}")
    except Exception as e:
        click.echo(f"❌ Configuration error: {str(e)}")

if __name__ == '__main__':
    cli()
