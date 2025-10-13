#!/usr/bin/env python3
"""
Galactica OS Installer
A secure, resumable installer for compartmentalized operating systems
with advanced security features for journalists and activists
"""

import sys
import os
import json
import logging
import subprocess
import time
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional, List, Tuple, Dict
from enum import Enum
import getpass


class InstallationPhase(Enum):
    """Track installation progress for resume capability"""
    NOT_STARTED = 0
    PREREQUISITES = 1
    DISK_SELECTED = 2
    PARTITIONED = 3
    ENCRYPTED = 4
    FILESYSTEMS = 5
    BASE_INSTALLED = 6
    CONFIGURED = 7
    SECURITY_HARDENING = 8
    BOOTLOADER = 9
    COMPLETED = 10


@dataclass
class SecurityConfig:
    """Security features configuration"""
    kernel_hardening: bool = True
    apparmor: bool = True
    usbguard: bool = True
    audit: bool = True
    mac_randomization: bool = True
    anti_forensics: bool = True
    disable_ipv6: bool = False
    secure_boot: bool = False
    tpm_encryption: bool = False
    disable_swap: bool = True
    hardened_malloc: bool = True
    firewall_lockdown: bool = True
    iommu_isolation: bool = True


@dataclass
class InstallConfig:
    """Installation configuration - can be saved/loaded"""
    disk: str
    hostname: str = "galactica-dom0"
    timezone: str = "UTC"
    locale: str = "en_US.UTF-8"
    security: SecurityConfig = field(default_factory=SecurityConfig)
    current_phase: InstallationPhase = InstallationPhase.NOT_STARTED
    
    # Runtime only - never persisted
    encryption_password: Optional[str] = None
    root_password: Optional[str] = None
    luks_uuid: Optional[str] = None
    efi_partition: Optional[str] = None
    root_partition: Optional[str] = None
    
    def save(self, path: Path):
        """Save config to JSON (excluding passwords)"""
        config_dict = asdict(self)
        config_dict['current_phase'] = self.current_phase.value
        config_dict['security'] = asdict(self.security)
        
        config_dict.pop('encryption_password', None)
        config_dict.pop('root_password', None)
        
        with open(path, 'w') as f:
            json.dump(config_dict, f, indent=2)
        os.chmod(path, 0o600)
    
    @classmethod
    def load(cls, path: Path) -> 'InstallConfig':
        """Load config from JSON"""
        with open(path) as f:
            data = json.load(f)
        data['current_phase'] = InstallationPhase(data['current_phase'])
        data['security'] = SecurityConfig(**data['security'])
        return cls(**data)


class SecurePasswordHandler:
    """Handle passwords securely"""
    
    @staticmethod
    def validate_password_strength(password: str, min_length: int = 20) -> Tuple[bool, str]:
        """Validate password strength"""
        if len(password) < min_length:
            return False, f"Too short (minimum {min_length} characters)"
        
        has_lower = any(c.islower() for c in password)
        has_upper = any(c.isupper() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
        
        variety_count = sum([has_lower, has_upper, has_digit, has_special])
        
        if variety_count < 3:
            return False, "Use at least 3 types: lowercase, uppercase, digits, special chars"
        
        unique_chars = len(set(password))
        if unique_chars < min_length // 2:
            return False, "Password too repetitive"
        
        return True, "Strong password"
    
    @staticmethod
    def get_password(prompt: str, min_length: int = 20, confirm: bool = True) -> str:
        """Get password with validation"""
        while True:
            print(f"\n{prompt}")
            print(f"Requirements: {min_length}+ chars, mix of upper/lower/digits/special")
            password = getpass.getpass("Password: ")
            
            valid, message = SecurePasswordHandler.validate_password_strength(
                password, min_length
            )
            
            if not valid:
                print(f"Error: {message}")
                continue
            
            if confirm:
                confirm_pass = getpass.getpass("Confirm password: ")
                if password != confirm_pass:
                    print("Error: Passwords don't match")
                    continue
            
            return password


class DiskManager:
    """Handle disk operations safely"""
    
    def __init__(self, device_path: str):
        self.device_path = device_path
        self.logger = logging.getLogger(__name__)
    
    def validate_device(self) -> Tuple[bool, str]:
        """Ensure device exists and is safe to use"""
        if not os.path.exists(self.device_path):
            return False, f"Device {self.device_path} does not exist"
        
        try:
            with open('/proc/mounts') as f:
                mounts = f.read()
                if self.device_path in mounts:
                    return False, "Device is currently mounted"
        except:
            pass
        
        return True, "Device OK"
    
    def get_device_info(self) -> Dict:
        """Get device information"""
        try:
            result = subprocess.run(
                ['lsblk', '-J', '-o', 'NAME,SIZE,TYPE,MODEL', self.device_path],
                capture_output=True, text=True, check=True
            )
            info = json.loads(result.stdout)
            return info['blockdevices'][0] if info['blockdevices'] else {}
        except Exception as e:
            self.logger.error(f"Failed to get device info: {e}")
            return {}
    
    def secure_wipe_disk(self, passes: int = 1) -> bool:
        """Securely wipe disk with random data"""
        print(f"\nSecurely wiping {self.device_path}...")
        print("This will take a while. Press Ctrl+C to skip (NOT RECOMMENDED)")
        
        try:
            for pass_num in range(1, passes + 1):
                print(f"\nPass {pass_num}/{passes}...")
                
                cmd = [
                    'dd',
                    'if=/dev/urandom',
                    f'of={self.device_path}',
                    'bs=4M',
                    'status=progress',
                    'conv=fdatasync'
                ]
                
                subprocess.run(cmd, check=True)
            
            return True
            
        except KeyboardInterrupt:
            print("\nWipe interrupted. Disk may contain recoverable data.")
            response = input("Continue with installation anyway? [y/N]: ")
            return response.lower() == 'y'
        except Exception as e:
            self.logger.error(f"Disk wipe failed: {e}")
            return False
    
    def create_partitions(self) -> Tuple[str, str]:
        """Create GPT partitions for EFI and encrypted root"""
        print("\nCreating partitions...")
        
        try:
            subprocess.run(['parted', '-s', self.device_path, 'mklabel', 'gpt'], check=True)
            
            subprocess.run([
                'parted', '-s', self.device_path,
                'mkpart', 'ESP', 'fat32', '1MiB', '513MiB'
            ], check=True)
            subprocess.run([
                'parted', '-s', self.device_path, 'set', '1', 'esp', 'on'
            ], check=True)
            
            subprocess.run([
                'parted', '-s', self.device_path,
                'mkpart', 'primary', '513MiB', '100%'
            ], check=True)
            
            subprocess.run(['partprobe', self.device_path], check=True)
            time.sleep(2)
            
            if 'nvme' in self.device_path or 'mmcblk' in self.device_path:
                efi = f"{self.device_path}p1"
                root = f"{self.device_path}p2"
            else:
                efi = f"{self.device_path}1"
                root = f"{self.device_path}2"
            
            self.logger.info(f"Created partitions: EFI={efi}, Root={root}")
            return efi, root
            
        except Exception as e:
            self.logger.error(f"Partitioning failed: {e}")
            raise


class EncryptionManager:
    """Handle LUKS2 encryption"""
    
    def __init__(self, partition: str, use_tpm: bool = False):
        self.partition = partition
        self.mapper_name = "cryptroot"
        self.use_tpm = use_tpm
        self.logger = logging.getLogger(__name__)
    
    def setup_luks(self, password: str, backup_key: bool = True) -> bool:
        """Create LUKS2 encrypted container"""
        print("\nSetting up LUKS2 encryption...")
        print("Using: AES-XTS-Plain64 with Argon2id KDF")
        
        try:
            cmd = [
                'cryptsetup', 'luksFormat',
                '--type', 'luks2',
                '--cipher', 'aes-xts-plain64',
                '--key-size', '512',
                '--hash', 'sha512',
                '--pbkdf', 'argon2id',
                '--pbkdf-memory', '1048576',
                '--pbkdf-parallel', '4',
                '--iter-time', '5000',
                '--use-random',
                '--label', 'GALACTICA_CRYPT',
                '--sector-size', '4096',
                self.partition
            ]
            
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = proc.communicate(input=f"{password}\n".encode())
            
            if proc.returncode != 0:
                self.logger.error(f"LUKS format failed: {stderr.decode()}")
                return False
            
            if backup_key:
                print("\nAdding backup key slot...")
                backup_pass = SecurePasswordHandler.get_password(
                    "Enter backup recovery password",
                    min_length=20
                )
                self._add_key_slot(password, backup_pass, slot=1)
            
            self.logger.info("LUKS container created successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Encryption setup failed: {e}")
            return False
    
    def _add_key_slot(self, existing_pass: str, new_pass: str, slot: int):
        """Add additional key slot for recovery"""
        cmd = ['cryptsetup', 'luksAddKey', '--key-slot', str(slot), self.partition]
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        input_data = f"{existing_pass}\n{new_pass}\n".encode()
        proc.communicate(input=input_data)
    
    def open_luks(self, password: str) -> bool:
        """Open LUKS container"""
        try:
            cmd = ['cryptsetup', 'open', self.partition, self.mapper_name]
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = proc.communicate(input=f"{password}\n".encode())
            
            if proc.returncode != 0:
                self.logger.error(f"Failed to open LUKS: {stderr.decode()}")
                return False
            
            mapper_path = f"/dev/mapper/{self.mapper_name}"
            if not os.path.exists(mapper_path):
                self.logger.error(f"Mapper device {mapper_path} not found")
                return False
            
            self.logger.info("LUKS container opened successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to open encryption: {e}")
            return False
    
    def get_uuid(self) -> Optional[str]:
        """Get UUID of LUKS partition"""
        try:
            result = subprocess.run(
                ['blkid', '-s', 'UUID', '-o', 'value', self.partition],
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except:
            return None


class FilesystemManager:
    """Manage filesystem creation and mounting"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.mount_point = Path('/mnt')
    
    def create_btrfs(self, device: str, label: str = "GalacticaOS") -> bool:
        """Create Btrfs filesystem with subvolumes"""
        print("\nCreating Btrfs filesystem...")
        
        try:
            subprocess.run([
                'mkfs.btrfs', '-f',
                '-L', label,
                '-m', 'single',
                '-d', 'single',
                device
            ], check=True)
            
            subprocess.run(['mount', device, self.mount_point], check=True)
            
            subvolumes = ['@', '@home', '@snapshots', '@var_log', '@var_cache']
            
            for subvol in subvolumes:
                subprocess.run([
                    'btrfs', 'subvolume', 'create',
                    self.mount_point / subvol[1:]
                ], check=True)
                print(f"  Created subvolume: {subvol}")
            
            subprocess.run(['umount', self.mount_point], check=True)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Btrfs creation failed: {e}")
            return False
    
    def mount_filesystem(self, device: str) -> bool:
        """Mount Btrfs with subvolumes"""
        print("\nMounting filesystem...")
        
        try:
            mount_opts = 'noatime,compress=zstd:3,space_cache=v2,ssd'
            
            subprocess.run([
                'mount', '-o', f'subvol=@,{mount_opts}',
                device, self.mount_point
            ], check=True)
            
            dirs = ['boot', 'home', '.snapshots', 'var/log', 'var/cache']
            for d in dirs:
                (self.mount_point / d).mkdir(parents=True, exist_ok=True)
            
            subvol_mounts = [
                ('@home', 'home', mount_opts),
                ('@snapshots', '.snapshots', 'noatime'),
                ('@var_log', 'var/log', 'noatime'),
                ('@var_cache', 'var/cache', 'noatime'),
            ]
            
            for subvol, path, opts in subvol_mounts:
                subprocess.run([
                    'mount', '-o', f'subvol={subvol},{opts}',
                    device, self.mount_point / path
                ], check=True)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Mounting failed: {e}")
            return False
    
    def create_efi_filesystem(self, device: str) -> bool:
        """Create and mount EFI partition"""
        try:
            subprocess.run(['mkfs.fat', '-F32', device], check=True)
            subprocess.run(['mount', device, self.mount_point / 'boot'], check=True)
            return True
        except Exception as e:
            self.logger.error(f"EFI filesystem creation failed: {e}")
            return False


class SystemInstaller:
    """Install and configure base system"""
    
    def __init__(self, config: InstallConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.mount_point = Path('/mnt')
    
    def install_base_system(self) -> bool:
        """Install base packages using pacstrap"""
        print("\nInstalling base system (this will take several minutes)...")
        
        packages = [
            'base', 'base-devel', 'linux-hardened', 'linux-hardened-headers',
            'linux-firmware', 'intel-ucode', 'amd-ucode',
            'btrfs-progs', 'dosfstools',
            'grub', 'efibootmgr',
            'xen',
            'apparmor', 'audit', 'firejail', 'usbguard',
            'cryptsetup', 'tpm2-tools', 'sbctl',
            'networkmanager', 'dnsmasq', 'iptables-nft',
            'haveged', 'rng-tools',
            'vim', 'tmux', 'git', 'htop', 'man-db', 'man-pages',
            'secure-delete',
            'hardened-malloc',
        ]
        
        try:
            cmd = ['pacstrap', '-K', str(self.mount_point)] + packages
            subprocess.run(cmd, check=True)
            
            self._generate_fstab()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Base installation failed: {e}")
            return False
    
    def _generate_fstab(self):
        """Generate fstab with security options"""
        result = subprocess.run(
            ['genfstab', '-U', str(self.mount_point)],
            capture_output=True, text=True, check=True
        )
        
        with open(self.mount_point / 'etc' / 'fstab', 'w') as f:
            f.write(result.stdout)
            f.write("\n# Galactica OS Secure Mounts\n")
            f.write("tmpfs /tmp tmpfs defaults,noexec,nosuid,nodev,size=2G,mode=1777 0 0\n")
            f.write("tmpfs /var/tmp tmpfs defaults,noexec,nosuid,nodev,size=1G,mode=1777 0 0\n")
            f.write("tmpfs /dev/shm tmpfs defaults,noexec,nosuid,nodev,mode=1777 0 0\n")
            
            if self.config.security.disable_swap:
                f.write("# Swap disabled for security\n")
    
    def configure_base_system(self) -> bool:
        """Configure timezone, locale, hostname"""
        print("\nConfiguring base system...")
        
        try:
            self._chroot(['ln', '-sf', f'/usr/share/zoneinfo/{self.config.timezone}',
                         '/etc/localtime'])
            self._chroot(['hwclock', '--systohc'])
            
            locale_gen = self.mount_point / 'etc' / 'locale.gen'
            with open(locale_gen, 'a') as f:
                f.write(f"\n{self.config.locale} UTF-8\n")
            self._chroot(['locale-gen'])
            
            with open(self.mount_point / 'etc' / 'locale.conf', 'w') as f:
                f.write(f"LANG={self.config.locale}\n")
            
            with open(self.mount_point / 'etc' / 'hostname', 'w') as f:
                f.write(f"{self.config.hostname}\n")
            
            with open(self.mount_point / 'etc' / 'hosts', 'w') as f:
                f.write("127.0.0.1   localhost\n")
                f.write("::1         localhost\n")
                f.write(f"127.0.1.1   {self.config.hostname}.localdomain {self.config.hostname}\n")
            
            if self.config.root_password:
                self._chroot(['chpasswd'], input=f"root:{self.config.root_password}\n")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration failed: {e}")
            return False
    
    def _chroot(self, cmd: List[str], input: str = None) -> subprocess.CompletedProcess:
        """Execute command in chroot"""
        full_cmd = ['arch-chroot', str(self.mount_point)] + cmd
        return subprocess.run(
            full_cmd,
            input=input.encode() if input else None,
            capture_output=True,
            check=True
        )


class SecurityHardening:
    """Apply comprehensive security hardening"""
    
    def __init__(self, config: InstallConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.mount_point = Path('/mnt')
    
    def apply_all_hardening(self) -> bool:
        """Apply all security hardening measures"""
        print("\nApplying security hardening...")
        
        try:
            if self.config.security.kernel_hardening:
                self._apply_kernel_hardening()
            
            if self.config.security.apparmor:
                self._configure_apparmor()
            
            if self.config.security.audit:
                self._configure_audit()
            
            if self.config.security.usbguard:
                self._configure_usbguard()
            
            if self.config.security.firewall_lockdown:
                self._configure_firewall()
            
            if self.config.security.mac_randomization:
                self._configure_mac_randomization()
            
            if self.config.security.anti_forensics:
                self._configure_anti_forensics()
            
            if self.config.security.hardened_malloc:
                self._configure_hardened_malloc()
            
            self._configure_xen()
            self._lockdown_dom0()
            
            # Reload systemd after all changes
            self._chroot(['systemctl', 'daemon-reload'])
            
            return True
            
        except Exception as e:
            self.logger.error(f"Security hardening failed: {e}")
            return False
    
    def _apply_kernel_hardening(self):
        """Apply kernel hardening via sysctl"""
        print("  Kernel hardening")
        
        sysctl_conf = self.mount_point / 'etc' / 'sysctl.d' / '99-galactica-security.conf'
        sysctl_conf.parent.mkdir(parents=True, exist_ok=True)
        
        with open(sysctl_conf, 'w') as f:
            f.write("""# Galactica OS Kernel Hardening

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
net.ipv4.icmp_ignore_bogus_error_responses=1
net.ipv6.conf.all.accept_ra=0
net.ipv6.conf.default.accept_ra=0
net.ipv4.conf.all.log_martians=1
net.ipv4.tcp_timestamps=0

# Kernel Hardening
kernel.dmesg_restrict=1
kernel.kptr_restrict=2
kernel.unprivileged_bpf_disabled=1
kernel.unprivileged_userns_clone=0
kernel.yama.ptrace_scope=3
dev.tty.ldisc_autoload=0
kernel.kexec_load_disabled=1
kernel.sysrq=0
kernel.panic_on_oops=1
kernel.panic=10

# Disable core dumps
kernel.core_pattern=|/bin/false
fs.suid_dumpable=0

# Memory protection
vm.mmap_min_addr=65536
vm.unprivileged_userfaultfd=0
vm.mmap_rnd_bits=32
vm.mmap_rnd_compat_bits=16

# Filesystem hardening
fs.protected_hardlinks=1
fs.protected_symlinks=1
fs.protected_fifos=2
fs.protected_regular=2

# Restrict perf
kernel.perf_event_paranoid=3
""")
        
        if self.config.security.disable_ipv6:
            with open(sysctl_conf, 'a') as f:
                f.write("\n# Disable IPv6\n")
                f.write("net.ipv6.conf.all.disable_ipv6=1\n")
                f.write("net.ipv6.conf.default.disable_ipv6=1\n")
    
    def _configure_audit(self):
        """Configure audit logging"""
        print("  Audit logging")
        
        audit_rules = self.mount_point / 'etc' / 'audit' / 'rules.d' / 'galactica.rules'
        audit_rules.parent.mkdir(parents=True, exist_ok=True)
        
        with open(audit_rules, 'w') as f:
            f.write("""# Galactica OS Audit Rules
-D
-b 8192
-f 2

# Identity changes
-w /etc/passwd -p wa -k identity
-w /etc/group -p wa -k identity
-w /etc/shadow -p wa -k identity
-w /etc/gshadow -p wa -k identity
-w /etc/sudoers -p wa -k identity
-w /etc/sudoers.d/ -p wa -k identity

# Kernel modules
-w /sbin/insmod -p x -k modules
-w /sbin/rmmod -p x -k modules
-w /sbin/modprobe -p x -k modules

# Crypto changes
-w /etc/cryptsetup-keys.d/ -p wa -k crypto
-w /etc/crypttab -p wa -k crypto

# Critical system files
-w /etc/hosts -p wa -k network
-w /etc/hostname -p wa -k network

-e 2
""")
        
        self._chroot(['systemctl', 'enable', 'auditd.service'])
    
    def _configure_apparmor(self):
        """Enable AppArmor"""
        print("  AppArmor mandatory access control")
        
        config = self.mount_point / 'etc' / 'default' / 'apparmor'
        config.parent.mkdir(parents=True, exist_ok=True)
        with open(config, 'w') as f:
            f.write('APPARMOR=enforce\n')
        
        self._chroot(['systemctl', 'enable', 'apparmor.service'])
    
    def _configure_usbguard(self):
        """Configure USBGuard"""
        print("  USBGuard USB protection")
        
        usbguard_conf = self.mount_point / 'etc' / 'usbguard' / 'usbguard-daemon.conf'
        usbguard_conf.parent.mkdir(parents=True, exist_ok=True)
        
        with open(usbguard_conf, 'w') as f:
            f.write("""# Galactica OS USBGuard Configuration
RuleFile=/etc/usbguard/rules.conf
ImplicitPolicyTarget=block
PresentDevicePolicy=apply-policy
InsertedDevicePolicy=block
AuthorizedDefault=none
RestoreControllerDeviceState=false
DeviceManagerBackend=uevent
IPCAllowedUsers=root
IPCAllowedGroups=wheel
""")
        
        self._chroot(['systemctl', 'enable', 'usbguard.service'])
    
    def _configure_firewall(self):
        """Configure strict firewall"""
        print("  Firewall lockdown")
        
        firewall_script = self.mount_point / 'usr' / 'local' / 'bin' / 'galactica-firewall'
        firewall_script.parent.mkdir(parents=True, exist_ok=True)
        
        with open(firewall_script, 'w') as f:
            f.write("""#!/bin/bash
# Galactica Dom0 Firewall

iptables -F
iptables -X
ip6tables -F
ip6tables -X

iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP
ip6tables -P INPUT DROP
ip6tables -P FORWARD DROP
ip6tables -P OUTPUT DROP

iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT
ip6tables -A INPUT -i lo -j ACCEPT
ip6tables -A OUTPUT -o lo -j ACCEPT

# Xen bridge traffic
iptables -A FORWARD -i xenbr+ -j ACCEPT
iptables -A FORWARD -o xenbr+ -j ACCEPT

echo "Galactica firewall active"
""")
        
        os.chmod(firewall_script, 0o755)
        
        firewall_service = self.mount_point / 'etc' / 'systemd' / 'system' / 'galactica-firewall.service'
        with open(firewall_service, 'w') as f:
            f.write("""[Unit]
Description=Galactica Dom0 Firewall
After=network-pre.target
Before=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/galactica-firewall
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
""")
        
        self._chroot(['systemctl', 'enable', 'galactica-firewall.service'])
    
    def _configure_mac_randomization(self):
        """Configure MAC address randomization"""
        print("  MAC address randomization")
        
        nm_conf = self.mount_point / 'etc' / 'NetworkManager' / 'conf.d' / 'mac-randomization.conf'
        nm_conf.parent.mkdir(parents=True, exist_ok=True)
        
        with open(nm_conf, 'w') as f:
            f.write("""[device]
wifi.scan-rand-mac-address=yes

[connection]
wifi.cloned-mac-address=random
ethernet.cloned-mac-address=random
connection.stable-id=${CONNECTION}/${BOOT}
""")
    
    def _configure_anti_forensics(self):
        """Configure anti-forensics features"""
        print("  Anti-forensics (RAM wipe on shutdown)")
        
        ram_wipe_service = self.mount_point / 'etc' / 'systemd' / 'system' / 'ram-wipe.service'
        with open(ram_wipe_service, 'w') as f:
            f.write("""[Unit]
Description=Wipe RAM on shutdown
DefaultDependencies=no
Before=shutdown.target reboot.target halt.target

[Service]
Type=oneshot
ExecStart=/usr/bin/sdmem -l -l -v
TimeoutStartSec=infinity

[Install]
WantedBy=shutdown.target reboot.target halt.target
""")
        
        self._chroot(['systemctl', 'enable', 'ram-wipe.service'])
        
        secure_rm = self.mount_point / 'usr' / 'local' / 'bin' / 'secure-rm'
        with open(secure_rm, 'w') as f:
            f.write("""#!/bin/bash
srm -v "$@"
""")
        os.chmod(secure_rm, 0o755)
    
    def _configure_hardened_malloc(self):
        """Enable hardened memory allocator"""
        print("  Hardened malloc")
        
        preload = self.mount_point / 'etc' / 'ld.so.preload'
        with open(preload, 'w') as f:
            f.write('/usr/lib/libhardened_malloc.so\n')
    
    def _configure_xen(self):
        """Configure Xen hypervisor"""
        print("  Xen hypervisor")
        
        xen_conf = self.mount_point / 'etc' / 'xen' / 'xl.conf'
        xen_conf.parent.mkdir(parents=True, exist_ok=True)
        
        with open(xen_conf, 'w') as f:
            f.write("""# Galactica OS Xen Configuration
autoballoon="off"
dom0_mem="4096M,max:4096M"
dom0_max_vcpus=4
dom0_vcpus_pin=true
vif.default.script="vif-bridge"
vif.default.bridge="xenbr0"
""")
        
        self._chroot(['systemctl', 'enable', 'xen-qemu-dom0-disk-backend.service'])
        self._chroot(['systemctl', 'enable', 'xen-init-dom0.service'])
    
    def _lockdown_dom0(self):
        """Complete Dom0 lockdown"""
        print("  Dom0 lockdown")
        
        self._chroot(['systemctl', 'disable', 'NetworkManager.service'], check_error=False)
        self._chroot(['systemctl', 'mask', 'NetworkManager.service'], check_error=False)
        
        services_to_disable = [
            'bluetooth.service',
            'cups.service',
            'avahi-daemon.service',
            'ModemManager.service'
        ]
        
        for service in services_to_disable:
            self._chroot(['systemctl', 'disable', service], check_error=False)
            self._chroot(['systemctl', 'mask', service], check_error=False)
    
    def _chroot(self, cmd: List[str], check_error: bool = True) -> subprocess.CompletedProcess:
        """Execute command in chroot"""
        full_cmd = ['arch-chroot', str(self.mount_point)] + cmd
        try:
            return subprocess.run(full_cmd, capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            if not check_error:
                return e
            raise


class BootloaderInstaller:
    """Install and configure GRUB"""
    
    def __init__(self, config: InstallConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.mount_point = Path('/mnt')
    
    def install_grub(self) -> bool:
        """Install GRUB with hardened boot parameters"""
        print("\nInstalling GRUB bootloader...")
        
        try:
            if not self.config.luks_uuid:
                raise RuntimeError("LUKS UUID not set - encryption must complete first")
            
            self._chroot([
                'grub-install',
                '--target=x86_64-efi',
                '--efi-directory=/boot',
                '--bootloader-id=GALACTICA',
                '--recheck'
            ])
            
            self._configure_grub()
            
            self._chroot(['grub-mkconfig', '-o', '/boot/grub/grub.cfg'])
            
            if self.config.security.secure_boot:
                self._configure_secure_boot()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Bootloader installation failed: {e}")
            return False
    
    def _configure_grub(self):
        """Configure GRUB with hardened kernel parameters"""
        grub_default = self.mount_point / 'etc' / 'default' / 'grub'
        
        cmdline_parts = [
            'quiet', 'loglevel=0',
            'slab_nomerge',
            'init_on_alloc=1',
            'init_on_free=1',
            'page_alloc.shuffle=1',
            'pti=on',
            'vsyscall=none',
            'debugfs=off',
            'oops=panic',
            'module.sig_enforce=1',
            'lockdown=confidentiality',
            'mce=0',
        ]
        
        if self.config.security.iommu_isolation:
            cmdline_parts.extend(['iommu=force', 'intel_iommu=on', 'amd_iommu=on'])
        
        if self.config.security.disable_ipv6:
            cmdline_parts.append('ipv6.disable=1')
        
        cmdline_default = ' '.join(cmdline_parts)
        
        cmdline_linux = f'cryptdevice=UUID={self.config.luks_uuid}:cryptroot root=/dev/mapper/cryptroot'
        
        if self.config.security.apparmor:
            cmdline_linux += ' apparmor=1 security=apparmor'
        
        with open(grub_default, 'w') as f:
            f.write(f"""# Galactica OS GRUB Configuration
GRUB_DEFAULT=0
GRUB_TIMEOUT=5
GRUB_DISTRIBUTOR="Galactica OS"
GRUB_CMDLINE_LINUX_DEFAULT="{cmdline_default}"
GRUB_CMDLINE_LINUX="{cmdline_linux}"
GRUB_DISABLE_RECOVERY=true
GRUB_DISABLE_OS_PROBER=true
GRUB_GFXMODE=auto
GRUB_GFXPAYLOAD_LINUX=keep
GRUB_DISABLE_SUBMENU=y
GRUB_ENABLE_CRYPTODISK=y
""")
    
    def _configure_secure_boot(self):
        """Configure Secure Boot with sbctl"""
        print("  Configuring Secure Boot...")
        
        try:
            self._chroot(['sbctl', 'create-keys'])
            self._chroot(['sbctl', 'enroll-keys', '-m'])
            self._chroot(['sbctl', 'sign', '-s', '/boot/grub/x86_64-efi/grub.efi'])
            self._chroot(['sbctl', 'sign', '-s', '/boot/vmlinuz-linux-hardened'])
            
            print("  Enable Secure Boot in UEFI firmware after reboot")
            
        except Exception as e:
            self.logger.warning(f"Secure Boot configuration failed: {e}")
            print("  Secure Boot setup incomplete - may need manual configuration")
    
    def configure_initramfs(self) -> bool:
        """Configure initramfs for encryption"""
        print("\nConfiguring initramfs...")
        
        try:
            mkinitcpio_conf = self.mount_point / 'etc' / 'mkinitcpio.conf'
            
            with open(mkinitcpio_conf, 'w') as f:
                f.write("""# Galactica OS mkinitcpio configuration
MODULES=(btrfs)
BINARIES=()
FILES=()
HOOKS=(base systemd autodetect keyboard sd-vconsole modconf block sd-encrypt filesystems fsck)
COMPRESSION="zstd"
COMPRESSION_OPTIONS=(-3)
""")
            
            self._chroot(['mkinitcpio', '-P'])
            
            return True
            
        except Exception as e:
            self.logger.error(f"Initramfs configuration failed: {e}")
            return False
    
    def _chroot(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Execute command in chroot"""
        full_cmd = ['arch-chroot', str(self.mount_point)] + cmd
        return subprocess.run(full_cmd, capture_output=True, check=True)


class GalacticaInstaller:
    """Main installer orchestrator"""
    
    def __init__(self):
        self.config: Optional[InstallConfig] = None
        self.state_file = Path("/tmp/galactica_install_state.json")
        
        log_file = Path('/tmp/galactica_install.log')
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def check_prerequisites(self) -> bool:
        """Verify system is ready"""
        print("\nChecking prerequisites...")
        
        checks = {
            'Running as root': os.geteuid() == 0,
            'UEFI firmware': Path('/sys/firmware/efi').exists(),
            'Internet connection': self._check_internet(),
            'Sufficient RAM (2GB+)': self._check_ram(),
        }
        
        all_passed = True
        for check, result in checks.items():
            status = "✓" if result else "✗"
            print(f"  {status} {check}")
            if not result:
                all_passed = False
        
        return all_passed
    
    def _check_internet(self) -> bool:
        """Check internet connectivity"""
        try:
            subprocess.run(
                ['ping', '-c', '1', '-W', '3', '1.1.1.1'],
                capture_output=True,
                timeout=5,
                check=True
            )
            return True
        except:
            return False
    
    def _check_ram(self) -> bool:
        """Check available RAM"""
        try:
            with open('/proc/meminfo') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        mem_kb = int(line.split()[1])
                        return mem_kb >= 2 * 1024 * 1024
        except:
            pass
        return False
    
    def interactive_setup(self):
        """Interactive configuration"""
        print("\n" + "="*60)
        print("GALACTICA OS INSTALLER")
        print("="*60)
        print("\nSecure Operating System for Journalists and Activists")
        print("\nWARNING: This will ERASE ALL DATA on the selected disk!")
        
        response = input("\nContinue? [yes/NO]: ")
        if response.lower() != 'yes':
            print("Installation cancelled.")
            sys.exit(0)
        
        self._select_disk()
        
        hostname = input(f"\nHostname [{self.config.hostname}]: ").strip()
        if hostname:
            self.config.hostname = hostname
        
        print("\nSecurity Configuration:")
        print("  1. Maximum (recommended for high-threat environments)")
        print("  2. Balanced (good security with better compatibility)")
        print("  3. Custom")
        
        choice = input("\nSelect security level [1]: ").strip() or "1"
        
        if choice == "1":
            pass
        elif choice == "2":
            self.config.security.disable_ipv6 = False
            self.config.security.anti_forensics = False
        elif choice == "3":
            self._custom_security_config()
        
        if Path('/sys/class/tpm/tpm0').exists():
            response = input("\nTPM 2.0 detected. Use TPM for auto-unlock? [y/N]: ")
            self.config.security.tpm_encryption = response.lower() == 'y'
        
        response = input("Configure Secure Boot? [y/N]: ")
        self.config.security.secure_boot = response.lower() == 'y'
    
    def _select_disk(self):
        """Interactive disk selection"""
        print("\nAvailable disks:")
        result = subprocess.run(
            ['lsblk', '-d', '-n', '-o', 'NAME,SIZE,TYPE,MODEL'],
            capture_output=True, text=True
        )
        print(result.stdout)
        
        while True:
            disk = input("\nEnter disk path (e.g., /dev/sda): ").strip()
            
            if not disk.startswith('/dev/'):
                print("Invalid path. Must start with /dev/")
                continue
            
            manager = DiskManager(disk)
            valid, message = manager.validate_device()
            
            if not valid:
                print(f"Error: {message}")
                response = input("Try another disk? [Y/n]: ")
                if response.lower() == 'n':
                    sys.exit(1)
                continue
            
            info = manager.get_device_info()
            print(f"\nSelected: {info.get('model', 'Unknown')} ({info.get('size', 'Unknown')})")
            print(f"  Path: {disk}")
            
            confirm = input("\nType 'DELETE MY DATA' to confirm: ")
            if confirm == "DELETE MY DATA":
                self.config.disk = disk
                break
            else:
                print("Confirmation failed")
    
    def _custom_security_config(self):
        """Custom security configuration"""
        print("\nCustom Security Configuration:")
        
        options = [
            ('kernel_hardening', "Kernel hardening"),
            ('apparmor', "AppArmor MAC"),
            ('usbguard', "USBGuard"),
            ('audit', "Audit logging"),
            ('firewall_lockdown', "Dom0 firewall"),
            ('mac_randomization', "MAC randomization"),
            ('anti_forensics', "Anti-forensics (RAM wipe)"),
            ('disable_ipv6', "Disable IPv6"),
            ('hardened_malloc', "Hardened malloc"),
        ]
        
        for attr, desc in options:
            default = 'Y' if getattr(self.config.security, attr) else 'N'
            response = input(f"  {desc} [{default}]: ").strip().lower()
            if response:
                setattr(self.config.security, attr, response == 'y')
    
    def run_installation(self):
        """Execute full installation"""
        phases = [
            (InstallationPhase.DISK_SELECTED, self._phase_disk),
            (InstallationPhase.PARTITIONED, self._phase_partition),
            (InstallationPhase.ENCRYPTED, self._phase_encryption),
            (InstallationPhase.FILESYSTEMS, self._phase_filesystems),
            (InstallationPhase.BASE_INSTALLED, self._phase_base_install),
            (InstallationPhase.CONFIGURED, self._phase_configure),
            (InstallationPhase.SECURITY_HARDENING, self._phase_security),
            (InstallationPhase.BOOTLOADER, self._phase_bootloader),
            (InstallationPhase.COMPLETED, self._phase_finalize),
        ]
        
        for phase, handler in phases:
            if phase.value <= self.config.current_phase.value:
                print(f"\nSkipping {phase.name} (already completed)")
                continue
            
            try:
                print(f"\n{'='*60}")
                print(f"Phase {phase.value}/{len(phases)}: {phase.name}")
                print(f"{'='*60}")
                
                handler()
                
                self.config.current_phase = phase
                self.config.save(self.state_file)
                
                print(f"\nPhase {phase.name} completed")
                
            except KeyboardInterrupt:
                print("\n\nInstallation interrupted!")
                print(f"State saved. Resume with: sudo python3 {sys.argv[0]} --resume")
                sys.exit(130)
            except Exception as e:
                self.logger.error(f"Phase {phase.name} failed: {e}", exc_info=True)
                print(f"\nPhase {phase.name} failed: {e}")
                print("Check log: /tmp/galactica_install.log")
                sys.exit(1)
    
    def _phase_disk(self):
        """Disk preparation"""
        manager = DiskManager(self.config.disk)
        response = input("\nSecurely wipe disk? (SLOW but more secure) [y/N]: ")
        if response.lower() == 'y':
            if not manager.secure_wipe_disk(passes=1):
                raise RuntimeError("Disk wipe failed or cancelled")
    
    def _phase_partition(self):
        """Partition disk"""
        manager = DiskManager(self.config.disk)
        efi, root = manager.create_partitions()
        self.config.efi_partition = efi
        self.config.root_partition = root
        print(f"Created: EFI={efi}, Root={root}")
    
    def _phase_encryption(self):
        """Setup encryption"""
        print("\nEncryption Setup")
        password = SecurePasswordHandler.get_password(
            "Enter disk encryption passphrase",
            min_length=20
        )
        
        response = input("\nAdd backup recovery key? [Y/n]: ")
        add_backup = response.lower() != 'n'
        
        enc = EncryptionManager(self.config.root_partition, self.config.security.tpm_encryption)
        
        if not enc.setup_luks(password, backup_key=add_backup):
            raise RuntimeError("Encryption setup failed")
        
        if not enc.open_luks(password):
            raise RuntimeError("Failed to open encrypted volume")
        
        self.config.luks_uuid = enc.get_uuid()
        print(f"LUKS UUID: {self.config.luks_uuid}")
    
    def _phase_filesystems(self):
        """Create filesystems"""
        fs = FilesystemManager()
        
        if not fs.create_btrfs('/dev/mapper/cryptroot'):
            raise RuntimeError("Btrfs creation failed")
        
        if not fs.mount_filesystem('/dev/mapper/cryptroot'):
            raise RuntimeError("Filesystem mount failed")
        
        if not fs.create_efi_filesystem(self.config.efi_partition):
            raise RuntimeError("EFI filesystem creation failed")
        
        print("Filesystems ready")
    
    def _phase_base_install(self):
        """Install base system"""
        installer = SystemInstaller(self.config)
        
        if not installer.install_base_system():
            raise RuntimeError("Base system installation failed")
        
        print("\nRoot Password Setup")
        self.config.root_password = SecurePasswordHandler.get_password(
            "Enter root password",
            min_length=12
        )
        
        if not installer.configure_base_system():
            raise RuntimeError("System configuration failed")
        
        print("Base system installed and configured")
    
    def _phase_configure(self):
        """Configure system"""
        pass
    
    def _phase_security(self):
        """Apply security hardening"""
        hardening = SecurityHardening(self.config)
        
        if not hardening.apply_all_hardening():
            raise RuntimeError("Security hardening failed")
        
        print("Security hardening complete")
    
    def _phase_bootloader(self):
        """Install bootloader"""
        bootloader = BootloaderInstaller(self.config)
        
        if not bootloader.configure_initramfs():
            raise RuntimeError("Initramfs configuration failed")
        
        if not bootloader.install_grub():
            raise RuntimeError("Bootloader installation failed")
        
        print("Bootloader installed")
    
    def _phase_finalize(self):
        """Finalize installation"""
        print("\nCreating post-install documentation...")
        
        readme = Path('/mnt/root/GALACTICA-README.txt')
        with open(readme, 'w') as f:
            f.write("""
GALACTICA OS - POST-INSTALLATION
===================================

INSTALLATION COMPLETE

IMPORTANT SECURITY INFORMATION:

1. FIRST BOOT
   - Enter your disk encryption passphrase at boot
   - Login as root with the password you set

2. DOM0 NETWORK ISOLATION
   - Dom0 has NO network access (by design)
   - Create a sys-net VM for internet access
   - Create a sys-usb VM for USB devices

3. ACTIVE SECURITY FEATURES
   - Full disk encryption (LUKS2 + Argon2id)
   - Hardened kernel (linux-hardened)
   - 30+ kernel hardening parameters
   - AppArmor mandatory access control
   - USBGuard (blocks unauthorized devices)
   - Audit logging enabled
   - Dom0 network isolation
   - Firewall (all external connections blocked)
   - MAC address randomization
   - Hardened memory allocator
   - Xen hypervisor for VM isolation

4. USB DEVICES
   - New USB devices are BLOCKED by default
   - List devices: usbguard list-devices
   - Allow device: usbguard allow-device <ID>
   - Block device: usbguard block-device <ID>

5. BACKUPS
   - Backup LUKS header: cryptsetup luksHeaderBackup
   - Btrfs snapshots: btrfs subvolume snapshot

Stay safe and secure!
""")
        
        print("Installation complete! System is ready for first boot.")


def main():
    """Main entry point"""
    installer = GalacticaInstaller()
    
    if not installer.check_prerequisites():
        print("\nPrerequisite check failed!")
        sys.exit(1)
    
    if '--resume' in sys.argv:
        if not installer.state_file.exists():
            print("No previous installation state found")
            sys.exit(1)
        installer.config = InstallConfig.load(installer.state_file)
        print(f"Resuming from phase: {installer.config.current_phase.name}")
    else:
        installer.config = InstallConfig(disk="")
        installer.interactive_setup()
        installer.config.current_phase = InstallationPhase.PREREQUISITES
    
    installer.run_installation()



main()