import click

from .host import Host
from .spec import Debian
from .utils import load_file


@click.group()
def main() -> None:
    """Virtual lab on libvirt."""


@main.command()
@click.option("-f", "--file", "path", required=True, type=click.Path(exists=True, dir_okay=False),
              help="VM spec: .yaml, .json or .jsonnet")
def deploy(path: str) -> None:
    """Create VM files on host and define VM in libvirt."""
    spec = Debian.from_dict(load_file(path))
    spec.deploy(Host())
    click.echo(f"{spec.name} defined")
