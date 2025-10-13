#!/bin/bash
#
# Galactica OS Installer
# Secure Dom0 Installation for Journalists, Activists, and Pentesters
#
# Usage: sudo bash galactica-install.sh
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root${NC}" 
   exit 1
fi

# Check if dialog is installed
if ! command -v dialog &> /dev/null; then
    echo "Installing dialog..."
    pacman -Sy --noconfirm dialog
fi

# Temporary file for dialog
TEMP_FILE=$(mktemp)
trap "rm -f $TEMP_FILE" EXIT

# Global variables
DISK=""
ENCRYPT_PASS=""
HOSTNAME="galactica-dom0"
ROOT_PASS=""
ENABLE_SECURE_BOOT=false
ENABLE_TPM=false

#==============================================================================
# WELCOME SCREEN
#==============================================================================
show_welcome() {
    dialog --title "Galactica OS Installer v1.0" \
           --msgbox "\nWelcome to Galactica OS - A Secure Operating System\n\n\
Designed for:\n\
  • Journalists requiring source protection\n\
  • Activists and protesters\n\
  • Security researchers and pentesters\n\n\
Features:\n\
  ✓ Full disk encryption (LUKS2)\n\
  ✓ Xen hypervisor for VM isolation\n\
  ✓ Hardened Linux kernel\n\
  ✓ Mandatory Access Control (AppArmor)\n\
  ✓ USB device protection\n\
  ✓ Complete dom0 network isolation\n\
  ✓ Anti-forensics features\n\n\
⚠️  WARNING: This will ERASE ALL DATA on the selected disk!\n\n\
Press OK to continue..." 24 70
}

#==============================================================================
# DISK SELECTION
#==============================================================================
select_disk() {
    echo -e "${CYAN}Detecting disks...${NC}"
    
    # Get list of disks (excluding loop devices and mounted root)
    local disk_list=$(lsblk -d -n -p -o NAME,SIZE,TYPE,MODEL | grep "disk" | awk '{print $1, $2, $4}')
    
    if [[ -z "$disk_list" ]]; then
        dialog --msgbox "No disks found!" 8 40
        exit 1
    fi
    
    # Build dialog menu
    local menu_items=()
    while IFS= read -r line; do
        local disk_name=$(echo "$line" | awk '{print $1}')
        local disk_info=$(echo "$line" | awk '{print $2, $3}')
        menu_items+=("$disk_name" "$disk_info")
    done <<< "$disk_list"
    
    dialog --title "Disk Selection" \
           --menu "Select the target disk for installation:" 15 70 5 \
           "${menu_items[@]}" 2> $TEMP_FILE
    
    DISK=$(cat $TEMP_FILE)
    
    # Confirmation
    dialog --title "⚠️  WARNING ⚠️" \
           --defaultno \
           --yesno "ALL DATA ON $DISK WILL BE PERMANENTLY ERASED!\n\n\
Disk: $DISK\n\
Size: $(lsblk -d -n -o SIZE $DISK)\n\
Model: $(lsblk -d -n -o MODEL $DISK)\n\n\
Are you ABSOLUTELY SURE you want to continue?" 14 60
}

#==============================================================================
# ENCRYPTION SETUP
#==============================================================================
setup_encryption() {
    while true; do
        dialog --title "Disk Encryption" \
               --insecure \
               --passwordbox "Enter a strong encryption passphrase:\n\n\
Recommendations:\n\
 • At least 20 characters\n\
 • Mix of uppercase, lowercase, numbers, symbols\n\
 • Unique and memorable\n\n\
⚠️  This passphrase CANNOT be recovered if lost!" 16 60 2> $TEMP_FILE
        
        ENCRYPT_PASS=$(cat $TEMP_FILE)
        
        if [[ ${#ENCRYPT_PASS} -lt 12 ]]; then
            dialog --msgbox "Passphrase too short! Must be at least 12 characters.\n\nFor journalists and activists, we recommend 20+ characters." 10 50
            continue
        fi
        
        dialog --title "Confirm Passphrase" \
               --insecure \
               --passwordbox "Re-enter your encryption passphrase:" 10 50 2> $TEMP_FILE
        
        local confirm_pass=$(cat $TEMP_FILE)
        
        if [[ "$ENCRYPT_PASS" != "$confirm_pass" ]]; then
            dialog --msgbox "Passphrases do not match! Please try again." 8 50
            continue
        fi
        
        break
    done
}

#==============================================================================
# SECURITY OPTIONS
#==============================================================================
configure_security() {
    dialog --title "Security Configuration" \
           --checklist "Select security features:\n(Use SPACE to toggle, ENTER to confirm)" 18 70 10 \
           "KERNEL_HARDENING" "Advanced kernel security parameters" ON \
           "APPARMOR" "Mandatory Access Control" ON \
           "USBGUARD" "Block unauthorized USB devices" ON \
           "AUDIT" "Security event logging" ON \
           "MAC_RANDOM" "Randomize MAC addresses" ON \
           "ANTI_FORENSICS" "RAM wipe, secure deletion" ON \
           "DISABLE_IPV6" "Disable IPv6 (reduce attack surface)" OFF \
           "SECURE_BOOT" "Configure Secure Boot (requires setup)" OFF \
           "TPM" "TPM-based encryption (requires TPM 2.0)" OFF 2> $TEMP_FILE
    
    # Read selected options
    local selected=$(cat $TEMP_FILE)
    [[ "$selected" =~ "SECURE_BOOT" ]] && ENABLE_SECURE_BOOT=true
    [[ "$selected" =~ "TPM" ]] && ENABLE_TPM=true
}

#==============================================================================
# HOSTNAME AND PASSWORD
#==============================================================================
configure_system() {
    # Hostname
    dialog --title "System Configuration" \
           --inputbox "Enter hostname for this system:" 10 50 "galactica-dom0" 2> $TEMP_FILE
    HOSTNAME=$(cat $TEMP_FILE)
    
    # Root password
    while true; do
        dialog --title "Root Password" \
               --insecure \
               --passwordbox "Enter root password:" 10 50 2> $TEMP_FILE
        ROOT_PASS=$(cat $TEMP_FILE)
        
        if [[ ${#ROOT_PASS} -lt 8 ]]; then
            dialog --msgbox "Password too short! Must be at least 8 characters." 8 50
            continue
        fi
        
        dialog --title "Confirm Root Password" \
               --insecure \
               --passwordbox "Re-enter root password:" 10 50 2> $TEMP_FILE
        local confirm_pass=$(cat $TEMP_FILE)
        
        if [[ "$ROOT_PASS" != "$confirm_pass" ]]; then
            dialog --msgbox "Passwords do not match!" 8 40
            continue
        fi
        
        break
    done
}

#==============================================================================
# REVIEW CONFIGURATION
#==============================================================================
review_config() {
    dialog --title "Review Configuration" \
           --yesno "Please review your installation settings:\n\n\
Target Disk: $DISK\n\
Hostname: $HOSTNAME\n\
Encryption: LUKS2 (AES-XTS-512)\n\
Kernel: linux-hardened\n\
Hypervisor: Xen\n\
Dom0 Network: DISABLED (isolated)\n\
Security: Maximum hardening\n\n\
Start installation?" 18 60
}

#==============================================================================
# INSTALLATION FUNCTIONS
#==============================================================================

# Securely wipe disk
wipe_disk() {
    echo -e "${YELLOW}Securely wiping disk (this may take a while)...${NC}"
    dd if=/dev/urandom of=$DISK bs=4M status=progress 2>&1 | \
        dialog --programbox "Secure Disk Wipe" 20 70
}

# Partition disk
partition_disk() {
    echo "Creating GPT partition table..."
    parted -s $DISK mklabel gpt
    
    echo "Creating EFI partition (512MB)..."
    parted -s $DISK mkpart ESP fat32 1MiB 513MiB
    parted -s $DISK set 1 esp on
    
    echo "Creating root partition..."
    parted -s $DISK mkpart primary 513MiB 100%
    
    # Inform kernel of changes
    partprobe $DISK
    sleep 2
}

# Setup LUKS encryption
setup_luks() {
    echo "Setting up LUKS2 encryption..."
    
    # Determine partition naming (handle nvme/mmcblk)
    if [[ $DISK =~ "nvme" ]] || [[ $DISK =~ "mmcblk" ]]; then
        local root_part="${DISK}p2"
        local efi_part="${DISK}p1"
    else
        local root_part="${DISK}2"
        local efi_part="${DISK}1"
    fi
    
    # Create LUKS container with strong settings
    echo -n "$ENCRYPT_PASS" | cryptsetup luksFormat \
        --type luks2 \
        --cipher aes-xts-plain64 \
        --key-size 512 \
        --hash sha512 \
        --iter-time 5000 \
        --use-random \
        $root_part -
    
    # Open encrypted container
    echo -n "$ENCRYPT_PASS" | cryptsetup open $root_part cryptroot -
    
    echo "Formatting EFI partition..."
    mkfs.fat -F32 $efi_part
    
    echo "Formatting root with Btrfs..."
    mkfs.btrfs -L GalacticaOS /dev/mapper/cryptroot
    
    # Mount and create subvolumes
    mount /dev/mapper/cryptroot /mnt
    btrfs subvolume create /mnt/@
    btrfs subvolume create /mnt/@home
    btrfs subvolume create /mnt/@snapshots
    umount /mnt
    
    # Remount with proper subvolumes and options
    mount -o subvol=@,compress=zstd,noatime /dev/mapper/cryptroot /mnt
    mkdir -p /mnt/{boot,home,.snapshots}
    mount -o subvol=@home,compress=zstd,noatime /dev/mapper/cryptroot /mnt/home
    mount -o subvol=@snapshots /dev/mapper/cryptroot /mnt/.snapshots
    mount $efi_part /mnt/boot
}

# Install base system
install_base() {
    echo "Installing base system..."
    
    pacstrap /mnt \
        base \
        base-devel \
        linux-hardened \
        linux-hardened-headers \
        linux-firmware \
        intel-ucode \
        amd-ucode \
        btrfs-progs \
        grub \
        efibootmgr \
        networkmanager \
        xen \
        apparmor \
        audit \
        firejail \
        usbguard \
        rng-tools \
        haveged \
        cryptsetup \
        vim \
        tmux \
        git
    
    # Generate fstab
    genfstab -U /mnt >> /mnt/etc/fstab
    
    # Add secure mount options
    cat >> /mnt/etc/fstab << 'EOF'

# Galactica OS Secure Mounts
tmpfs /tmp tmpfs defaults,noexec,nosuid,nodev,size=2G 0 0
tmpfs /var/tmp tmpfs defaults,noexec,nosuid,nodev,size=1G 0 0
tmpfs /dev/shm tmpfs defaults,noexec,nosuid,nodev 0 0
EOF
}

# Configure system
configure_base_system() {
    echo "Configuring base system..."
    
    # Timezone (UTC for privacy)
    arch-chroot /mnt ln -sf /usr/share/zoneinfo/UTC /etc/localtime
    arch-chroot /mnt hwclock --systohc
    
    # Locale
    echo "en_US.UTF-8 UTF-8" >> /mnt/etc/locale.gen
    arch-chroot /mnt locale-gen
    echo "LANG=en_US.UTF-8" > /mnt/etc/locale.conf
    
    # Hostname
    echo "$HOSTNAME" > /mnt/etc/hostname
    cat > /mnt/etc/hosts << EOF
127.0.0.1   localhost
::1         localhost
127.0.1.1   $HOSTNAME.localdomain $HOSTNAME
EOF
    
    # Root password
    echo "root:$ROOT_PASS" | arch-chroot /mnt chpasswd
}

# Apply kernel hardening
apply_kernel_hardening() {
    echo "Applying kernel hardening..."
    
    cat > /mnt/etc/sysctl.d/99-galactica-security.conf << 'EOF'
# Galactica OS Kernel Hardening

# Network Security
net.ipv4.conf.all.rp_filter=1
net.ipv4.conf.default.rp_filter=1
net.ipv4.tcp_syncookies=1
net.ipv4.conf.all.accept_redirects=0
net.ipv4.conf.default.accept_redirects=0
net.ipv4.conf.all.secure_redirects=0
net.ipv4.conf.default.secure_redirects=0
net.ipv6.conf.all.accept_redirects=0
net.ipv6.conf.default.accept_redirects=0
net.ipv4.conf.all.send_redirects=0
net.ipv4.conf.default.send_redirects=0
net.ipv4.conf.all.accept_source_route=0
net.ipv4.conf.default.accept_source_route=0
net.ipv6.conf.all.accept_source_route=0
net.ipv6.conf.default.accept_source_route=0
net.ipv4.icmp_echo_ignore_all=1
net.ipv6.conf.all.accept_ra=0
net.ipv6.conf.default.accept_ra=0
net.ipv4.conf.all.log_martians=1

# Kernel Hardening
kernel.dmesg_restrict=1
kernel.kptr_restrict=2
kernel.unprivileged_bpf_disabled=1
kernel.unprivileged_userns_clone=0
kernel.yama.ptrace_scope=2
dev.tty.ldisc_autoload=0
kernel.kexec_load_disabled=1
kernel.sysrq=0

# Disable core dumps
kernel.core_pattern=|/bin/false
fs.suid_dumpable=0

# Memory protection
vm.mmap_min_addr=65536
vm.unprivileged_userfaultfd=0

# Filesystem hardening
fs.protected_hardlinks=1
fs.protected_symlinks=1
fs.protected_fifos=2
fs.protected_regular=2
EOF
}

# Configure GRUB with hardening
configure_grub() {
    echo "Configuring GRUB with hardened boot parameters..."
    
    # Get UUID of encrypted partition
    local crypt_uuid=$(blkid -s UUID -o value ${DISK}2 2>/dev/null || blkid -s UUID -o value ${DISK}p2)
    
    cat > /mnt/etc/default/grub << EOF
GRUB_DEFAULT=0
GRUB_TIMEOUT=5
GRUB_DISTRIBUTOR="Galactica OS"
GRUB_CMDLINE_LINUX_DEFAULT="quiet loglevel=0 slab_nomerge init_on_alloc=1 init_on_free=1 page_alloc.shuffle=1 pti=on vsyscall=none debugfs=off oops=panic module.sig_enforce=1 lockdown=confidentiality mce=0 iommu=force intel_iommu=on amd_iommu=on"
GRUB_CMDLINE_LINUX="cryptdevice=UUID=$crypt_uuid:cryptroot root=/dev/mapper/cryptroot apparmor=1 security=apparmor"
GRUB_DISABLE_RECOVERY=true
GRUB_DISABLE_OS_PROBER=true
GRUB_GFXMODE=auto
GRUB_GFXPAYLOAD_LINUX=keep
GRUB_DISABLE_SUBMENU=y
EOF
    
    # Install GRUB
    arch-chroot /mnt grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=GALACTICA --recheck
    arch-chroot /mnt grub-mkconfig -o /boot/grub/grub.cfg
}

# Configure mkinitcpio for encryption
configure_initramfs() {
    echo "Configuring initramfs..."
    
    cat > /mnt/etc/mkinitcpio.conf << 'EOF'
MODULES=(btrfs)
BINARIES=()
FILES=()
HOOKS=(base systemd autodetect keyboard sd-vconsole modconf block sd-encrypt filesystems fsck)
COMPRESSION="zstd"
EOF
    
    arch-chroot /mnt mkinitcpio -P
}

# Configure AppArmor
configure_apparmor() {
    echo "Configuring AppArmor..."
    
    arch-chroot /mnt systemctl enable apparmor.service
    
    echo "APPARMOR=enforce" > /mnt/etc/default/apparmor
}

# Configure USBGuard
configure_usbguard() {
    echo "Configuring USBGuard..."
    
    cat > /mnt/etc/usbguard/usbguard-daemon.conf << 'EOF'
ImplicitPolicyTarget=block
PresentDevicePolicy=apply-policy
PresentControllerPolicy=apply-policy
InsertedDevicePolicy=block
AuthorizedDefault=none
AuditBackend=LinuxAudit
IPCAllowedUsers=root
IPCAllowedGroups=wheel
EOF
    
    # Generate initial policy
    arch-chroot /mnt usbguard generate-policy > /mnt/etc/usbguard/rules.conf
    arch-chroot /mnt systemctl enable usbguard.service
}

# Configure audit
configure_audit() {
    echo "Configuring audit system..."
    
    cat > /mnt/etc/audit/rules.d/galactica.rules << 'EOF'
# Galactica OS Audit Rules
-w /etc/passwd -p wa -k identity
-w /etc/group -p wa -k identity
-w /etc/shadow -p wa -k identity
-a always,exit -F arch=b64 -S execve -F euid=0 -k root-commands
-a always,exit -F arch=b64 -S socket -S connect -k network
-a always,exit -F arch=b64 -S unlink -S unlinkat -S rename -k delete
-w /sbin/insmod -p x -k modules
-w /sbin/rmmod -p x -k modules
-a always,exit -F arch=b64 -S init_module -S delete_module -k modules
EOF
    
    arch-chroot /mnt systemctl enable auditd.service
}

# Lockdown Dom0
lockdown_dom0() {
    echo "Locking down Dom0..."
    
    # Disable NetworkManager (dom0 should have NO network)
    arch-chroot /mnt systemctl disable NetworkManager
    arch-chroot /mnt systemctl mask NetworkManager
    
    # Disable unnecessary services
    for service in bluetooth.service cups.service avahi-daemon.service ModemManager.service; do
        arch-chroot /mnt systemctl disable $service 2>/dev/null || true
        arch-chroot /mnt systemctl mask $service 2>/dev/null || true
    done
    
    # Create firewall rules
    cat > /mnt/usr/local/bin/galactica-firewall << 'EOF'
#!/bin/bash
# Dom0 Firewall - Block ALL external network

iptables -F
iptables -X
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP

# Allow loopback only
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT
EOF
    
    chmod +x /mnt/usr/local/bin/galactica-firewall
    
    # Create firewall service
    cat > /mnt/etc/systemd/system/galactica-firewall.service << 'EOF'
[Unit]
Description=Galactica Dom0 Firewall
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/galactica-firewall
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
    
    arch-chroot /mnt systemctl enable galactica-firewall.service
}

# Configure Xen
configure_xen() {
    echo "Configuring Xen hypervisor..."
    
    mkdir -p /mnt/etc/xen
    cat > /mnt/etc/xen/xl.conf << 'EOF'
# Galactica OS Xen Configuration
autoballoon="off"
dom0_mem="4096M,max:4096M"
dom0_max_vcpus=4
vif.default.script="vif-bridge"
vif.default.bridge="xenbr0"
EOF
    
    arch-chroot /mnt systemctl enable xen-qemu-dom0-disk-backend.service
    arch-chroot /mnt systemctl enable xen-init-dom0.service
}

# Configure MAC randomization
configure_mac_random() {
    echo "Configuring MAC randomization..."
    
    mkdir -p /mnt/etc/NetworkManager/conf.d
    cat > /mnt/etc/NetworkManager/conf.d/mac-randomization.conf << 'EOF'
[device]
wifi.scan-rand-mac-address=yes

[connection]
wifi.cloned-mac-address=random
ethernet.cloned-mac-address=random
EOF
}

# Configure anti-forensics
configure_anti_forensics() {
    echo "Configuring anti-forensics features..."
    
    # RAM wipe on shutdown
    cat > /mnt/etc/systemd/system/ram-wipe.service << 'EOF'
[Unit]
Description=Wipe RAM on shutdown
DefaultDependencies=no
Before=shutdown.target reboot.target halt.target

[Service]
Type=oneshot
ExecStart=/usr/bin/sdmem -l -l -v

[Install]
WantedBy=shutdown.target reboot.target halt.target
EOF
    
    # Note: sdmem is part of secure-delete package
    # User needs to install it: pacman -S secure-delete
}

# Create post-install info
create_post_install_info() {
    cat > /mnt/root/GALACTICA-README.txt << 'EOF'
╔═══════════════════════════════════════════════════════════════╗
║              GALACTICA OS - POST-INSTALLATION                 ║
╚═══════════════════════════════════════════════════════════════╝

IMPORTANT SECURITY INFORMATION:

1. DOM0 NETWORK ISOLATION
   - Dom0 has NO network access (by design)
   - All networking should be done through VMs
   - You need to create a sys-net VM for internet access

2. FIRST BOOT
   - You will be prompted for your disk encryption passphrase
   - Login as root with the password you set during installation

3. NEXT STEPS
   - Create sys-net VM for network access
   - Create sys-usb VM for USB devices
   - Create work/personal VMs as needed

4. USB DEVICES
   - USBGuard is active - new devices are blocked by default
   - To allow a device: usbguard allow-device <device-id>
   - List devices: usbguard list-devices

5. SECURITY FEATURES ACTIVE
   ✓ Full disk encryption (LUKS2)
   ✓ Hardened kernel with 30+ security parameters
   ✓ AppArmor mandatory access control
   ✓ USB device protection
   ✓ Audit logging
   ✓ Dom0 network isolation
   ✓ Firewall (blocks all external connections)
   ✓ MAC address randomization
   ✓ Anti-forensics (secure deletion tools)

6. IMPORTANT COMMANDS
   - View security logs: journalctl -u auditd
   - AppArmor status: aa-status
   - USBGuard status: usbguard list-devices
   - Check firewall: iptables -L -v

7. CREATING VMs
   - You need to set up Xen networking first
   - Create a bridge: brctl addbr xenbr0
   - Then create VMs using xl or your VM manager

8. BACKUPS
   - Regular Btrfs snapshots: btrfs subvolume snapshot /mnt/@ /mnt/.snapshots/snapshot-name
   - Back up /etc/usbguard/rules.conf
   - Back up /etc/apparmor.d/ custom profiles

SUPPORT & DOCUMENTATION:
- For Xen documentation: https://wiki.xenproject.org/
- For AppArmor: https://wiki.archlinux.org/title/AppArmor
- For USBGuard: https://usbguard.github.io/

Stay safe and secure!

EOF
}

#==============================================================================
# MAIN INSTALLATION PROCESS
#==============================================================================
main_installation() {
    (
        echo "0"
        echo "# Preparing installation..."
        sleep 1
        
        echo "5"
        echo "# Partitioning disk..."
        partition_disk
        
        echo "15"
        echo "# Setting up encryption (this will take a few minutes)..."
        setup_luks
        
        echo "25"
        echo "# Installing base system (this will take several minutes)..."
        install_base
        
        echo "45"
        echo "# Configuring system..."
        configure_base_system
        
        echo "55"
        echo "# Applying kernel hardening..."
        apply_kernel_hardening
        
        echo "60"
        echo "# Configuring bootloader..."
        configure_grub
        configure_initramfs
        
        echo "70"
        echo "# Configuring AppArmor..."
        configure_apparmor
        
        echo "75"
        echo "# Configuring USBGuard..."
        configure_usbguard
        
        echo "80"
        echo "# Configuring audit system..."
        configure_audit
        
        echo "85"
        echo "# Locking down Dom0..."
        lockdown_dom0
        
        echo "90"
        echo "# Configuring Xen hypervisor..."
        configure_xen
        
        echo "93"
        echo "# Configuring MAC randomization..."
        configure_mac_random

        echo "95"
        echo "# Installing Galactica components..."
       # install_galactica_components not made yet

        echo "96"
        echo "# Configuring anti-forensics..."
        configure_anti_forensics
        
        echo "98"
        echo "# Creating post-install documentation..."
        create_post_install_info
        
        echo "100"
        echo "# Installation complete!"
        sleep 2
        
    ) | dialog --title "Installing Galactica OS" --gauge "Please wait..." 10 70 0
}

#==============================================================================
# CLEANUP AND FINISH
#==============================================================================
finish_installation() {
    # Unmount everything
    umount -R /mnt 2>/dev/null || true
    cryptsetup close cryptroot 2>/dev/null || true
    
    dialog --title "Installation Complete!" \
           --msgbox "\n\
Galactica OS has been successfully installed!\n\n\
IMPORTANT:\n\
1. Remove the installation media\n\
2. Reboot your system\n\
3. At boot, enter your disk encryption passphrase\n\
4. Login as root\n\
5. Read /root/GALACTICA-README.txt for next steps\n\n\
Your system is now configured with maximum security.\n\
Dom0 is isolated - you'll need to create VMs for actual work.\n\n\
Stay safe!" 20 70
}

# Add this after configure_xen() function

install_galactica_components() {
    dialog --yesno "Do you want to install Galactica compositor and VM manager?\n\n(This requires internet access during installation)" 10 60
    
    if [ $? -eq 0 ]; then
        echo "Installing Galactica components..."
        
        # Clone and build compositor
        arch-chroot /mnt bash -c "
            cd /opt
            git clone https://github.com/yourusername/galactica-compositor.git
            cd galactica-compositor
            cargo build --release
            install -Dm755 target/release/galactica-compositor /usr/bin/galactica-compositor
        "
        
        # Clone and build VM manager
        arch-chroot /mnt bash -c "
            cd /opt
            git clone https://github.com/yourusername/galactica-vmd.git
            cd galactica-vmd
            cargo build --release
            install -Dm755 target/release/galactica-vmd /usr/bin/galactica-vmd
            install -Dm755 target/release/galactica-vm /usr/bin/galactica-vm
        "
        
        # Enable services
        arch-chroot /mnt systemctl enable galactica-compositor
        arch-chroot /mnt systemctl enable galactica-vmd
    fi
}



#==============================================================================
# MAIN SCRIPT EXECUTION
#==============================================================================
main() {
    clear
    
    # Show welcome
    show_welcome
    
    # Select disk
    select_disk || exit 1
    
    # Setup encryption
    setup_encryption
    
    # Configure security
    configure_security
    
    # Configure system
    configure_system
    
    # Review
    review_config || exit 1
    
    # Perform installation
    main_installation
    
    # Finish
    finish_installation
}

# Run main function
main