#!/usr/bin/env bash

confirm() {
    # call with a prompt string or use a default
    read -r -p "${1:-Are you sure? [y/N]} " response
    case "$response" in
        [yY][eE][sS]|[yY])
            true
            ;;
        *)
            false
            ;;
    esac
}

net-enable-protocols() {
  sudo sh -c "echo 0x4000 >/sys/class/net/$1/bridge/group_fwd_mask"
}

case $1 in
  status)
    virsh -c qemu:///system net-list --all
    virsh -c qemu:///system list --all
    ;;

  start)
    for net in $(virsh -c qemu:///system net-list --name --inactive)
    do
      virsh -c qemu:///system net-start $net
      net-enable-protocols $net
    done
    for vm in $(virsh -c qemu:///system list --name --inactive); do virsh -c qemu:///system start $vm; done
    ;;

  stop)
    for vm in $(virsh -c qemu:///system list --name); do virsh -c qemu:///system destroy $vm; done
    for net in $(virsh -c qemu:///system net-list --name); do virsh -c qemu:///system net-destroy $net; done
    ;;

  destroy)
    confirm "Are you sure to destroy all VMs? [y/N]"|| exit

    for vm in $(virsh -c qemu:///system list --all --name); do virsh -c qemu:///system undefine $vm; done
    for net in $(virsh -c qemu:///system net-list --all --name); do virsh -c qemu:///system net-undefine $net; done
    ;;

  *)
    echo "unknown command" $1
    echo
    echo "commands:"
    echo "  status"
    echo "  start"
    echo "  stop"
    echo "  destroy"
    ;;
esac
