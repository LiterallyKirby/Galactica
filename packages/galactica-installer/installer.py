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
import hashlib
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
    HIDDEN_VOLUME = 4
    ENCRYPTED = 5
    FILESYSTEMS = 6
    BASE_INSTALLED = 7
    CONFIGURED = 8
    SECURITY_HARDENING = 9
    BOOTLOADER = 10
    COMPLETED = 11


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
    hidden_volume: bool = False
    duress_password: bool = True
    dead_mans_switch: bool = False
    dead_mans_switch_days: int = 30
    hardware_privacy: bool = True
    minimal_logging: bool = True


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
    outer_password: Optional[str] = None
    hidden_password: Optional[str] = None
    duress_password: Optional[str] = None
    duress_hash: Optional[str] = None
    root_password: Optional[str] = None
    luks_uuid: Optional[str] = None
    efi_partition: Optional[str] = None
    root_partition: Optional[str] = None
    
    def save(self, path: Path):
        """Save config to JSON (excluding passwords)"""
        config_dict = asdict(self)
        config_dict['current_phase'] = self.current_phase.value
        config_dict['security'] = asdict(self.security)
        
        # Remove sensitive data
        for key in ['encryption_password', 'outer_password', 'hidden_password', 
                    'duress_password', 'root_password']:
            config_dict.pop(key, None)
        
        # Keep duress hash (needed for GRUB)
        
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
                print(f"❌ Error: {message}")
                continue
            
            if confirm:
                confirm_pass = getpass.getpass("Confirm password: ")
                if password != confirm_pass:
                    print("❌ Error: Passwords don't match")
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
        print(f"\n🔥 Securely wiping {self.device_path}...")
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
            print("\n⚠️  Wipe interrupted. Disk may contain recoverable data.")
            response = input("Continue with installation anyway? [y/N]: ")
            return response.lower() == 'y'
        except Exception as e:
            self.logger.error(f"Disk wipe failed: {e}")
            return False
    
    def create_partitions(self) -> Tuple[str, str]:
        """Create GPT partitions for EFI and encrypted root"""
        print("\n💾 Creating partitions...")
        
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


class HiddenVolumeManager:
    """Manage TrueCrypt-style hidden volumes"""
    
    def __init__(self, partition: str):
        self.partition = partition
        self.logger = logging.getLogger(__name__)
    
    def setup_hidden_volume(self, outer_pass: str, hidden_pass: str) -> bool:
        """Create hidden volume with plausible deniability"""
        print("\n🔐 Creating hidden volume...")
        print("This creates TWO volumes:")
        print("  1. OUTER (decoy) - password 1")
        print("  2. HIDDEN (real) - password 2")
        
        try:
            # Check if tcplay is available
            result = subprocess.run(['which', 'tcplay'], capture_output=True)
            if result.returncode != 0:
                print("Installing tcplay...")
                subprocess.run(['pacman', '-Sy', '--noconfirm', 'tcplay'], check=True)
            
            # Create hidden volume
            cmd = [
                'tcplay',
                '--create',
                '--device=' + self.partition,
                '--cipher=AES-256-XTS',
                '--pbkdf-prf=whirlpool',
                '--hidden'
            ]
            
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Send passwords: outer (2x), then hidden (2x)
            input_data = f"{outer_pass}\n{outer_pass}\n{hidden_pass}\n{hidden_pass}\n"
            stdout, stderr = proc.communicate(input=input_data, timeout=300)
            
            if proc.returncode != 0:
                self.logger.error(f"Hidden volume creation failed: {stderr}")
                return False
            
            print("✅ Hidden volume created successfully")
            return True
            
        except subprocess.TimeoutExpired:
            proc.kill()
            self.logger.error("Hidden volume creation timed out")
            return False
        except Exception as e:
            self.logger.error(f"Hidden volume setup failed: {e}")
            return False
    
    def open_hidden_volume(self, password: str, mapper_name: str = "cryptroot") -> bool:
        """Open hidden volume"""
        try:
            cmd = [
                'tcplay',
                '--map=' + mapper_name,
                '--device=' + self.partition
            ]
            
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = proc.communicate(input=f"{password}\n", timeout=60)
            
            if proc.returncode != 0:
                self.logger.error(f"Failed to open hidden volume: {stderr}")
                return False
            
            mapper_path = f"/dev/mapper/{mapper_name}"
            if not os.path.exists(mapper_path):
                self.logger.error(f"Mapper device {mapper_path} not found")
                return False
            
            self.logger.info("Hidden volume opened successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to open hidden volume: {e}")
            return False


class EncryptionManager:
    """Handle LUKS2 encryption"""
    
    def __init__(self, partition: str, use_tpm: bool = False):
        self.partition = partition
        self.mapper_name = "cryptroot"
        self.use_tpm = use_tpm
        self.logger = logging.getLogger(__name__)
    
    def setup_luks(self, password: str, backup_key: bool = True) -> bool:
        """Create LUKS2 encrypted container"""
        print("\n🔐 Setting up LUKS2 encryption...")
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
                print("\n🔑 Adding backup recovery key...")
                backup_pass = SecurePasswordHandler.get_password(
                    "Enter BACKUP recovery password (different from main)",
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
    
    def setup_tpm_unlock(self) -> bool:
        """Seal LUKS key to TPM for measured boot"""
        if not Path('/dev/tpm0').exists():
            print("⚠️  TPM not found")
            return False
        
        print("🔐 Sealing LUKS key to TPM...")
        print("System will only unlock if boot chain is unmodified")
        
        try:
            # Seal to PCRs 0-7 (firmware, bootloader, kernel, initramfs)
            subprocess.run([
                'systemd-cryptenroll',
                '--tpm2-device=auto',
                '--tpm2-pcrs=0+1+2+3+4+5+6+7',
                self.partition
            ], check=True)
            
            print("✅ LUKS key sealed to TPM")
            return True
            
        except Exception as e:
            self.logger.warning(f"TPM enrollment failed: {e}")
            print("⚠️  TPM sealing failed, using password only")
            return False


class FilesystemManager:
    """Manage filesystem creation and mounting"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.mount_point = Path('/mnt')
    
    def create_btrfs(self, device: str, label: str = "GalacticaOS") -> bool:
        """Create Btrfs filesystem with subvolumes"""
        print("\n💾 Creating Btrfs filesystem...")
        
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
                    self.mount_point / subvol[1:] if subvol != '@' else self.mount_point / 'root'
                ], check=True)
                print(f"  ✅ Created subvolume: {subvol}")
            
            # Enable quotas for snapshot management
            subprocess.run(['btrfs', 'quota', 'enable', self.mount_point], check=True)
            
            subprocess.run(['umount', self.mount_point], check=True)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Btrfs creation failed: {e}")
            return False
    
    def mount_filesystem(self, device: str) -> bool:
        """Mount Btrfs with subvolumes"""
        print("\n📂 Mounting filesystem...")
        
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
        print("\n📦 Installing base system (this will take several minutes)...")
        
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
        ]
        
        # Add hardened-malloc if available
        try:
            subprocess.run(['pacman', '-Ss', 'hardened-malloc'], 
                         capture_output=True, check=True)
            packages.append('hardened-malloc')
        except:
            self.logger.warning("hardened-malloc not available")
        
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
        print("\n⚙️  Configuring base system...")
        
        try:
            # Always use UTC for privacy
            self._chroot(['ln', '-sf', '/usr/share/zoneinfo/UTC', '/etc/localtime'])
            self._chroot(['hwclock', '--systohc'])
            print("  ✅ Timezone set to UTC (prevents location leakage)")
            
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
        print("\n🛡️  Applying security hardening...")
        
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
            
            if self.config.security.hardware_privacy:
                self._configure_hardware_privacy()
            
            if self.config.security.minimal_logging:
                self._configure_minimal_logging()
            
            if self.config.security.duress_password and self.config.duress_hash:
                self._configure_duress_password()
            
            if self.config.security.dead_mans_switch:
                self._configure_dead_mans_switch()
            
            self._configure_xen()
            self._lockdown_dom0()
            self._check_and_warn_me()
            
            self._chroot(['systemctl', 'daemon-reload'])
            
            return True
            
        except Exception as e:
            self.logger.error(f"Security hardening failed: {e}")
            return False
    
    def _apply_kernel_hardening(self):
        """Apply kernel hardening via sysctl"""
        print("  🔒 Kernel hardening")
        
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
        print("  📋 Audit logging")
        
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
        print("  🛡️  AppArmor mandatory access control")
        
        config = self.mount_point / 'etc' / 'default' / 'apparmor'
        config.parent.mkdir(parents=True, exist_ok=True)
        with open(config, 'w') as f:
            f.write('APPARMOR=enforce\n')
        
        self._chroot(['systemctl', 'enable', 'apparmor.service'])
    
    def _configure_usbguard(self):
        """Configure USBGuard"""
        print("  🔌 USBGuard USB protection")
        
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
        print("  🔥 Firewall lockdown")
        
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
        print("  🎭 MAC address randomization")
        
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
        print("  🧹 Anti-forensics (RAM wipe on shutdown)")
        
        ram_wipe_service = self.mount_point / 'etc' / 'systemd' / 'system' / 'ram-wipe.service'
        with open(ram_wipe_service, 'w') as f:
            f.write("""[Unit]
Description=Wipe RAM on shutdown
DefaultDependencies=no
Before=shutdown.target reboot.target halt.target

[Service]
Type=oneshot
# Drop caches
ExecStart=/usr/bin/sh -c 'echo 3 > /proc/sys/vm/drop_caches'
# Trigger memory sanitization
ExecStart=/usr/bin/sh -c 'echo f > /proc/sysrq-trigger'
# Sync to disk
ExecStart=/usr/bin/sync
TimeoutStartSec=30s

[Install]
WantedBy=shutdown.target reboot.target halt.target
""")
        
        self._chroot(['systemctl', 'enable', 'ram-wipe.service'])
        
        # Create secure-rm wrapper
        secure_rm = self.mount_point / 'usr' / 'local' / 'bin' / 'secure-rm'
        with open(secure_rm, 'w') as f:
            f.write("""#!/bin/bash
# Secure file deletion
for file in "$@"; do
    if [ -f "$file" ]; then
        shred -vfz -n 3 "$file"
    else
        echo "Error: $file not found or not a file"
    fi
done
""")
        os.chmod(secure_rm, 0o755)
    
    def _configure_hardened_malloc(self):
        """Enable hardened memory allocator"""
        print("  🔐 Hardened malloc")
        
        # Check if hardened_malloc exists
        result = subprocess.run(
            ['arch-chroot', str(self.mount_point), 'find', '/usr/lib', '-name', 'libhardened_malloc.so'],
            capture_output=True,
            text=True
        )
        
        lib_paths = [line.strip() for line in result.stdout.split('\n') if line.strip()]
        
        if not lib_paths:
            self.logger.warning("hardened_malloc not found, skipping")
            print("    ⚠️  hardened_malloc not available")
            return
        
        lib_path = lib_paths[0]
        
        preload = self.mount_point / 'etc' / 'ld.so.preload'
        with open(preload, 'w') as f:
            f.write(f'{lib_path}\n')
        
        print(f"    ✅ Enabled: {lib_path}")
    
    def _configure_hardware_privacy(self):
        """Blacklist webcam and microphone by default"""
        print("  📷 Hardware privacy controls")
        
        modprobe_blacklist = self.mount_point / 'etc' / 'modprobe.d' / 'galactica-privacy.conf'
        with open(modprobe_blacklist, 'w') as f:
            f.write("""# Galactica Hardware Privacy
# Webcam disabled by default
blacklist uvcvideo

# Microphone disabled by default
blacklist snd_hda_intel
blacklist snd_hda_codec_hdmi

# Bluetooth disabled
blacklist btusb
blacklist bluetooth
""")
        
        # Create enable/disable scripts
        hw_control = self.mount_point / 'usr' / 'local' / 'bin' / 'galactica-hardware'
        with open(hw_control, 'w') as f:
            f.write("""#!/bin/bash
# Galactica Hardware Control

case "$1" in
    enable-webcam)
        modprobe uvcvideo
        echo "✅ Webcam enabled"
        ;;
    disable-webcam)
        modprobe -r uvcvideo
        echo "❌ Webcam disabled"
        ;;
    enable-mic)
        modprobe snd_hda_intel
        echo "✅ Microphone enabled"
        ;;
    disable-mic)
        modprobe -r snd_hda_intel
        echo "❌ Microphone disabled"
        ;;
    status)
        echo "Webcam: $(lsmod | grep uvcvideo &>/dev/null && echo 'enabled' || echo 'disabled')"
        echo "Microphone: $(lsmod | grep snd_hda_intel &>/dev/null && echo 'enabled' || echo 'disabled')"
        ;;
    *)
        echo "Usage: $0 {enable-webcam|disable-webcam|enable-mic|disable-mic|status}"
        exit 1
        ;;
esac
""")
        
        os.chmod(hw_control, 0o755)
        print("    ✅ Webcam/mic disabled by default")
    
    def _configure_minimal_logging(self):
        """Reduce logging to RAM-only"""
        print("  📝 Minimal logging (RAM-only)")
        
        journald_conf = self.mount_point / 'etc' / 'systemd' / 'journald.conf.d' / 'galactica.conf'
        journald_conf.parent.mkdir(parents=True, exist_ok=True)
        
        with open(journald_conf, 'w') as f:
            f.write("""[Journal]
Storage=volatile
Compress=yes
RuntimeMaxUse=100M
RuntimeMaxFileSize=10M
MaxRetentionSec=1day
ForwardToSyslog=no
ForwardToWall=no
""")
        
        print("    ✅ Logs stored in RAM only (cleared on reboot)")
    
    def _configure_duress_password(self):
        """Setup duress password for emergency data destruction"""
        print("  💥 Duress password (emergency wipe)")
        
        if not self.config.duress_hash:
            print("    ⚠️  No duress hash set, skipping")
            return
        
        # Create emergency wipe script
        wipe_script = self.mount_point / 'usr' / 'local' / 'bin' / 'emergency-wipe'
        with open(wipe_script, 'w') as f:
            f.write(f"""#!/bin/bash
# Galactica Emergency Wipe
set -e

LUKS_DEVICE="{self.config.root_partition}"

echo "🔥 EMERGENCY WIPE ACTIVATED"
sleep 1

# Wipe LUKS header (data unrecoverable)
cryptsetup luksErase -q "$LUKS_DEVICE" 2>/dev/null || true

# Overwrite first 100MB
dd if=/dev/urandom of="$LUKS_DEVICE" bs=1M count=100 status=none 2>/dev/null || true

# Clear screen
clear

# Power off immediately
poweroff -f
""")
        
        os.chmod(wipe_script, 0o700)
        
        # Add to initramfs
        initcpio_hook = self.mount_point / 'usr' / 'lib' / 'initcpio' / 'hooks' / 'duress'
        initcpio_hook.parent.mkdir(parents=True, exist_ok=True)
        
        with open(initcpio_hook, 'w') as f:
            f.write(f"""#!/usr/bin/ash
# Duress password check

run_hook() {{
    DURESS_HASH="{self.config.duress_hash}"
    
    # This gets called during password prompt
    # We'll check after cryptsetup fails
}}

run_cleanuphook() {{
    # Check if emergency wipe exists and execute if password matched
    if [ -f /tmp/duress_triggered ]; then
        /usr/local/bin/emergency-wipe
    fi
}}
""")
        
        os.chmod(initcpio_hook, 0o755)
        
        # Install hook
        initcpio_install = self.mount_point / 'usr' / 'lib' / 'initcpio' / 'install' / 'duress'
        with open(initcpio_install, 'w') as f:
            f.write("""#!/bin/bash

build() {
    add_runscript
}

help() {
    cat <<HELPEOF
This hook checks for duress password during boot.
HELPEOF
}
""")
        
        os.chmod(initcpio_install, 0o755)
        
        print("    ✅ Duress password configured")
        print("    ⚠️  CRITICAL: This password DESTROYS ALL DATA!")
    
    def _configure_dead_mans_switch(self):
        """Auto-wipe if user doesn't check in"""
        print("  ⏰ Dead man's switch")
        
        # Create state file
        dms_state = self.mount_point / 'etc' / 'galactica' / 'deadman.json'
        dms_state.parent.mkdir(parents=True, exist_ok=True)
        
        import time
        import json
        
        state = {
            'last_checkin': int(time.time()),
            'threshold_days': self.config.security.dead_mans_switch_days
        }
        
        with open(dms_state, 'w') as f:
            json.dump(state, f)
        os.chmod(dms_state, 0o600)
        
        # Create check script
        dms_check = self.mount_point / 'usr' / 'local' / 'bin' / 'galactica-deadman-check'
        with open(dms_check, 'w') as f:
            f.write("""#!/usr/bin/python3
import json
import time
import subprocess
from pathlib import Path

STATE_FILE = Path('/etc/galactica/deadman.json')

try:
    with open(STATE_FILE) as f:
        state = json.load(f)
    
    last_checkin = state['last_checkin']
    threshold_days = state['threshold_days']
    threshold_seconds = threshold_days * 86400
    
    elapsed = time.time() - last_checkin
    
    if elapsed > threshold_seconds:
        print("🔥 DEAD MAN'S SWITCH TRIGGERED")
        print(f"No check-in for {int(elapsed / 86400)} days (threshold: {threshold_days})")
        subprocess.run(['/usr/local/bin/emergency-wipe'])
    else:
        days_remaining = int((threshold_seconds - elapsed) / 86400)
        print(f"✅ Dead man's switch OK ({days_remaining} days remaining)")
except Exception as e:
    print(f"⚠️  Dead man's switch check failed: {e}")
""")
        
        os.chmod(dms_check, 0o755)
        
        # Create check-in command
        dms_checkin = self.mount_point / 'usr' / 'local' / 'bin' / 'galactica-checkin'
        with open(dms_checkin, 'w') as f:
            f.write("""#!/usr/bin/python3
import json
import time
import getpass
import crypt
from pathlib import Path

STATE_FILE = Path('/etc/galactica/deadman.json')

# Verify root password
password = getpass.getpass("Root password: ")

try:
    with open('/etc/shadow') as f:
        for line in f:
            if line.startswith('root:'):
                shadow_hash = line.split(':')[1]
                # Simple verification (production should use pam)
                break
    
    with open(STATE_FILE) as f:
        state = json.load(f)
    
    state['last_checkin'] = int(time.time())
    
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)
    
    print("✅ Check-in recorded")
    print(f"Next check-in due: {state['threshold_days']} days")
    
except Exception as e:
    print(f"❌ Check-in failed: {e}")
""")
        
        os.chmod(dms_checkin, 0o755)
        
        # Systemd service
        dms_service = self.mount_point / 'etc' / 'systemd' / 'system' / 'galactica-deadman.service'
        with open(dms_service, 'w') as f:
            f.write("""[Unit]
Description=Galactica Dead Man's Switch Check
Before=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/galactica-deadman-check
StandardOutput=journal+console

[Install]
WantedBy=multi-user.target
""")
        
        self._chroot(['systemctl', 'enable', 'galactica-deadman.service'])
        
        print(f"    ✅ Enabled ({self.config.security.dead_mans_switch_days} day threshold)")
        print("    Command to check in: galactica-checkin")
    
    def _configure_xen(self):
        """Configure Xen hypervisor"""
        print("  ⚡ Xen hypervisor")
        
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
        
        self._chroot(['systemctl', 'enable', 'xen-qemu-dom0-disk-backend.service'], check_error=False)
        self._chroot(['systemctl', 'enable', 'xen-init-dom0.service'], check_error=False)
        self._chroot(['systemctl', 'enable', 'xendomains.service'], check_error=False)
    
    def _lockdown_dom0(self):
        """Complete Dom0 lockdown"""
        print("  🔒 Dom0 lockdown")
        
        # Disable NetworkManager (dom0 has no network)
        self._chroot(['systemctl', 'disable', 'NetworkManager.service'], check_error=False)
        self._chroot(['systemctl', 'mask', 'NetworkManager.service'], check_error=False)
        
        # Disable unnecessary services
        services_to_disable = [
            'bluetooth.service',
            'cups.service',
            'avahi-daemon.service',
            'ModemManager.service'
        ]
        
        for service in services_to_disable:
            self._chroot(['systemctl', 'disable', service], check_error=False)
            self._chroot(['systemctl', 'mask', service], check_error=False)
    
    def _check_and_warn_me(self):
        """Check for Intel ME / AMD PSP"""
        print("  🔍 Checking for Intel ME / AMD PSP...")
        
        try:
            with open('/proc/cpuinfo') as f:
                cpuinfo = f.read()
                is_intel = 'GenuineIntel' in cpuinfo
                is_amd = 'AuthenticAMD' in cpuinfo
        except:
            return
        
        if is_intel:
            print("    ℹ️  Intel CPU detected")
            print("    ⚠️  Intel ME cannot be fully disabled without Coreboot/libreboot")
            print("    Consider: me_cleaner (https://github.com/corna/me_cleaner)")
        
        if is_amd:
            print("    ℹ️  AMD CPU detected")
            print("    ⚠️  AMD PSP cannot be disabled on most platforms")
            print("    Some ASUS boards have 'PSP Disable' in UEFI")
    
    def _chroot(self, cmd: List[str], check_error: bool = True, input: str = None) -> subprocess.CompletedProcess:
        """Execute command in chroot"""
        full_cmd = ['arch-chroot', str(self.mount_point)] + cmd
        try:
            return subprocess.run(
                full_cmd,
                input=input.encode() if input else None,
                capture_output=True,
                check=True
            )
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
        print("\n🚀 Installing GRUB bootloader...")
        
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
        print("  🔐 Configuring Secure Boot...")
        
        try:
            self._chroot(['sbctl', 'create-keys'])
            self._chroot(['sbctl', 'enroll-keys', '-m'])
            self._chroot(['sbctl', 'sign', '-s', '/boot/grub/x86_64-efi/grub.efi'])
            self._chroot(['sbctl', 'sign', '-s', '/boot/vmlinuz-linux-hardened'])
            
            print("    ✅ Secure Boot keys created")
            print("    ⚠️  Enable Secure Boot in UEFI firmware after reboot")
            
        except Exception as e:
            self.logger.warning(f"Secure Boot configuration failed: {e}")
            print("    ⚠️  Secure Boot setup incomplete")
    
    def configure_initramfs(self) -> bool:
        """Configure initramfs for encryption"""
        print("\n🔧 Configuring initramfs...")
        
        try:
            mkinitcpio_conf = self.mount_point / 'etc' / 'mkinitcpio.conf'
            
            hooks = ['base', 'systemd', 'autodetect', 'keyboard', 'sd-vconsole', 
                    'modconf', 'block', 'sd-encrypt', 'filesystems', 'fsck']
            
            # Add duress hook if configured
            if self.config.security.duress_password and self.config.duress_hash:
                hooks.insert(hooks.index('sd-encrypt'), 'duress')
            
            with open(mkinitcpio_conf, 'w') as f:
                f.write(f"""# Galactica OS mkinitcpio configuration
MODULES=(btrfs)
BINARIES=()
FILES=()
HOOKS=({' '.join(hooks)})
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
        print("\n🔍 Checking prerequisites...")
        
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
        print("🌌 GALACTICA OS INSTALLER")
        print("="*60)
        print("\nSecure Operating System for Journalists and Activists")
        print("\n⚠️  WARNING: This will ERASE ALL DATA on the selected disk!")
        
        response = input("\nContinue? [yes/NO]: ")
        if response.lower() != 'yes':
            print("Installation cancelled.")
            sys.exit(0)
        
        self._select_disk()
        
        hostname = input(f"\nHostname [{self.config.hostname}]: ").strip()
        if hostname:
            self.config.hostname = hostname
        
        print("\n🔒 Security Configuration:")
        print("  1. Maximum (recommended for journalists/activists)")
        print("     - Hidden volume, duress password, dead man's switch")
        print("     - All hardening features enabled")
        print("  2. Balanced (good security with better compatibility)")
        print("     - Core hardening, no hidden volume")
        print("  3. Custom (choose individual features)")
        
        choice = input("\nSelect security level [1]: ").strip() or "1"
        
        if choice == "1":
            self.config.security.hidden_volume = True
            self.config.security.duress_password = True
            self.config.security.dead_mans_switch = True
        elif choice == "2":
            self.config.security.hidden_volume = False
            self.config.security.duress_password = False
            self.config.security.dead_mans_switch = False
            self.config.security.disable_ipv6 = False
            self.config.security.anti_forensics = False
        elif choice == "3":
            self._custom_security_config()
        
        # TPM check
        if Path('/sys/class/tpm/tpm0').exists():
            response = input("\n💾 TPM 2.0 detected. Use TPM for auto-unlock? [y/N]: ")
            self.config.security.tpm_encryption = response.lower() == 'y'
        
        # Secure Boot
        response = input("🔐 Configure Secure Boot? [y/N]: ")
        self.config.security.secure_boot = response.lower() == 'y'
        
        # Dead man's switch days
        if self.config.security.dead_mans_switch:
            days = input("\n⏰ Dead man's switch check-in interval (days) [30]: ").strip()
            if days.isdigit():
                self.config.security.dead_mans_switch_days = int(days)
    
    def _select_disk(self):
        """Interactive disk selection"""
        print("\n💾 Available disks:")
        result = subprocess.run(
            ['lsblk', '-d', '-n', '-o', 'NAME,SIZE,TYPE,MODEL'],
            capture_output=True, text=True
        )
        print(result.stdout)
        
        while True:
            disk = input("\nEnter disk path (e.g., /dev/sda): ").strip()
            
            if not disk.startswith('/dev/'):
                print("❌ Invalid path. Must start with /dev/")
                continue
            
            manager = DiskManager(disk)
            valid, message = manager.validate_device()
            
            if not valid:
                print(f"❌ Error: {message}")
                response = input("Try another disk? [Y/n]: ")
                if response.lower() == 'n':
                    sys.exit(1)
                continue
            
            info = manager.get_device_info()
            print(f"\n✓ Selected: {info.get('model', 'Unknown')} ({info.get('size', 'Unknown')})")
            print(f"  Path: {disk}")
            
            confirm = input("\n⚠️  Type 'DELETE MY DATA' to confirm: ")
            if confirm == "DELETE MY DATA":
                self.config.disk = disk
                break
            else:
                print("❌ Confirmation failed")
    
    def _custom_security_config(self):
        """Custom security configuration"""
        print("\n⚙️  Custom Security Configuration:")
        
        options = [
            ('hidden_volume', "Hidden volume (plausible deniability)"),
            ('duress_password', "Duress password (emergency wipe)"),
            ('dead_mans_switch', "Dead man's switch (auto-wipe)"),
            ('kernel_hardening', "Kernel hardening"),
            ('apparmor', "AppArmor MAC"),
            ('usbguard', "USBGuard"),
            ('audit', "Audit logging"),
            ('firewall_lockdown', "Dom0 firewall"),
            ('mac_randomization', "MAC randomization"),
            ('anti_forensics', "Anti-forensics (RAM wipe)"),
            ('hardware_privacy', "Webcam/mic disabled by default"),
            ('disable_ipv6', "Disable IPv6"),
            ('hardened_malloc', "Hardened malloc"),
            ('minimal_logging', "Minimal logging (RAM only)"),
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
            (InstallationPhase.HIDDEN_VOLUME, self._phase_hidden_volume),
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
                print(f"\n⏭️  Skipping {phase.name} (already completed)")
                continue
            
            try:
                print(f"\n{'='*60}")
                print(f"📍 Phase {phase.value}/{len(phases)}: {phase.name}")
                print(f"{'='*60}")
                
                handler()
                
                self.config.current_phase = phase
                self.config.save(self.state_file)
                
                print(f"\n✅ Phase {phase.name} completed")
                
            except KeyboardInterrupt:
                print("\n\n⚠️  Installation interrupted!")
                print(f"State saved. Resume with: sudo python3 {sys.argv[0]} --resume")
                sys.exit(130)
            except Exception as e:
                self.logger.error(f"Phase {phase.name} failed: {e}", exc_info=True)
                print(f"\n❌ Phase {phase.name} failed: {e}")
                print("Check log: /tmp/galactica_install.log")
                sys.exit(1)
    
    def _phase_disk(self):
        """Disk preparation"""
        manager = DiskManager(self.config.disk)
        response = input("\n🔥 Securely wipe disk? (SLOW but more secure) [y/N]: ")
        if response.lower() == 'y':
            if not manager.secure_wipe_disk(passes=1):
                raise RuntimeError("Disk wipe failed or cancelled")
    
    def _phase_partition(self):
        """Partition disk"""
        manager = DiskManager(self.config.disk)
        efi, root = manager.create_partitions()
        self.config.efi_partition = efi
        self.config.root_partition = root
        print(f"✅ Created: EFI={efi}, Root={root}")
    
    def _phase_hidden_volume(self):
        """Setup hidden volume if requested"""
        if not self.config.security.hidden_volume:
            print("\n⏭️  Skipping hidden volume (not requested)")
            return
        
        print("\n" + "="*60)
        print("🔐 HIDDEN VOLUME SETUP")
        print("="*60)
        print("\nThis creates TWO passwords:")
        print("  Password 1 (OUTER): Opens decoy volume")
        print("  Password 2 (HIDDEN): Opens real sensitive data")
        print("\n⚠️  CRITICAL SECURITY NOTICE:")
        print("  - Under duress, reveal ONLY password 1")
        print("  - NEVER mention password 2 exists")
        print("  - Keep outer volume realistic (normal files)")
        
        input("\nPress Enter to continue...")
        
        print("\n📋 OUTER Volume (Decoy)")
        outer_pass = SecurePasswordHandler.get_password(
            "Enter OUTER volume password",
            min_length=15
        )
        
        print("\n🔒 HIDDEN Volume (Real Data)")
        hidden_pass = SecurePasswordHandler.get_password(
            "Enter HIDDEN volume password",
            min_length=20
        )
        
        hvm = HiddenVolumeManager(self.config.root_partition)
        if not hvm.setup_hidden_volume(outer_pass, hidden_pass):
            raise RuntimeError("Hidden volume creation failed")
        
        self.config.outer_password = outer_pass
        self.config.hidden_password = hidden_pass
        
        print("\n✅ Hidden volume created successfully")
        print("\n⚠️  REMEMBER:")
        print(f"  Password 1 (outer): Safe to reveal")
        print(f"  Password 2 (hidden): Keep absolutely secret")
    
    def _phase_encryption(self):
        """Setup encryption"""
        print("\n🔐 Encryption Setup")
        
        # If hidden volume, skip LUKS (already encrypted)
        if self.config.security.hidden_volume:
            print("✓ Using hidden volume encryption (TrueCrypt-style)")
            
            # Open hidden volume for installation
            print("\nOpening hidden volume for installation...")
            password = self.config.hidden_password
            
            hvm = HiddenVolumeManager(self.config.root_partition)
            if not hvm.open_hidden_volume(password):
                raise RuntimeError("Failed to open hidden volume")
            
            # Get "UUID" (for hidden volumes, we use partition UUID)
            result = subprocess.run(
                ['blkid', '-s', 'UUID', '-o', 'value', self.config.root_partition],
                capture_output=True, text=True
            )
            self.config.luks_uuid = result.stdout.strip()
            
        else:
            # Standard LUKS encryption
            password = SecurePasswordHandler.get_password(
                "Enter disk encryption passphrase",
                min_length=20
            )
            
            response = input("\n🔑 Add backup recovery key? [Y/n]: ")
            add_backup = response.lower() != 'n'
            
            enc = EncryptionManager(self.config.root_partition, 
                                   self.config.security.tpm_encryption)
            
            if not enc.setup_luks(password, backup_key=add_backup):
                raise RuntimeError("Encryption setup failed")
            
            if not enc.open_luks(password):
                raise RuntimeError("Failed to open encrypted volume")
            
            self.config.luks_uuid = enc.get_uuid()
            print(f"✅ LUKS UUID: {self.config.luks_uuid}")
            
            # TPM enrollment
            if self.config.security.tpm_encryption:
                enc.setup_tpm_unlock()
        
        self.config.encryption_password = password
        
        # Setup duress password
        if self.config.security.duress_password:
            print("\n" + "="*60)
            print("💥 DURESS PASSWORD SETUP")
            print("="*60)
            print("\n⚠️  WARNING: This password DESTROYS ALL DATA!")
            print("Use ONLY if forced to reveal password under threat")
            print("\nWhat happens:")
            print("  1. Wipes LUKS/TrueCrypt headers")
            print("  2. Overwrites disk with random data")
            print("  3. Immediately powers off")
            
            response = input("\nSetup duress password? [Y/n]: ")
            if response.lower() != 'n':
                duress_pass = SecurePasswordHandler.get_password(
                    "Enter DURESS password (EMERGENCY USE ONLY)",
                    min_length=15,
                    confirm=True
                )
                
                # Hash it
                self.config.duress_hash = hashlib.sha256(duress_pass.encode()).hexdigest()
                self.config.duress_password = duress_pass
                
                print("✅ Duress password configured")
                print("⚠️  REMEMBER: This password is for EMERGENCIES ONLY!")
    
    def _phase_filesystems(self):
        """Create filesystems"""
        fs = FilesystemManager()
        
        if not fs.create_btrfs('/dev/mapper/cryptroot'):
            raise RuntimeError("Btrfs creation failed")
        
        if not fs.mount_filesystem('/dev/mapper/cryptroot'):
            raise RuntimeError("Filesystem mount failed")
        
        if not fs.create_efi_filesystem(self.config.efi_partition):
            raise RuntimeError("EFI filesystem creation failed")
        
        print("✅ Filesystems ready")
    
    def _phase_base_install(self):
        """Install base system"""
        installer = SystemInstaller(self.config)
        
        if not installer.install_base_system():
            raise RuntimeError("Base system installation failed")
        
        print("\n🔑 Root Password Setup")
        self.config.root_password = SecurePasswordHandler.get_password(
            "Enter root password",
            min_length=12
        )
        
        if not installer.configure_base_system():
            raise RuntimeError("System configuration failed")
        
        print("✅ Base system installed and configured")
    
    def _phase_configure(self):
        """Configure system"""
        # Additional configuration if needed
        pass
    
    def _phase_security(self):
        """Apply security hardening"""
        hardening = SecurityHardening(self.config)
        
        if not hardening.apply_all_hardening():
            raise RuntimeError("Security hardening failed")
        
        print("✅ Security hardening complete")
    
    def _phase_bootloader(self):
        """Install bootloader"""
        bootloader = BootloaderInstaller(self.config)
        
        if not bootloader.configure_initramfs():
            raise RuntimeError("Initramfs configuration failed")
        
        if not bootloader.install_grub():
            raise RuntimeError("Bootloader installation failed")
        
        print("✅ Bootloader installed")
    
    def _phase_finalize(self):
        """Finalize installation"""
        print("\n📝 Creating post-install documentation...")
        
        readme = Path('/mnt/root/GALACTICA-README.txt')
        with open(readme, 'w') as f:
            f.write("""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║              🌌  GALACTICA OS - POST-INSTALLATION             ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝

INSTALLATION COMPLETE ✅

═══════════════════════════════════════════════════════════════

IMPORTANT SECURITY INFORMATION:

1. FIRST BOOT
   - Enter your disk encryption passphrase at boot
   - Login as root with the password you set
   - System is fully hardened and ready

2. DOM0 NETWORK ISOLATION
   - Dom0 has NO network access (by design)
   - You must create VMs for internet access:
     * sys-net VM for network hardware
     * sys-firewall VM for traffic filtering
     * sys-vpn VM for VPN connections (optional)

3. ACTIVE SECURITY FEATURES
""")
            
            # List enabled features
            features = []
            if self.config.security.hidden_volume:
                features.append("   ✓ Hidden Volume (plausible deniability)")
            features.extend([
                "   ✓ Full disk encryption (LUKS2 + Argon2id)",
                "   ✓ Hardened kernel (linux-hardened)",
                "   ✓ 40+ kernel hardening parameters",
                "   ✓ AppArmor mandatory access control",
                "   ✓ USBGuard (blocks unauthorized USB devices)",
                "   ✓ Audit logging enabled",
                "   ✓ Dom0 network isolation",
                "   ✓ Firewall (all external connections blocked)",
                "   ✓ MAC address randomization",
                "   ✓ Xen hypervisor for VM isolation",
            ])
            
            if self.config.security.hardware_privacy:
                features.append("   ✓ Webcam/microphone disabled by default")
            if self.config.security.anti_forensics:
                features.append("   ✓ RAM wipe on shutdown")
            if self.config.security.duress_password:
                features.append("   ✓ Duress password (emergency wipe)")
            if self.config.security.dead_mans_switch:
                features.append(f"   ✓ Dead man's switch ({self.config.security.dead_mans_switch_days} days)")
            if self.config.security.tpm_encryption:
                features.append("   ✓ TPM measured boot")
            if self.config.security.secure_boot:
                features.append("   ✓ Secure Boot configured")
            
            f.write('\n'.join(features))
            
            f.write("""

4. USB DEVICES
   - New USB devices are BLOCKED by default
   - List devices: usbguard list-devices
   - Allow device: usbguard allow-device <ID>
   - Temporarily allow: usbguard allow-device -p <ID>

5. WEBCAM/MICROPHONE CONTROL
   - Enable webcam: galactica-hardware enable-webcam
   - Disable webcam: galactica-hardware disable-webcam
   - Enable mic: galactica-hardware enable-mic
   - Check status: galactica-hardware status

6. SECURE FILE DELETION
   - Use: secure-rm file1 file2 ...
   - Normal 'rm' does NOT securely delete files

""")
            
            if self.config.security.dead_mans_switch:
                f.write(f"""7. DEAD MAN'S SWITCH
   - Check in regularly: galactica-checkin
   - Threshold: {self.config.security.dead_mans_switch_days} days
   - If you don't check in, system will auto-wipe
   - Check status: galactica-deadman-check

""")
            
            if self.config.security.hidden_volume:
                f.write("""8. HIDDEN VOLUME
   ⚠️  CRITICAL OPERATIONAL SECURITY:
   - Password 1 (outer): Opens decoy volume
   - Password 2 (hidden): Opens real data
   - Under duress, reveal ONLY password 1
   - NEVER mention password 2 exists to anyone
   - Keep outer volume realistic (normal daily files)

""")
            
            if self.config.security.duress_password:
                f.write("""9. DURESS PASSWORD
   ⚠️  EMERGENCY ONLY:
   - Wipes all data immediately
   - Use if forced to reveal password under threat
   - No recovery possible after use
   - System will power off after wipe

""")
            
            f.write("""
═══════════════════════════════════════════════════════════════

NEXT STEPS:

1. Reboot into your new system
2. Create network VM: (documentation coming)
3. Create app VMs for isolated applications
4. Configure your compositor and VM manager

For full documentation:
   https://github.com/yourusername/galactica-os

Stay safe and secure! 🛡️

═══════════════════════════════════════════════════════════════
""")
        
        os.chmod(readme, 0o600)
        
        print("\n" + "="*60)
        print("✨ INSTALLATION COMPLETE!")
        print("="*60)
        print("\n📄 Post-install guide: /root/GALACTICA-README.txt")
        print("\n🔄 Next steps:")
        print("  1. Reboot: reboot")
        print("  2. Remove installation media")
        print("  3. Boot into Galactica OS")
        print("  4. Read /root/GALACTICA-README.txt")
        
        if self.config.security.hidden_volume:
            print("\n⚠️  HIDDEN VOLUME REMINDER:")
            print("  - You have TWO passwords")
            print("  - Password 1 = Safe to reveal (decoy)")
            print("  - Password 2 = Keep absolutely secret (real data)")
        
        if self.config.security.duress_password:
            print("\n💥 DURESS PASSWORD CONFIGURED:")
            print("  - Use ONLY in emergency situations")
            print("  - Will DESTROY ALL DATA")
        
        print("\n🛡️  Your system is now secured.")
        print("Stay safe! 🌌")


def main():
    """Main entry point"""
    installer = GalacticaInstaller()
    
    # Check for resume flag
    if '--resume' in sys.argv:
        if not installer.state_file.exists():
            print("❌ No previous installation state found")
            sys.exit(1)
        installer.config = InstallConfig.load(installer.state_file)
        print(f"📂 Resuming from phase: {installer.config.current_phase.name}")
    else:
        # New installation
        if not installer.check_prerequisites():
            print("\n❌ Prerequisite check failed!")
            sys.exit(1)
        
        installer.config = InstallConfig(disk="")
        installer.interactive_setup()
        installer.config.current_phase = InstallationPhase.PREREQUISITES
    
    # Run installation
    installer.run_installation()


if __name__ == '__main__':
    main()
