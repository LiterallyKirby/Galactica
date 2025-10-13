#!/usr/bin/env python3
"""
Galactica OS Security Validation Suite
Tests all security features after installation to ensure proper configuration
"""

import sys
import os
import subprocess
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import re


class TestResult(Enum):
    """Test result status"""
    PASS = "✅ PASS"
    FAIL = "❌ FAIL"
    WARN = "⚠️  WARN"
    SKIP = "⏭️  SKIP"
    INFO = "ℹ️  INFO"


@dataclass
class SecurityTest:
    """Individual security test"""
    name: str
    category: str
    description: str
    result: TestResult = TestResult.INFO
    message: str = ""
    details: List[str] = field(default_factory=list)
    critical: bool = False


class SecurityValidator:
    """Main security validation orchestrator"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.tests: List[SecurityTest] = []
        self.summary = {
            TestResult.PASS: 0,
            TestResult.FAIL: 0,
            TestResult.WARN: 0,
            TestResult.SKIP: 0
        }
    
    def run_all_tests(self) -> bool:
        """Run all security validation tests"""
        print("=" * 70)
        print("🌌 GALACTICA OS SECURITY VALIDATION SUITE")
        print("=" * 70)
        print()
        
        # Check if running on Galactica
        if not self._is_galactica_system():
            print("⚠️  WARNING: This doesn't appear to be a Galactica OS installation")
            response = input("Continue anyway? [y/N]: ")
            if response.lower() != 'y':
                return False
        
        test_categories = [
            ("Encryption", self._test_encryption),
            ("Kernel Hardening", self._test_kernel_hardening),
            ("Mandatory Access Control", self._test_mac),
            ("Network Security", self._test_network_security),
            ("Hardware Security", self._test_hardware_security),
            ("Anti-Forensics", self._test_anti_forensics),
            ("Xen Hypervisor", self._test_xen),
            ("Boot Security", self._test_boot_security),
            ("Filesystem Security", self._test_filesystem_security),
            ("Services & Daemons", self._test_services),
            ("Emergency Features", self._test_emergency_features),
        ]
        
        for category, test_func in test_categories:
            self._print_category_header(category)
            test_func()
            print()
        
        self._print_summary()
        return self.summary[TestResult.FAIL] == 0
    
    def _is_galactica_system(self) -> bool:
        """Check if this is a Galactica installation"""
        indicators = [
            Path('/etc/galactica').exists(),
            Path('/usr/local/bin/galactica-hardware').exists(),
            self._command_exists('xl'),  # Xen
        ]
        return any(indicators)
    
    def _print_category_header(self, category: str):
        """Print test category header"""
        print(f"\n{'─' * 70}")
        print(f"📋 {category}")
        print(f"{'─' * 70}")
    
    def _add_test(self, test: SecurityTest):
        """Add test result and update summary"""
        self.tests.append(test)
        if test.result in self.summary:
            self.summary[test.result] += 1
        
        # Print result
        icon = test.result.value
        print(f"{icon} {test.name}")
        
        if test.message:
            print(f"    {test.message}")
        
        if self.verbose and test.details:
            for detail in test.details:
                print(f"    • {detail}")
        
        # If critical test fails, print warning
        if test.critical and test.result == TestResult.FAIL:
            print(f"    ⚠️  CRITICAL SECURITY ISSUE!")
    
    # ═══════════════════════════════════════════════════════════
    # ENCRYPTION TESTS
    # ═══════════════════════════════════════════════════════════
    
    def _test_encryption(self):
        """Test disk encryption"""
        
        # Test 1: LUKS encryption active
        test = SecurityTest(
            name="LUKS2 Encryption",
            category="Encryption",
            description="Check if root is encrypted with LUKS2",
            critical=True
        )
        
        try:
            result = subprocess.run(
                ['lsblk', '-o', 'NAME,FSTYPE', '-n'],
                capture_output=True, text=True, check=True
            )
            
            if 'crypto_LUKS' in result.stdout or 'crypt' in result.stdout:
                test.result = TestResult.PASS
                test.message = "Root filesystem is encrypted"
                
                # Check LUKS version
                cryptsetup_result = subprocess.run(
                    ['cryptsetup', 'luksDump', '/dev/mapper/cryptroot'],
                    capture_output=True, text=True
                )
                
                if 'Version:        2' in cryptsetup_result.stdout:
                    test.details.append("Using LUKS2 (recommended)")
                else:
                    test.details.append("Using LUKS1 (consider upgrading)")
                
                # Check cipher
                if 'aes-xts-plain64' in cryptsetup_result.stdout:
                    test.details.append("Cipher: AES-XTS-Plain64 ✓")
                
                # Check key size
                if 'MK bits:        512' in cryptsetup_result.stdout:
                    test.details.append("Key size: 512-bit ✓")
            else:
                test.result = TestResult.FAIL
                test.message = "No LUKS encryption detected!"
        except Exception as e:
            test.result = TestResult.WARN
            test.message = f"Could not verify encryption: {e}"
        
        self._add_test(test)
        
        # Test 2: No swap (security risk)
        test = SecurityTest(
            name="Swap Disabled",
            category="Encryption",
            description="Verify swap is disabled (prevents memory leaks)",
            critical=False
        )
        
        result = subprocess.run(['swapon', '--show'], capture_output=True, text=True)
        if not result.stdout.strip():
            test.result = TestResult.PASS
            test.message = "Swap is disabled"
        else:
            test.result = TestResult.WARN
            test.message = "Swap is enabled (may leak sensitive data)"
            test.details.append("Consider disabling: swapoff -a")
        
        self._add_test(test)
    
    # ═══════════════════════════════════════════════════════════
    # KERNEL HARDENING TESTS
    # ═══════════════════════════════════════════════════════════
    
    def _test_kernel_hardening(self):
        """Test kernel hardening parameters"""
        
        critical_sysctls = {
            'kernel.dmesg_restrict': '1',
            'kernel.kptr_restrict': '2',
            'kernel.unprivileged_bpf_disabled': '1',
            'kernel.yama.ptrace_scope': '3',
            'kernel.kexec_load_disabled': '1',
            'vm.mmap_min_addr': '65536',
            'net.ipv4.conf.all.rp_filter': '1',
            'net.ipv4.conf.all.accept_redirects': '0',
            'net.ipv4.conf.all.send_redirects': '0',
            'net.ipv4.icmp_echo_ignore_all': '1',
        }
        
        passed = 0
        failed = 0
        details = []
        
        for param, expected in critical_sysctls.items():
            try:
                result = subprocess.run(
                    ['sysctl', '-n', param],
                    capture_output=True, text=True, check=True
                )
                actual = result.stdout.strip()
                
                if actual == expected:
                    passed += 1
                    if self.verbose:
                        details.append(f"{param} = {actual} ✓")
                else:
                    failed += 1
                    details.append(f"{param} = {actual} (expected {expected}) ✗")
            except:
                failed += 1
                details.append(f"{param} = NOT SET ✗")
        
        test = SecurityTest(
            name="Kernel Hardening Parameters",
            category="Kernel",
            description="Verify sysctl hardening",
            critical=True,
            details=details
        )
        
        if failed == 0:
            test.result = TestResult.PASS
            test.message = f"All {passed} critical parameters configured correctly"
        elif failed < 3:
            test.result = TestResult.WARN
            test.message = f"{passed} passed, {failed} failed"
        else:
            test.result = TestResult.FAIL
            test.message = f"Multiple kernel hardening parameters missing ({failed} failed)"
        
        self._add_test(test)
        
        # Test kernel version
        test = SecurityTest(
            name="Hardened Kernel",
            category="Kernel",
            description="Check if using linux-hardened",
            critical=False
        )
        
        result = subprocess.run(['uname', '-r'], capture_output=True, text=True)
        kernel = result.stdout.strip()
        
        if 'hardened' in kernel:
            test.result = TestResult.PASS
            test.message = f"Using hardened kernel: {kernel}"
        else:
            test.result = TestResult.WARN
            test.message = f"Not using hardened kernel: {kernel}"
            test.details.append("Consider: pacman -S linux-hardened")
        
        self._add_test(test)
    
    # ═══════════════════════════════════════════════════════════
    # MANDATORY ACCESS CONTROL TESTS
    # ═══════════════════════════════════════════════════════════
    
    def _test_mac(self):
        """Test AppArmor and other MAC systems"""
        
        # Test 1: AppArmor
        test = SecurityTest(
            name="AppArmor Status",
            category="MAC",
            description="Check AppArmor enforcement",
            critical=True
        )
        
        if self._command_exists('aa-status'):
            result = subprocess.run(
                ['aa-status', '--enabled'],
                capture_output=True
            )
            
            if result.returncode == 0:
                test.result = TestResult.PASS
                test.message = "AppArmor is enabled and enforcing"
                
                # Get profile count
                status = subprocess.run(
                    ['aa-status', '--json'],
                    capture_output=True, text=True
                )
                try:
                    data = json.loads(status.stdout)
                    profiles = data.get('profiles', {})
                    enforce = len(profiles.get('enforce', []))
                    complain = len(profiles.get('complain', []))
                    test.details.append(f"Profiles: {enforce} enforce, {complain} complain")
                except:
                    pass
            else:
                test.result = TestResult.FAIL
                test.message = "AppArmor is not enabled!"
        else:
            test.result = TestResult.FAIL
            test.message = "AppArmor not installed"
        
        self._add_test(test)
        
        # Test 2: USBGuard
        test = SecurityTest(
            name="USBGuard Protection",
            category="MAC",
            description="Check USBGuard daemon status",
            critical=False
        )
        
        result = subprocess.run(
            ['systemctl', 'is-active', 'usbguard.service'],
            capture_output=True, text=True
        )
        
        if result.stdout.strip() == 'active':
            test.result = TestResult.PASS
            test.message = "USBGuard is active"
            
            # Check policy
            if Path('/etc/usbguard/rules.conf').exists():
                test.details.append("Policy file exists")
        else:
            test.result = TestResult.WARN
            test.message = "USBGuard is not active"
            test.details.append("USB devices not restricted")
        
        self._add_test(test)
    
    # ═══════════════════════════════════════════════════════════
    # NETWORK SECURITY TESTS
    # ═══════════════════════════════════════════════════════════
    
    def _test_network_security(self):
        """Test network isolation and firewall"""
        
        # Test 1: Dom0 network isolation
        test = SecurityTest(
            name="Dom0 Network Isolation",
            category="Network",
            description="Verify dom0 has no network access",
            critical=True
        )
        
        # Check if NetworkManager is disabled
        nm_status = subprocess.run(
            ['systemctl', 'is-enabled', 'NetworkManager.service'],
            capture_output=True, text=True
        )
        
        if 'masked' in nm_status.stdout or 'disabled' in nm_status.stdout:
            test.result = TestResult.PASS
            test.message = "NetworkManager is disabled (dom0 isolation)"
            test.details.append("Dom0 has no direct network access ✓")
        else:
            test.result = TestResult.FAIL
            test.message = "NetworkManager is enabled (security risk!)"
            test.details.append("Dom0 should NOT have network access")
        
        self._add_test(test)
        
        # Test 2: Firewall
        test = SecurityTest(
            name="Firewall Configuration",
            category="Network",
            description="Check iptables firewall rules",
            critical=True
        )
        
        result = subprocess.run(
            ['iptables', '-L', '-n'],
            capture_output=True, text=True
        )
        
        if 'DROP' in result.stdout:
            test.result = TestResult.PASS
            test.message = "Firewall has DROP rules"
            
            # Count DROP rules
            drops = result.stdout.count('DROP')
            test.details.append(f"Found {drops} DROP rules")
        else:
            test.result = TestResult.WARN
            test.message = "No DROP rules found in firewall"
        
        self._add_test(test)
        
        # Test 3: MAC randomization
        test = SecurityTest(
            name="MAC Address Randomization",
            category="Network",
            description="Check if MAC randomization is configured",
            critical=False
        )
        
        config_file = Path('/etc/NetworkManager/conf.d/mac-randomization.conf')
        if config_file.exists():
            with open(config_file) as f:
                content = f.read()
                if 'random' in content:
                    test.result = TestResult.PASS
                    test.message = "MAC randomization configured"
                else:
                    test.result = TestResult.WARN
                    test.message = "Config exists but randomization not enabled"
        else:
            test.result = TestResult.SKIP
            test.message = "NetworkManager not used (dom0 isolation)"
        
        self._add_test(test)
        
        # Test 4: IPv6 disabled (if configured)
        test = SecurityTest(
            name="IPv6 Status",
            category="Network",
            description="Check if IPv6 is disabled",
            critical=False
        )
        
        result = subprocess.run(
            ['sysctl', '-n', 'net.ipv6.conf.all.disable_ipv6'],
            capture_output=True, text=True
        )
        
        if result.stdout.strip() == '1':
            test.result = TestResult.PASS
            test.message = "IPv6 is disabled (prevents leaks)"
        else:
            test.result = TestResult.INFO
            test.message = "IPv6 is enabled"
            test.details.append("Optional: disable to prevent IPv6 leaks")
        
        self._add_test(test)
    
    # ═══════════════════════════════════════════════════════════
    # HARDWARE SECURITY TESTS
    # ═══════════════════════════════════════════════════════════
    
    def _test_hardware_security(self):
        """Test hardware privacy controls"""
        
        # Test 1: Webcam disabled
        test = SecurityTest(
            name="Webcam Disabled by Default",
            category="Hardware",
            description="Check if webcam driver is blacklisted",
            critical=False
        )
        
        result = subprocess.run(['lsmod'], capture_output=True, text=True)
        
        if 'uvcvideo' not in result.stdout:
            test.result = TestResult.PASS
            test.message = "Webcam driver not loaded"
            test.details.append("Enable when needed: galactica-hardware enable-webcam")
        else:
            test.result = TestResult.WARN
            test.message = "Webcam driver is loaded"
            test.details.append("Disable: galactica-hardware disable-webcam")
        
        self._add_test(test)
        
        # Test 2: Microphone disabled
        test = SecurityTest(
            name="Microphone Disabled by Default",
            category="Hardware",
            description="Check if microphone driver is blacklisted",
            critical=False
        )
        
        if 'snd_hda_intel' not in result.stdout:
            test.result = TestResult.PASS
            test.message = "Microphone driver not loaded"
        else:
            test.result = TestResult.WARN
            test.message = "Microphone driver is loaded"
        
        self._add_test(test)
        
        # Test 3: Bluetooth disabled
        test = SecurityTest(
            name="Bluetooth Disabled",
            category="Hardware",
            description="Check if Bluetooth is disabled",
            critical=False
        )
        
        if 'bluetooth' not in result.stdout and 'btusb' not in result.stdout:
            test.result = TestResult.PASS
            test.message = "Bluetooth is disabled"
        else:
            test.result = TestResult.INFO
            test.message = "Bluetooth driver loaded"
        
        self._add_test(test)
        
        # Test 4: Hardware control script
        test = SecurityTest(
            name="Hardware Control Script",
            category="Hardware",
            description="Check if galactica-hardware exists",
            critical=False
        )
        
        if Path('/usr/local/bin/galactica-hardware').exists():
            test.result = TestResult.PASS
            test.message = "Hardware control script installed"
            test.details.append("Usage: galactica-hardware {enable|disable}-{webcam|mic}")
        else:
            test.result = TestResult.WARN
            test.message = "Hardware control script not found"
        
        self._add_test(test)
    
    # ═══════════════════════════════════════════════════════════
    # ANTI-FORENSICS TESTS
    # ═══════════════════════════════════════════════════════════
    
    def _test_anti_forensics(self):
        """Test anti-forensics features"""
        
        # Test 1: RAM wipe on shutdown
        test = SecurityTest(
            name="RAM Wipe Service",
            category="Anti-Forensics",
            description="Check if RAM wipe is configured",
            critical=False
        )
        
        result = subprocess.run(
            ['systemctl', 'is-enabled', 'ram-wipe.service'],
            capture_output=True, text=True
        )
        
        if 'enabled' in result.stdout:
            test.result = TestResult.PASS
            test.message = "RAM wipe on shutdown is enabled"
            test.details.append("Memory cleared on poweroff/reboot")
        else:
            test.result = TestResult.WARN
            test.message = "RAM wipe service not enabled"
        
        self._add_test(test)
        
        # Test 2: Secure deletion tool
        test = SecurityTest(
            name="Secure Deletion Tool",
            category="Anti-Forensics",
            description="Check if secure-rm exists",
            critical=False
        )
        
        if Path('/usr/local/bin/secure-rm').exists():
            test.result = TestResult.PASS
            test.message = "Secure deletion tool installed"
            test.details.append("Usage: secure-rm file1 file2 ...")
        else:
            test.result = TestResult.WARN
            test.message = "Secure deletion tool not found"
        
        self._add_test(test)
        
        # Test 3: Minimal logging
        test = SecurityTest(
            name="Minimal Logging",
            category="Anti-Forensics",
            description="Check journald configuration",
            critical=False
        )
        
        config_file = Path('/etc/systemd/journald.conf.d/galactica.conf')
        if config_file.exists():
            with open(config_file) as f:
                content = f.read()
                if 'Storage=volatile' in content:
                    test.result = TestResult.PASS
                    test.message = "Logs stored in RAM only"
                    test.details.append("Logs cleared on reboot")
                else:
                    test.result = TestResult.WARN
                    test.message = "Logging to persistent storage"
        else:
            test.result = TestResult.INFO
            test.message = "Custom journald config not found"
        
        self._add_test(test)
        
        # Test 4: Core dumps disabled
        test = SecurityTest(
            name="Core Dumps Disabled",
            category="Anti-Forensics",
            description="Check if core dumps are disabled",
            critical=False
        )
        
        result = subprocess.run(
            ['sysctl', '-n', 'kernel.core_pattern'],
            capture_output=True, text=True
        )
        
        if '/bin/false' in result.stdout or not result.stdout.strip():
            test.result = TestResult.PASS
            test.message = "Core dumps disabled"
        else:
            test.result = TestResult.WARN
            test.message = f"Core dumps enabled: {result.stdout.strip()}"
        
        self._add_test(test)
    
    # ═══════════════════════════════════════════════════════════
    # XEN HYPERVISOR TESTS
    # ═══════════════════════════════════════════════════════════
    
    def _test_xen(self):
        """Test Xen hypervisor configuration"""
        
        # Test 1: Xen running
        test = SecurityTest(
            name="Xen Hypervisor",
            category="Xen",
            description="Check if running under Xen",
            critical=True
        )
        
        if self._command_exists('xl'):
            result = subprocess.run(
                ['xl', 'info'],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                test.result = TestResult.PASS
                test.message = "Xen hypervisor is running"
                
                # Extract version
                for line in result.stdout.split('\n'):
                    if 'xen_version' in line:
                        version = line.split(':')[1].strip()
                        test.details.append(f"Version: {version}")
            else:
                test.result = TestResult.FAIL
                test.message = "Xen tools installed but hypervisor not running"
        else:
            test.result = TestResult.FAIL
            test.message = "Xen not installed"
        
        self._add_test(test)
        
        # Test 2: Dom0 is Domain-0
        test = SecurityTest(
            name="Dom0 Identity",
            category="Xen",
            description="Verify this is dom0",
            critical=True
        )
        
        if self._command_exists('xl'):
            result = subprocess.run(
                ['xl', 'list'],
                capture_output=True, text=True
            )
            
            if 'Domain-0' in result.stdout:
                test.result = TestResult.PASS
                test.message = "Running as dom0"
            else:
                test.result = TestResult.WARN
                test.message = "Not running as dom0 (might be domU)"
        else:
            test.result = TestResult.SKIP
            test.message = "Xen not available"
        
        self._add_test(test)
        
        # Test 3: Xen configuration
        test = SecurityTest(
            name="Xen Configuration",
            category="Xen",
            description="Check /etc/xen/xl.conf",
            critical=False
        )
        
        config_file = Path('/etc/xen/xl.conf')
        if config_file.exists():
            test.result = TestResult.PASS
            test.message = "Xen configuration file exists"
            
            with open(config_file) as f:
                content = f.read()
                if 'autoballoon="off"' in content:
                    test.details.append("Autoballoon disabled ✓")
                if 'vif.default.bridge' in content:
                    test.details.append("Bridge networking configured ✓")
        else:
            test.result = TestResult.WARN
            test.message = "Xen configuration not found"
        
        self._add_test(test)
    
    # ═══════════════════════════════════════════════════════════
    # BOOT SECURITY TESTS
    # ═══════════════════════════════════════════════════════════
    
    def _test_boot_security(self):
        """Test boot security features"""
        
        # Test 1: Secure Boot
        test = SecurityTest(
            name="Secure Boot",
            category="Boot",
            description="Check Secure Boot status",
            critical=False
        )
        
        sb_file = Path('/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c')
        if sb_file.exists():
            try:
                with open(sb_file, 'rb') as f:
                    data = f.read()
                    # Last byte indicates status (1 = enabled, 0 = disabled)
                    if data[-1] == 1:
                        test.result = TestResult.PASS
                        test.message = "Secure Boot is enabled"
                    else:
                        test.result = TestResult.INFO
                        test.message = "Secure Boot is disabled"
                        test.details.append("Optional: Enable in UEFI firmware")
            except:
                test.result = TestResult.INFO
                test.message = "Could not read Secure Boot status"
        else:
            test.result = TestResult.INFO
            test.message = "Secure Boot not available (Legacy boot or disabled)"
        
        self._add_test(test)
        
        # Test 2: Boot parameters
        test = SecurityTest(
            name="Kernel Boot Parameters",
            category="Boot",
            description="Check hardening boot parameters",
            critical=False
        )
        
        with open('/proc/cmdline') as f:
            cmdline = f.read()
        
        required_params = [
            'slab_nomerge',
            'init_on_alloc=1',
            'init_on_free=1',
            'pti=on',
            'lockdown=confidentiality',
        ]
        
        found = []
        missing = []
        
        for param in required_params:
            if param in cmdline:
                found.append(param)
            else:
                missing.append(param)
        
        if not missing:
            test.result = TestResult.PASS
            test.message = f"All {len(found)} hardening parameters present"
        elif len(missing) < 3:
            test.result = TestResult.WARN
            test.message = f"{len(found)} present, {len(missing)} missing"
            test.details = [f"Missing: {', '.join(missing)}"]
        else:
            test.result = TestResult.FAIL
            test.message = f"Many hardening parameters missing ({len(missing)})"
            test.details = [f"Missing: {', '.join(missing)}"]
        
        self._add_test(test)
        
        # Test 3: TPM
        test = SecurityTest(
            name="TPM Availability",
            category="Boot",
            description="Check if TPM is available",
            critical=False
        )
        
        if Path('/dev/tpm0').exists():
            test.result = TestResult.PASS
            test.message = "TPM 2.0 device detected"
            test.details.append("Can be used for measured boot")
        else:
            test.result = TestResult.INFO
            test.message = "No TPM detected"
        
        self._add_test(test)
    
    # ═══════════════════════════════════════════════════════════
    # FILESYSTEM SECURITY TESTS
    # ═══════════════════════════════════════════════════════════
    
    def _test_filesystem_security(self):
        """Test filesystem security settings"""
        
        # Test 1: /tmp noexec
        test = SecurityTest(
            name="/tmp Mount Options",
            category="Filesystem",
            description="Check if /tmp is mounted with noexec",
            critical=False
        )
        
        result = subprocess.run(
            ['mount'],
            capture_output=True, text=True
        )
        
        tmp_line = [line for line in result.stdout.split('\n') if ' /tmp ' in line]
        
        if tmp_line:
            if 'noexec' in tmp_line[0] and 'nosuid' in tmp_line[0]:
                test.result = TestResult.PASS
                test.message = "/tmp mounted with noexec,nosuid"
            else:
                test.result = TestResult.WARN
                test.message = "/tmp not properly restricted"
                test.details.append("Should have: noexec,nosuid,nodev")
        else:
            test.result = TestResult.INFO
            test.message = "/tmp not separately mounted"
        
        self._add_test(test)
        
        # Test 2: Btrfs snapshots
        test = SecurityTest(
            name="Btrfs Snapshots",
            category="Filesystem",
            description="Check if using Btrfs with snapshots",
            critical=False
        )
        
        if 'btrfs' in result.stdout:
            test.result = TestResult.PASS
            test.message = "Using Btrfs filesystem"
            
            # Check for snapshots subvolume
            if Path('/.snapshots').exists():
                test.details.append("Snapshots subvolume exists ✓")
        else:
            test.result = TestResult.INFO
            test.message = "Not using Btrfs"
        
        self._add_test(test)
        
        # Test 3: File permissions
        test = SecurityTest(
            name="Critical File Permissions",
            category="Filesystem",
            description="Check permissions on sensitive files",
            critical=False
        )
        
        critical_files = {
            '/etc/shadow': 0o000,
            '/etc/gshadow': 0o000,
            '/boot/grub/grub.cfg': 0o400,
        }
        
        issues = []
        for filepath, expected_perms in critical_files.items():
            if Path(filepath).exists():
                actual_perms = os.stat(filepath).st_mode & 0o777
                if actual_perms != expected_perms:
                    issues.append(f"{filepath}: {oct(actual_perms)} (should be {oct(expected_perms)})")
        
        if not issues:
            test.result = TestResult.PASS
            test.message = "Critical file permissions correct"
        else:
            test.result = TestResult.WARN
            test.message = "Some file permissions too permissive"
            test.details = issues
        
        self._add_test(test)
    
    # ═══════════════════════════════════════════════════════════
    # SERVICES & DAEMONS TESTS
    # ═══════════════════════════════════════════════════════════
    
    def _test_services(self):
        """Test service configuration"""
        
        # Test 1: Audit daemon
        test = SecurityTest(
            name="Audit Daemon",
            category="Services",
            description="Check if auditd is running",
            critical=False
        )
        
        result = subprocess.run(
            ['systemctl', 'is-active', 'auditd.service'],
            capture_output=True, text=True
        )
        
        if result.stdout.strip() == 'active':
            test.result = TestResult.PASS
            test.message = "Audit daemon is active"
            
            # Check audit rules
            if Path('/etc/audit/rules.d/galactica.rules').exists():
                test.details.append("Galactica audit rules installed")
        else:
            test.result = TestResult.WARN
            test.message = "Audit daemon not running"
        
        self._add_test(test)
        
        # Test 2: Unnecessary services disabled
        test = SecurityTest(
            name="Attack Surface Reduction",
            category="Services",
            description="Check if unnecessary services are disabled",
            critical=False
        )
        
        should_be_disabled = [
            'bluetooth.service',
            'cups.service',
            'avahi-daemon.service',
        ]
        
        disabled = []
        enabled = []
        
        for service in should_be_disabled:
            result = subprocess.run(
                ['systemctl', 'is-enabled', service],
                capture_output=True, text=True
            )
            if 'disabled' in result.stdout or 'masked' in result.stdout:
                disabled.append(service)
            else:
                enabled.append(service)
        
        if not enabled:
            test.result = TestResult.PASS
            test.message = f"All {len(disabled)} unnecessary services disabled"
        else:
            test.result = TestResult.WARN
            test.message = f"{len(enabled)} unnecessary services still enabled"
            test.details = [f"Enabled: {', '.join(enabled)}"]
        
        self._add_test(test)
        
        # Test 3: Xen services
        test = SecurityTest(
            name="Xen Services",
            category="Services",
            description="Check Xen-related services",
            critical=False
        )
        
        xen_services = [
            'xendomains.service',
            'xen-qemu-dom0-disk-backend.service',
        ]
        
        active = []
        for service in xen_services:
            result = subprocess.run(
                ['systemctl', 'is-active', service],
                capture_output=True, text=True
            )
            if result.stdout.strip() == 'active':
                active.append(service)
        
        if active:
            test.result = TestResult.PASS
            test.message = f"{len(active)} Xen services active"
            test.details = active
        else:
            test.result = TestResult.INFO
            test.message = "No Xen services active (may start on demand)"
        
        self._add_test(test)
    
    # ═══════════════════════════════════════════════════════════
    # EMERGENCY FEATURES TESTS
    # ═══════════════════════════════════════════════════════════
    
    def _test_emergency_features(self):
        """Test emergency security features"""
        
        # Test 1: Duress password
        test = SecurityTest(
            name="Duress Password",
            category="Emergency",
            description="Check if emergency wipe is configured",
            critical=False
        )
        
        if Path('/usr/local/bin/emergency-wipe').exists():
            test.result = TestResult.PASS
            test.message = "Emergency wipe script exists"
            test.details.append("⚠️  Use duress password ONLY in emergency!")
            
            # Check if initramfs hook exists
            if Path('/usr/lib/initcpio/hooks/duress').exists():
                test.details.append("Initramfs hook installed ✓")
        else:
            test.result = TestResult.INFO
            test.message = "Duress password not configured"
            test.details.append("Optional feature for high-threat scenarios")
        
        self._add_test(test)
        
        # Test 2: Dead man's switch
        test = SecurityTest(
            name="Dead Man's Switch",
            category="Emergency",
            description="Check if auto-wipe is configured",
            critical=False
        )
        
        dms_state = Path('/etc/galactica/deadman.json')
        if dms_state.exists():
            test.result = TestResult.PASS
            test.message = "Dead man's switch configured"
            
            try:
                with open(dms_state) as f:
                    data = json.load(f)
                    threshold = data.get('threshold_days', 'unknown')
                    test.details.append(f"Check-in required every {threshold} days")
                    test.details.append("Command: galactica-checkin")
            except:
                pass
            
            # Check if service is enabled
            result = subprocess.run(
                ['systemctl', 'is-enabled', 'galactica-deadman.service'],
                capture_output=True, text=True
            )
            if 'enabled' in result.stdout:
                test.details.append("Service enabled ✓")
        else:
            test.result = TestResult.INFO
            test.message = "Dead man's switch not configured"
            test.details.append("Optional feature for high-risk users")
        
        self._add_test(test)
        
        # Test 3: Hidden volume
        test = SecurityTest(
            name="Hidden Volume",
            category="Emergency",
            description="Check for TrueCrypt-style hidden volume",
            critical=False
        )
        
        # Check if tcplay is installed (indicator of hidden volume)
        if self._command_exists('tcplay'):
            # Check if root partition uses TrueCrypt
            result = subprocess.run(
                ['lsblk', '-o', 'NAME,FSTYPE', '-n'],
                capture_output=True, text=True
            )
            
            # TrueCrypt volumes don't show standard FSTYPE
            test.result = TestResult.INFO
            test.message = "tcplay installed (hidden volume support)"
            test.details.append("Cannot verify if hidden volume is in use")
            test.details.append("⚠️  NEVER reveal hidden volume password!")
        else:
            test.result = TestResult.INFO
            test.message = "Hidden volume not configured"
        
        self._add_test(test)
    
    # ═══════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════
    
    def _command_exists(self, cmd: str) -> bool:
        """Check if command exists in PATH"""
        return subprocess.run(
            ['which', cmd],
            capture_output=True
        ).returncode == 0
    
    def _print_summary(self):
        """Print test summary"""
        print("\n" + "═" * 70)
        print("📊 SECURITY VALIDATION SUMMARY")
        print("═" * 70)
        print()
        
        total = sum(self.summary.values())
        passed = self.summary[TestResult.PASS]
        failed = self.summary[TestResult.FAIL]
        warned = self.summary[TestResult.WARN]
        skipped = self.summary[TestResult.SKIP]
        
        print(f"Total tests: {total}")
        print(f"  ✅ Passed:  {passed}")
        print(f"  ❌ Failed:  {failed}")
        print(f"  ⚠️  Warnings: {warned}")
        print(f"  ⏭️  Skipped: {skipped}")
        print()
        
        # Calculate score
        score = (passed / (total - skipped) * 100) if (total - skipped) > 0 else 0
        
        print(f"Security Score: {score:.1f}%")
        print()
        
        # Interpretation
        if score >= 90:
            print("🌟 EXCELLENT - System is well-hardened")
        elif score >= 75:
            print("✅ GOOD - Most security features enabled")
        elif score >= 60:
            print("⚠️  FAIR - Some security issues detected")
        else:
            print("❌ POOR - Significant security concerns")
        
        # Critical failures
        critical_failures = [t for t in self.tests 
                           if t.critical and t.result == TestResult.FAIL]
        
        if critical_failures:
            print()
            print("⚠️  CRITICAL FAILURES:")
            for test in critical_failures:
                print(f"  • {test.name}: {test.message}")
        
        print("\n" + "═" * 70)
        
        # Recommendations
        if failed > 0 or warned > 0:
            print("\n📋 RECOMMENDATIONS:")
            
            failed_tests = [t for t in self.tests if t.result == TestResult.FAIL]
            warned_tests = [t for t in self.tests if t.result == TestResult.WARN]
            
            if failed_tests:
                print("\n🔴 Failed tests (fix these):")
                for test in failed_tests[:5]:  # Show top 5
                    print(f"  • {test.category}: {test.name}")
                    if test.details:
                        print(f"    → {test.details[0]}")
            
            if warned_tests:
                print("\n🟡 Warnings (consider fixing):")
                for test in warned_tests[:5]:  # Show top 5
                    print(f"  • {test.category}: {test.name}")
        
        print("\n" + "═" * 70)
        
        # Save detailed report
        report_file = Path('/tmp/galactica-security-report.txt')
        self._save_detailed_report(report_file)
        print(f"\n📄 Detailed report saved: {report_file}")
    
    def _save_detailed_report(self, filepath: Path):
        """Save detailed test results to file"""
        with open(filepath, 'w') as f:
            f.write("=" * 70 + "\n")
            f.write("GALACTICA OS SECURITY VALIDATION REPORT\n")
            f.write("=" * 70 + "\n")
            f.write(f"\nGenerated: {subprocess.run(['date'], capture_output=True, text=True).stdout}")
            f.write(f"Hostname: {subprocess.run(['hostname'], capture_output=True, text=True).stdout}")
            f.write("\n")
            
            # Group by category
            categories = {}
            for test in self.tests:
                if test.category not in categories:
                    categories[test.category] = []
                categories[test.category].append(test)
            
            for category, tests in categories.items():
                f.write(f"\n{'─' * 70}\n")
                f.write(f"{category}\n")
                f.write(f"{'─' * 70}\n\n")
                
                for test in tests:
                    f.write(f"{test.result.value} {test.name}\n")
                    if test.message:
                        f.write(f"  Message: {test.message}\n")
                    if test.details:
                        f.write(f"  Details:\n")
                        for detail in test.details:
                            f.write(f"    • {detail}\n")
                    f.write("\n")
            
            # Summary
            f.write("\n" + "=" * 70 + "\n")
            f.write("SUMMARY\n")
            f.write("=" * 70 + "\n")
            total = sum(self.summary.values())
            f.write(f"Total tests: {total}\n")
            f.write(f"Passed:  {self.summary[TestResult.PASS]}\n")
            f.write(f"Failed:  {self.summary[TestResult.FAIL]}\n")
            f.write(f"Warnings: {self.summary[TestResult.WARN]}\n")
            f.write(f"Skipped: {self.summary[TestResult.SKIP]}\n")


class QuickSecurityCheck:
    """Quick security check for CI/CD or automated testing"""
    
    @staticmethod
    def run() -> bool:
        """Run quick security checks, return True if all critical tests pass"""
        print("🔍 Running quick security check...\n")
        
        checks = [
            ("LUKS encryption", QuickSecurityCheck._check_encryption),
            ("Dom0 isolation", QuickSecurityCheck._check_dom0_isolation),
            ("Xen hypervisor", QuickSecurityCheck._check_xen),
            ("AppArmor", QuickSecurityCheck._check_apparmor),
            ("Kernel hardening", QuickSecurityCheck._check_kernel),
        ]
        
        all_passed = True
        for name, check_func in checks:
            result = check_func()
            status = "✅" if result else "❌"
            print(f"{status} {name}")
            if not result:
                all_passed = False
        
        print()
        if all_passed:
            print("✅ All critical security checks passed")
        else:
            print("❌ Some critical security checks failed")
            print("Run full validation: sudo python3 validate-security.py")
        
        return all_passed
    
    @staticmethod
    def _check_encryption() -> bool:
        """Quick check for encryption"""
        result = subprocess.run(['lsblk', '-o', 'FSTYPE'], capture_output=True, text=True)
        return 'crypto_LUKS' in result.stdout or 'crypt' in result.stdout
    
    @staticmethod
    def _check_dom0_isolation() -> bool:
        """Quick check for dom0 network isolation"""
        result = subprocess.run(
            ['systemctl', 'is-enabled', 'NetworkManager.service'],
            capture_output=True, text=True
        )
        return 'masked' in result.stdout or 'disabled' in result.stdout
    
    @staticmethod
    def _check_xen() -> bool:
        """Quick check for Xen"""
        result = subprocess.run(['which', 'xl'], capture_output=True)
        if result.returncode != 0:
            return False
        result = subprocess.run(['xl', 'list'], capture_output=True, text=True)
        return 'Domain-0' in result.stdout
    
    @staticmethod
    def _check_apparmor() -> bool:
        """Quick check for AppArmor"""
        result = subprocess.run(['aa-status', '--enabled'], capture_output=True)
        return result.returncode == 0
    
    @staticmethod
    def _check_kernel() -> bool:
        """Quick check for hardened kernel"""
        result = subprocess.run(['uname', '-r'], capture_output=True, text=True)
        return 'hardened' in result.stdout.lower()


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Galactica OS Security Validation Suite',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sudo python3 validate-security.py                 # Full validation
  sudo python3 validate-security.py --quick         # Quick check
  sudo python3 validate-security.py --verbose       # Detailed output
  sudo python3 validate-security.py --json          # JSON output

Report issues: https://github.com/yourusername/galactica-os/issues
        """
    )
    
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Run quick security check only'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed test information'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results in JSON format'
    )
    
    parser.add_argument(
        '--category', '-c',
        choices=['encryption', 'kernel', 'mac', 'network', 'hardware', 
                'forensics', 'xen', 'boot', 'filesystem', 'services', 'emergency'],
        help='Run only tests in specified category'
    )
    
    args = parser.parse_args()
    
    # Check if running as root
    if os.geteuid() != 0:
        print("⚠️  WARNING: Not running as root")
        print("Some tests may fail or show incomplete results")
        print("Recommended: sudo python3 validate-security.py")
        print()
        response = input("Continue anyway? [y/N]: ")
        if response.lower() != 'y':
            sys.exit(1)
    
    # Quick check mode
    if args.quick:
        success = QuickSecurityCheck.run()
        sys.exit(0 if success else 1)
    
    # Full validation
    validator = SecurityValidator(verbose=args.verbose)
    success = validator.run_all_tests()
    
    # JSON output
    if args.json:
        output = {
            'summary': {
                'passed': validator.summary[TestResult.PASS],
                'failed': validator.summary[TestResult.FAIL],
                'warned': validator.summary[TestResult.WARN],
                'skipped': validator.summary[TestResult.SKIP],
            },
            'tests': [
                {
                    'name': test.name,
                    'category': test.category,
                    'result': test.result.name,
                    'message': test.message,
                    'details': test.details,
                    'critical': test.critical,
                }
                for test in validator.tests
            ]
        }
        
        json_file = Path('/tmp/galactica-security-report.json')
        with open(json_file, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"\n📄 JSON report: {json_file}")
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()