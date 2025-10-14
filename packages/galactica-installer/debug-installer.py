#!/usr/bin/env python3
"""
Galactica OS Installer Debugger
Validates environment and provides detailed diagnostics
"""

import sys
import os
import subprocess
import json
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import traceback


class Color:
    """ANSI color codes"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class InstallerDebugger:
    """Debug Galactica installer issues"""
    
    def __init__(self):
        self.log_file = Path('/tmp/galactica_install.log')
        self.state_file = Path('/tmp/galactica_install_state.json')
        self.issues: List[Dict] = []
        self.warnings: List[Dict] = []
    
    def print_header(self, text: str):
        """Print colored header"""
        print(f"\n{Color.BOLD}{Color.CYAN}{'='*70}{Color.RESET}")
        print(f"{Color.BOLD}{Color.CYAN}{text}{Color.RESET}")
        print(f"{Color.BOLD}{Color.CYAN}{'='*70}{Color.RESET}\n")
    
    def print_section(self, text: str):
        """Print section header"""
        print(f"\n{Color.BOLD}{Color.BLUE}▶ {text}{Color.RESET}")
        print(f"{Color.BLUE}{'─'*70}{Color.RESET}")
    
    def print_success(self, text: str):
        """Print success message"""
        print(f"{Color.GREEN}✓{Color.RESET} {text}")
    
    def print_error(self, text: str):
        """Print error message"""
        print(f"{Color.RED}✗{Color.RESET} {text}")
        self.issues.append({'type': 'error', 'message': text})
    
    def print_warning(self, text: str):
        """Print warning message"""
        print(f"{Color.YELLOW}⚠{Color.RESET} {text}")
        self.warnings.append({'type': 'warning', 'message': text})
    
    def print_info(self, text: str):
        """Print info message"""
        print(f"{Color.CYAN}ℹ{Color.RESET} {text}")
    
    def run_full_diagnostic(self) -> bool:
        """Run complete diagnostic suite"""
        self.print_header("🔍 GALACTICA INSTALLER DIAGNOSTIC TOOL")
        
        checks = [
            ("System Requirements", self.check_system_requirements),
            ("Required Commands", self.check_commands),
            ("Disk Availability", self.check_disks),
            ("Previous Installation State", self.check_state),
            ("Log File Analysis", self.analyze_logs),
            ("Known Issues Check", self.check_known_issues),
        ]
        
        all_passed = True
        for section, check_func in checks:
            self.print_section(section)
            try:
                if not check_func():
                    all_passed = False
            except Exception as e:
                self.print_error(f"Check failed with exception: {e}")
                traceback.print_exc()
                all_passed = False
        
        self.print_summary()
        return all_passed
    
    def check_system_requirements(self) -> bool:
        """Check system meets requirements"""
        all_good = True
        
        # Root check
        if os.geteuid() == 0:
            self.print_success("Running as root")
        else:
            self.print_error("Not running as root (required for installation)")
            all_good = False
        
        # UEFI check
        if Path('/sys/firmware/efi').exists():
            self.print_success("UEFI firmware detected")
        else:
            self.print_error("UEFI not detected (Legacy BIOS not supported)")
            all_good = False
        
        # RAM check
        try:
            with open('/proc/meminfo') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        mem_kb = int(line.split()[1])
                        mem_gb = mem_kb / 1024 / 1024
                        if mem_gb >= 2:
                            self.print_success(f"Sufficient RAM: {mem_gb:.1f}GB")
                        else:
                            self.print_error(f"Insufficient RAM: {mem_gb:.1f}GB (need 2GB+)")
                            all_good = False
                        break
        except Exception as e:
            self.print_warning(f"Could not check RAM: {e}")
        
        # Internet check
        try:
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '3', '1.1.1.1'],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                self.print_success("Internet connection available")
            else:
                self.print_warning("No internet (may fail downloading packages)")
        except Exception as e:
            self.print_warning(f"Could not check internet: {e}")
        
        # Arch Linux check
        if Path('/etc/arch-release').exists():
            self.print_success("Running on Arch Linux")
        else:
            self.print_warning("Not Arch Linux (installer designed for Arch)")
        
        return all_good
    
    def check_commands(self) -> bool:
        """Check required commands exist"""
        required = {
            'critical': [
                'pacstrap', 'arch-chroot', 'genfstab',  # Arch tools
                'cryptsetup', 'lsblk', 'blkid',  # Disk tools
                'parted', 'mkfs.btrfs', 'mkfs.fat',  # Filesystem tools
                'grub-install', 'grub-mkconfig',  # Bootloader
            ],
            'important': [
                'xl',  # Xen (may not be installed yet)
                'aa-status',  # AppArmor (may not be installed yet)
                'usbguard',  # USBGuard (may not be installed yet)
            ],
            'optional': [
                'tcplay',  # Hidden volumes
                'sbctl',  # Secure Boot
                'tpm2_',  # TPM tools
            ]
        }
        
        all_good = True
        
        for category, commands in required.items():
            missing = []
            for cmd in commands:
                result = subprocess.run(['which', cmd], capture_output=True)
                if result.returncode != 0:
                    missing.append(cmd)
            
            if missing:
                if category == 'critical':
                    self.print_error(f"Missing critical commands: {', '.join(missing)}")
                    all_good = False
                elif category == 'important':
                    self.print_warning(f"Missing important commands (will be installed): {', '.join(missing)}")
                else:
                    self.print_info(f"Missing optional commands: {', '.join(missing)}")
            else:
                self.print_success(f"All {category} commands available")
        
        # Check if pacstrap is from arch-install-scripts
        if all_good:
            try:
                result = subprocess.run(
                    ['pacman', '-Qi', 'arch-install-scripts'],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    self.print_success("arch-install-scripts package installed")
                else:
                    self.print_error("arch-install-scripts not installed")
                    self.print_info("Install: pacman -S arch-install-scripts")
                    all_good = False
            except Exception as e:
                self.print_warning(f"Could not verify arch-install-scripts: {e}")
        
        return all_good
    
    def check_disks(self) -> bool:
        """Check available disks"""
        try:
            result = subprocess.run(
                ['lsblk', '-d', '-n', '-o', 'NAME,SIZE,TYPE,MODEL'],
                capture_output=True,
                text=True,
                check=True
            )
            
            print("\nAvailable disks:")
            disks = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split()
                    if parts:
                        disk_name = parts[0]
                        disks.append(disk_name)
                        print(f"  /dev/{line}")
            
            if disks:
                self.print_success(f"Found {len(disks)} disk(s)")
                
                # Check for mounted partitions
                mount_result = subprocess.run(
                    ['mount'],
                    capture_output=True,
                    text=True
                )
                
                mounted = []
                for disk in disks:
                    if f"/dev/{disk}" in mount_result.stdout:
                        mounted.append(disk)
                
                if mounted:
                    self.print_warning(f"Some disks have mounted partitions: {', '.join(mounted)}")
                    self.print_info("Unmount before installation to avoid issues")
            else:
                self.print_error("No disks detected")
                return False
            
            return True
            
        except Exception as e:
            self.print_error(f"Failed to check disks: {e}")
            return False
    
    def check_state(self) -> bool:
        """Check previous installation state"""
        if not self.state_file.exists():
            self.print_info("No previous installation state found (fresh install)")
            return True
        
        try:
            with open(self.state_file) as f:
                state = json.load(f)
            
            self.print_warning("Previous installation state found!")
            self.print_info(f"Phase: {state.get('current_phase', 'unknown')}")
            self.print_info(f"Disk: {state.get('disk', 'unknown')}")
            self.print_info(f"Hostname: {state.get('hostname', 'unknown')}")
            
            # Check if disk still exists
            disk = state.get('disk')
            if disk and Path(disk).exists():
                self.print_success(f"Disk {disk} still exists")
            elif disk:
                self.print_error(f"Disk {disk} no longer exists!")
                return False
            
            # Check if partitions exist
            root_part = state.get('root_partition')
            if root_part and Path(root_part).exists():
                self.print_success(f"Root partition {root_part} exists")
            elif root_part:
                self.print_error(f"Root partition {root_part} missing!")
                return False
            
            # Check if /mnt has any mounts
            mount_result = subprocess.run(
                ['mount'],
                capture_output=True,
                text=True
            )
            
            if '/mnt' in mount_result.stdout:
                self.print_warning("/mnt has active mounts from previous installation")
                self.print_info("May need to unmount: umount -R /mnt")
            
            print("\n" + Color.YELLOW + "Resume options:" + Color.RESET)
            print("  1. Resume installation: python3 installer.py --resume")
            print("  2. Start fresh: rm /tmp/galactica_install_state.json")
            
            return True
            
        except Exception as e:
            self.print_error(f"Failed to parse state file: {e}")
            self.print_info("Consider removing corrupted state: rm /tmp/galactica_install_state.json")
            return False
    
    def analyze_logs(self) -> bool:
        """Analyze installation logs for errors"""
        if not self.log_file.exists():
            self.print_info("No log file found (installation not started)")
            return True
        
        try:
            with open(self.log_file) as f:
                log_content = f.read()
            
            # Count log levels
            errors = log_content.count('ERROR')
            warnings = log_content.count('WARNING')
            
            if errors > 0:
                self.print_error(f"Found {errors} errors in log")
                
                # Extract last few errors
                lines = log_content.split('\n')
                error_lines = [l for l in lines if 'ERROR' in l][-5:]
                
                if error_lines:
                    print(f"\n{Color.RED}Recent errors:{Color.RESET}")
                    for line in error_lines:
                        print(f"  {line}")
            else:
                self.print_success("No errors in log")
            
            if warnings > 0:
                self.print_warning(f"Found {warnings} warnings in log")
            
            # Check for specific error patterns
            error_patterns = {
                'Permission denied': 'Not running as root or file permissions issue',
                'No space left': 'Disk full',
                'Failed to mount': 'Filesystem or partition issue',
                'cryptsetup.*failed': 'Encryption setup failed',
                'pacstrap.*failed': 'Package installation failed (check internet)',
                'grub-install.*failed': 'Bootloader installation failed',
            }
            
            for pattern, explanation in error_patterns.items():
                if pattern.lower() in log_content.lower():
                    self.print_warning(f"Detected: {explanation}")
            
            return errors == 0
            
        except Exception as e:
            self.print_warning(f"Could not analyze logs: {e}")
            return True
    
    def check_known_issues(self) -> bool:
        """Check for known issues"""
        self.print_info("Checking for known installer bugs...")
        
        known_issues = [
            {
                'id': 'BTRFS-001',
                'title': 'Btrfs subvolume path bug',
                'description': 'Line 507: subvolume creation uses wrong path',
                'severity': 'HIGH',
                'workaround': 'Will be fixed in installer.py update',
            },
            {
                'id': 'RESUME-001',
                'title': 'Hidden volume resume not implemented',
                'description': 'Cannot resume after hidden volume setup interruption',
                'severity': 'MEDIUM',
                'workaround': 'Start fresh if interrupted during hidden volume phase',
            },
            {
                'id': 'DURESS-001',
                'title': 'Duress password hook incomplete',
                'description': 'Initramfs hook created but password check not implemented',
                'severity': 'MEDIUM',
                'workaround': 'Feature not fully functional in current version',
            },
            {
                'id': 'NVME-001',
                'title': 'NVMe partition detection',
                'description': 'May fail to detect p1/p2 vs 1/2 partition naming',
                'severity': 'LOW',
                'workaround': 'Manually verify partition names if installation fails',
            },
        ]
        
        print(f"\n{Color.YELLOW}Known issues in current version:{Color.RESET}")
        for issue in known_issues:
            severity_color = Color.RED if issue['severity'] == 'HIGH' else Color.YELLOW
            print(f"\n  [{severity_color}{issue['severity']}{Color.RESET}] {issue['id']}: {issue['title']}")
            print(f"    {issue['description']}")
            print(f"    Workaround: {issue['workaround']}")
        
        return True
    
    def print_summary(self):
        """Print diagnostic summary"""
        self.print_header("📊 DIAGNOSTIC SUMMARY")
        
        if not self.issues and not self.warnings:
            print(f"{Color.GREEN}{Color.BOLD}✓ All checks passed!{Color.RESET}")
            print(f"\n{Color.GREEN}System is ready for Galactica OS installation.{Color.RESET}")
            print(f"\n{Color.CYAN}Next steps:{Color.RESET}")
            print(f"  1. Review installation guide")
            print(f"  2. Backup any important data")
            print(f"  3. Run: sudo python3 installer.py")
        else:
            if self.issues:
                print(f"\n{Color.RED}{Color.BOLD}✗ {len(self.issues)} critical issue(s) found{Color.RESET}")
                for i, issue in enumerate(self.issues, 1):
                    print(f"  {i}. {issue['message']}")
            
            if self.warnings:
                print(f"\n{Color.YELLOW}{Color.BOLD}⚠ {len(self.warnings)} warning(s){Color.RESET}")
                for i, warning in enumerate(self.warnings, 1):
                    print(f"  {i}. {warning['message']}")
            
            if self.issues:
                print(f"\n{Color.RED}Fix critical issues before running installer.{Color.RESET}")
            else:
                print(f"\n{Color.YELLOW}You may proceed, but address warnings if possible.{Color.RESET}")
        
        print(f"\n{Color.CYAN}{'─'*70}{Color.RESET}")
        print(f"{Color.CYAN}Log file: {self.log_file}{Color.RESET}")
        if self.state_file.exists():
            print(f"{Color.CYAN}State file: {self.state_file}{Color.RESET}")
    
    def check_specific_phase(self, phase: str) -> bool:
        """Debug specific installation phase"""
        phase_checks = {
            'disk': self.debug_disk_phase,
            'partition': self.debug_partition_phase,
            'encryption': self.debug_encryption_phase,
            'filesystem': self.debug_filesystem_phase,
            'bootloader': self.debug_bootloader_phase,
        }
        
        if phase not in phase_checks:
            print(f"{Color.RED}Unknown phase: {phase}{Color.RESET}")
            print(f"Available: {', '.join(phase_checks.keys())}")
            return False
        
        self.print_header(f"Debugging Phase: {phase.upper()}")
        return phase_checks[phase]()
    
    def debug_disk_phase(self) -> bool:
        """Debug disk selection phase"""
        self.print_info("Checking disk phase...")
        
        if not self.state_file.exists():
            self.print_warning("No state file - disk not selected yet")
            return True
        
        with open(self.state_file) as f:
            state = json.load(f)
        
        disk = state.get('disk')
        if not disk:
            self.print_error("Disk not set in state")
            return False
        
        if not Path(disk).exists():
            self.print_error(f"Disk {disk} does not exist")
            return False
        
        self.print_success(f"Disk selected: {disk}")
        
        # Check if disk is in use
        result = subprocess.run(['lsblk', disk], capture_output=True, text=True)
        print(f"\n{result.stdout}")
        
        return True
    
    def debug_partition_phase(self) -> bool:
        """Debug partitioning phase"""
        self.print_info("Checking partition phase...")
        
        with open(self.state_file) as f:
            state = json.load(f)
        
        efi_part = state.get('efi_partition')
        root_part = state.get('root_partition')
        
        if not efi_part or not root_part:
            self.print_warning("Partitions not created yet")
            return True
        
        # Check EFI partition
        if Path(efi_part).exists():
            self.print_success(f"EFI partition exists: {efi_part}")
            
            result = subprocess.run(
                ['blkid', '-s', 'TYPE', '-o', 'value', efi_part],
                capture_output=True,
                text=True
            )
            if 'vfat' in result.stdout:
                self.print_success("EFI partition is FAT32")
            else:
                self.print_warning(f"EFI partition type: {result.stdout.strip()}")
        else:
            self.print_error(f"EFI partition missing: {efi_part}")
            return False
        
        # Check root partition
        if Path(root_part).exists():
            self.print_success(f"Root partition exists: {root_part}")
        else:
            self.print_error(f"Root partition missing: {root_part}")
            return False
        
        return True
    
    def debug_encryption_phase(self) -> bool:
        """Debug encryption phase"""
        self.print_info("Checking encryption phase...")
        
        with open(self.state_file) as f:
            state = json.load(f)
        
        root_part = state.get('root_partition')
        if not root_part:
            self.print_warning("Root partition not set")
            return True
        
        # Check if LUKS
        result = subprocess.run(
            ['cryptsetup', 'isLuks', root_part],
            capture_output=True
        )
        
        if result.returncode == 0:
            self.print_success("LUKS encryption detected")
            
            # Get LUKS info
            result = subprocess.run(
                ['cryptsetup', 'luksDump', root_part],
                capture_output=True,
                text=True
            )
            print(f"\n{Color.CYAN}LUKS Information:{Color.RESET}")
            for line in result.stdout.split('\n')[:10]:
                print(f"  {line}")
        else:
            self.print_info("No LUKS encryption (may be hidden volume)")
            
            # Check for tcplay
            result = subprocess.run(['which', 'tcplay'], capture_output=True)
            if result.returncode == 0:
                self.print_info("tcplay available (hidden volume support)")
            else:
                self.print_warning("Neither LUKS nor tcplay detected")
        
        # Check if cryptroot mapper exists
        if Path('/dev/mapper/cryptroot').exists():
            self.print_success("Encrypted volume is open (/dev/mapper/cryptroot)")
        else:
            self.print_info("Encrypted volume not currently open")
        
        return True
    
    def debug_filesystem_phase(self) -> bool:
        """Debug filesystem phase"""
        self.print_info("Checking filesystem phase...")
        
        # Check /mnt
        result = subprocess.run(['mount'], capture_output=True, text=True)
        
        if '/mnt' in result.stdout:
            self.print_success("/mnt is mounted")
            
            # Show mount points
            mounts = [l for l in result.stdout.split('\n') if '/mnt' in l]
            print(f"\n{Color.CYAN}Mounts:{Color.RESET}")
            for mount in mounts:
                print(f"  {mount}")
            
            # Check if btrfs
            if 'btrfs' in result.stdout:
                self.print_success("Using Btrfs filesystem")
                
                # Check subvolumes
                result = subprocess.run(
                    ['btrfs', 'subvolume', 'list', '/mnt'],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    print(f"\n{Color.CYAN}Subvolumes:{Color.RESET}")
                    print(result.stdout)
        else:
            self.print_info("/mnt not mounted (filesystem not created/mounted yet)")
        
        return True
    
    def debug_bootloader_phase(self) -> bool:
        """Debug bootloader phase"""
        self.print_info("Checking bootloader phase...")
        
        # Check if GRUB is installed
        grub_dir = Path('/mnt/boot/grub')
        if grub_dir.exists():
            self.print_success("GRUB directory exists")
            
            grub_cfg = Path('/mnt/boot/grub/grub.cfg')
            if grub_cfg.exists():
                self.print_success("GRUB config exists")
                
                with open(grub_cfg) as f:
                    content = f.read()
                
                if 'cryptdevice' in content:
                    self.print_success("GRUB configured for encryption")
                else:
                    self.print_warning("No cryptdevice in GRUB config")
            else:
                self.print_warning("GRUB config not generated yet")
        else:
            self.print_info("GRUB not installed yet")
        
        # Check EFI boot entry
        try:
            result = subprocess.run(
                ['efibootmgr'],
                capture_output=True,
                text=True
            )
            if 'GALACTICA' in result.stdout:
                self.print_success("GALACTICA EFI boot entry found")
            else:
                self.print_info("No GALACTICA boot entry (may not be installed yet)")
        except:
            self.print_info("Could not check EFI boot entries")
        
        return True


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Debug Galactica OS installer',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--phase',
        choices=['disk', 'partition', 'encryption', 'filesystem', 'bootloader'],
        help='Debug specific installation phase'
    )
    
    parser.add_argument(
        '--logs',
        action='store_true',
        help='Show recent log entries'
    )
    
    parser.add_argument(
        '--state',
        action='store_true',
        help='Show current installation state'
    )
    
    args = parser.parse_args()
    
    debugger = InstallerDebugger()
    
    # Quick options
    if args.logs:
        debugger.print_header("📄 INSTALLATION LOGS")
        if debugger.log_file.exists():
            with open(debugger.log_file) as f:
                lines = f.readlines()
                print(''.join(lines[-50:]))  # Last 50 lines
        else:
            print("No log file found")
        return
    
    if args.state:
        debugger.print_header("💾 INSTALLATION STATE")
        if debugger.state_file.exists():
            with open(debugger.state_file) as f:
                state = json.load(f)
                print(json.dumps(state, indent=2))
        else:
            print("No state file found")
        return
    
    # Phase-specific debugging
    if args.phase:
        success = debugger.check_specific_phase(args.phase)
        sys.exit(0 if success else 1)
    
    # Full diagnostic
    success = debugger.run_full_diagnostic()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()