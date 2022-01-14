
virt-install --name H11 \
             --ram 4096 \
             --vcpus=2 \
             --arch=x86_64 \
             --disk path=/var/lib/libvirt/images/H11.qcow2,size=16,device=disk,bus=ide,format=qcow2 \
             --import \
             --network=network:default,model=virtio \
             --network=network:default,model=virtio \
             --network=network:default,model=virtio &

virt-install --name SRX \
            --ram 4096 \
            --vcpus=2 \
            --arch=x86_64 \
            --disk path=/var/lib/libvirt/images/SRX/media-vsrx-vmdisk-15.1X49-D150.2.qcow \
            --import \
            --network=network:default,model=virtio \
            --network=network:default,model=virtio \
            --network=network:default,model=virtio &
