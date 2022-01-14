virt-install --name vQFX1-RE \
             --ram 1024 \
             --cpu Haswell,+vmx \
             --vcpus=1 \
             --arch=x86_64 \
             --disk path=/var/lib/libvirt/images/vqfx10k-1-re.qcow2,size=16,device=disk,bus=ide,format=qcow2 \
             --import \
             --network=network:default,model=e1000 --network=network:internal1,model=e1000 --network=network:reserved,model=e1000 \
             --network=network:vmnet1,model=e1000 --network=network:vmnet3,model=e1000 --network=network:vmnet4,model=e1000

virt-install --name vQFX1-PFE \
             --ram 2048 \
             --cpu Haswell,+vmx \
             --vcpus=1 \
             --arch=x86_64 \
             --disk path=/var/lib/libvirt/images/vqfx10k-1-pfe.qcow2,device=disk,bus=ide,format=qcow2 \
             --import \
             --network=network:default,model=e1000 --network=network:internal1,model=e1000
