import argparse

from .node import Node
from .spec import Debian
from .utils import load_file


def deploy(args: argparse.Namespace) -> None:
    spec = Debian.from_dict(load_file(args.file))
    spec.deploy(Node())
    print(f"{spec.name} defined")


def main() -> None:
    parser = argparse.ArgumentParser(prog="vlab")
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("deploy", help="create VM files on node and define VM in libvirt")
    p.add_argument("-f", "--file", required=True, help="VM spec: .yaml, .json or .jsonnet")
    p.set_defaults(func=deploy)

    args = parser.parse_args()
    args.func(args)
