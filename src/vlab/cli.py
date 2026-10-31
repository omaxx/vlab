import click

from .node import Node
from .spec import Debian
from .utils import load_file


@click.group()
def main() -> None:
    """Virtual lab on libvirt."""


@main.command()
@click.option("-f", "--file", "path", required=True, type=click.Path(exists=True, dir_okay=False),
              help="VM spec: .yaml, .json or .jsonnet")
def deploy(path: str) -> None:
    """Create VM files on node and define VM in libvirt."""
    spec = Debian.from_dict(load_file(path))
    spec.deploy(Node())
    click.echo(f"{spec.name} defined")
