from dataclasses import dataclass
import subprocess


@dataclass
class Host:
    """Host (hypervisor) running the VMs.

    Every operation is a separate process started via run(), so it can later be sent over ssh.
    """

    ip: str | None = None  # None = local host
    vm_path: str = "/var/lib/vlab"
    uri: str | None = None  # libvirt URI override, e.g. "test:///default"

    @property
    def libvirt_uri(self) -> str:
        if self.uri:
            return self.uri
        return "qemu:///system" if self.ip is None else f"qemu+ssh://{self.ip}/system"

    def __str__(self) -> str:
        return self.ip or "localhost"

    @property
    def images_dir(self) -> str:
        return f"{self.vm_path}/images"

    def vm_dir(self, name: str) -> str:
        return f"{self.vm_path}/vms/{name}"

    def _proc(self, cmd: tuple[str, ...], input: str | None, check: bool) -> subprocess.CompletedProcess[str]:
        return subprocess.run(cmd, input=input, capture_output=True, text=True, check=check)

    def run(self, *cmd: str, input: str | None = None) -> str:
        """Run command, return stdout; raise CalledProcessError on non-zero exit."""
        return self._proc(cmd, input, check=True).stdout

    def exists(self, path: str) -> bool:
        return self._proc(("test", "-e", path), None, check=False).returncode == 0

    def mkdir(self, path: str) -> None:
        self.run("mkdir", "-p", path)

    def cp(self, src: str, dst: str) -> None:
        self.run("cp", src, dst)

    def cow(self, base: str, dst: str) -> None:
        """Create qcow2 overlay dst backed by base (base must stay unchanged)."""
        self.run("qemu-img", "create", "-f", "qcow2", "-F", "qcow2", "-b", base, dst)

    def resize(self, path: str, size: str) -> None:
        """Grow disk image, size e.g. "20G"."""
        self.run("qemu-img", "resize", path, size)

    def read(self, path: str) -> str:
        return self.run("cat", path)

    def write(self, path: str, content: str) -> None:
        self.run("tee", path, input=content)

    def rm(self, path: str) -> None:
        """Remove file or directory tree."""
        self.run("rm", "-r", path)

    def seed_iso(self, iso: str, user_data: str, meta_data: str, network_config: str | None = None) -> None:
        """Build cloud-init NoCloud seed iso from existing files."""
        net = ("-N", network_config) if network_config else ()
        self.run("cloud-localds", *net, iso, user_data, meta_data)
