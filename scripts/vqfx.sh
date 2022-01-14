virt-install \
    --name r1-re \
    --ram 1024 \
    --vcpus=1 \
    --arch=x86_64 \
    --disk path=/home/maxim/vlab/r1/re/vqfx-20.2R1.10-re-qemu.qcow2 \
    --import \
    --network=network:mgmt,model=e1000 \
    --network=network:r1-int,model=e1000 \
    --network=network:r1-res,model=e1000 \
    --network=network:r1_r2_1,model=e1000 \
    --network=network:r1_r2_2,model=e1000 \
    &

virt-install \
    --name r1-pfe \
    --ram 2048 \
    --vcpus=1 \
    --arch=x86_64 \
    --disk path=/home/maxim/vlab/r1/pfe/vqfx-20.2R1-2019010209-pfe-qemu.qcow \
    --import \
    --network=network:mgmt,model=e1000 \
    --network=network:r1-int,model=e1000 \
    &
