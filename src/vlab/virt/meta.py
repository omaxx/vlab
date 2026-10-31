import xml.etree.ElementTree as ET

# vlab metadata inside libvirt XML: <metadata><vlab:domain|vlab:network ...>
NS = "https://omaxx.net/vlab"
ET.register_namespace("vlab", NS)


def tag(name: str) -> str:
    return f"{{{NS}}}{name}"
