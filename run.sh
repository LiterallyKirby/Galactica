#!/bin/bash
set -e

# Clean & recreate build dir
rm -rf build
mkdir -p build

# Assemble the kernel boot file
nasm -f elf32 src/kernel.asm -o build/boot.o

# Compile all .c files in src/
for file in src/*.c; do
    obj="build/$(basename "${file%.c}.o")"
    echo "Compiling $file -> $obj"
    i686-elf-gcc -m32 -ffreestanding -fno-stack-protector -c "$file" -Iinclude -o "$obj"
done

# Link all object files together
OBJ_FILES="build/*.o"
echo "Linking: $OBJ_FILES"
i686-elf-ld -m elf_i386 -T src/link.ld -o build/kernel $OBJ_FILES

# Run in QEMU
echo "Launching QEMU..."

qemu-system-i386 -kernel build/kernel -hda fat16.img

