#!/usr/bin/env python3
"""
Simple Idempotent Upload Script for Epstein Browser
One script to rule them all - no bullshit, just works.
"""

import os
import sys
import hashlib
import subprocess
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleUploader:
    """Simple, no-nonsense file uploader."""
    
    def __init__(self, local_dir: str, remote_host: str, remote_user: str, remote_dir: str, ssh_port: int = 22):
        self.local_dir = Path(local_dir)
        self.remote_host = remote_host
        self.remote_user = remote_user
        self.remote_dir = remote_dir
        self.ssh_port = ssh_port
        
        # SSH key paths
        self.ssh_dir = Path(__file__).parent / ".ssh"
        self.ssh_dir.mkdir(mode=0o700, exist_ok=True)
        self.private_key = self.ssh_dir / "upload_key"
        self.public_key = self.ssh_dir / "upload_key.pub"
        
        # Exclude these file types
        self.excluded_extensions = {'.mp4', '.MP4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.tmp', '.log'}
        
        # Stats
        self.stats = {'scanned': 0, 'uploaded': 0, 'skipped': 0, 'excluded': 0, 'errors': 0}
    
    def generate_ssh_key(self, force: bool = False) -> bool:
        """Generate SSH key pair."""
        if not force and self.private_key.exists() and self.public_key.exists():
            logger.info("SSH keys already exist")
            return True
        
        try:
            if force:
                for key in [self.private_key, self.public_key]:
                    if key.exists():
                        key.unlink()
            
            cmd = [
                "ssh-keygen", "-t", "ed25519", "-f", str(self.private_key),
                "-N", "", "-C", f"epstein-upload-{os.getenv('COMPUTERNAME', 'unknown')}"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            os.chmod(self.private_key, 0o600)
            os.chmod(self.public_key, 0o644)
            
            logger.info("SSH key pair generated")
            return True
        except Exception as e:
            logger.error(f"Failed to generate SSH keys: {e}")
            return False
    
    def get_public_key(self) -> Optional[str]:
        """Get public key content."""
        try:
            return self.public_key.read_text().strip() if self.public_key.exists() else None
        except:
            return None
    
    def copy_key_to_server(self) -> bool:
        """Try to copy the public key to the server using ssh-copy-id."""
        try:
            cmd = [
                "ssh-copy-id", "-i", str(self.public_key), "-p", str(self.ssh_port),
                f"{self.remote_user}@{self.remote_host}"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                logger.info("SSH key copied to server successfully")
                return True
            else:
                logger.warning(f"ssh-copy-id failed: {result.stderr}")
                return False
        except Exception as e:
            logger.warning(f"ssh-copy-id not available: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test SSH connection."""
        try:
            cmd = [
                "ssh", "-i", str(self.private_key), "-p", str(self.ssh_port),
                "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=accept-new",
                "-o", "UserKnownHostsFile=/dev/null", "-o", "PasswordAuthentication=no",
                "-o", "LogLevel=ERROR",  # Suppress warnings
                f"{self.remote_user}@{self.remote_host}", "echo 'OK'"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                logger.error(f"SSH connection failed: {result.stderr}")
            return result.returncode == 0
        except Exception as e:
            logger.error(f"SSH connection error: {e}")
            return False
    
    def calculate_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file."""
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except:
            return ""
    
    def should_exclude(self, file_path: Path) -> bool:
        """Check if file should be excluded."""
        if file_path.suffix.lower() in self.excluded_extensions:
            return True
        if file_path.name.lower() in {'.ds_store', 'thumbs.db', 'desktop.ini'}:
            return True
        if file_path.stat().st_size > 1024 * 1024 * 1024:  # 1GB limit
            return True
        return False
    
    def scan_local_files(self) -> Dict[str, Dict]:
        """Scan local files and build manifest."""
        logger.info(f"Scanning {self.local_dir}")
        manifest = {}
        
        for file_path in self.local_dir.rglob('*'):
            if file_path.is_file():
                self.stats['scanned'] += 1
                
                if self.should_exclude(file_path):
                    self.stats['excluded'] += 1
                    continue
                
                try:
                    rel_path = str(file_path.relative_to(self.local_dir)).replace('\\', '/')
                    file_hash = self.calculate_hash(file_path)
                    
                    if file_hash:
                        manifest[rel_path] = {
                            'path': rel_path,
                            'size': file_path.stat().st_size,
                            'hash': file_hash,
                            'local_path': str(file_path)
                        }
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
                    self.stats['errors'] += 1
        
        logger.info(f"Found {len(manifest)} files to process")
        return manifest
    
    def get_remote_files(self) -> Dict[str, Dict]:
        """Get remote file manifest."""
        logger.info("Getting remote file list...")
        
        script = f"""
        cd "{self.remote_dir}" 2>/dev/null || exit 1
        find . -type f -printf '%P\\t%s\\t%T@\\n' | while IFS=$'\\t' read -r relpath size mtime; do
            if [ -n "$relpath" ]; then
                hash=$(sha256sum "$relpath" 2>/dev/null | cut -d' ' -f1)
                if [ -n "$hash" ]; then
                    echo "{{\\"path\\": \\"$relpath\\", \\"size\\": $size, \\"hash\\": \\"$hash\\"}}"
                fi
            fi
        done
        """
        
        try:
            cmd = [
                "ssh", "-i", str(self.private_key), "-p", str(self.ssh_port),
                "-o", "StrictHostKeyChecking=accept-new", "-o", "UserKnownHostsFile=/dev/null",
                "-o", "LogLevel=ERROR",  # Suppress warnings
                f"{self.remote_user}@{self.remote_host}", script
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                logger.error(f"Failed to get remote files: {result.stderr}")
                logger.error(f"SSH command output: {result.stdout}")
                logger.info("This might mean the remote directory doesn't exist yet, or there's a connection issue.")
                logger.info("All local files will be uploaded on first run.")
                return {}
            
            manifest = {}
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    try:
                        file_info = json.loads(line)
                        manifest[file_info['path']] = file_info
                    except:
                        continue
            
            logger.info(f"Found {len(manifest)} remote files")
            return manifest
        except Exception as e:
            logger.error(f"Error getting remote files: {e}")
            return {}
    
    def upload_file(self, local_path: Path, remote_rel_path: str) -> bool:
        """Upload a single file."""
        try:
            # Create remote directory
            remote_dir = f"{self.remote_user}@{self.remote_host}:{self.remote_dir}/{Path(remote_rel_path).parent}"
            mkdir_cmd = [
                "ssh", "-i", str(self.private_key), "-p", str(self.ssh_port),
                "-o", "StrictHostKeyChecking=accept-new", "-o", "UserKnownHostsFile=/dev/null",
                "-o", "LogLevel=ERROR",  # Suppress warnings
                f"{self.remote_user}@{self.remote_host}",
                f"mkdir -p '{self.remote_dir}/{Path(remote_rel_path).parent}'"
            ]
            subprocess.run(mkdir_cmd, check=True, capture_output=True)
            
            # Upload file
            remote_path = f"{self.remote_user}@{self.remote_host}:{self.remote_dir}/{remote_rel_path}"
            scp_cmd = [
                "scp", "-i", str(self.private_key), "-P", str(self.ssh_port),
                "-o", "StrictHostKeyChecking=accept-new", "-o", "UserKnownHostsFile=/dev/null",
                "-o", "LogLevel=ERROR",  # Suppress warnings
                str(local_path), remote_path
            ]
            
            result = subprocess.run(scp_cmd, capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Upload failed for {remote_rel_path}: {e}")
            return False
    
    def sync(self, dry_run: bool = False) -> bool:
        """Main sync function."""
        logger.info("=" * 50)
        logger.info("Epstein Browser Data Sync")
        logger.info("=" * 50)
        
        # Generate SSH keys if needed
        if not self.private_key.exists():
            logger.info("Generating SSH keys...")
            if not self.generate_ssh_key():
                return False
            
            public_key = self.get_public_key()
            if public_key:
                logger.info(f"Add this public key to your server:")
                logger.info(f"{public_key}")
                logger.info(f"Then run: ssh-copy-id -i {self.public_key} {self.remote_user}@{self.remote_host}")
                return False
        
        # Test connection
        if not self.test_connection():
            logger.error("SSH connection failed. Check your keys and server access.")
            return False
        
        # Scan files
        local_files = self.scan_local_files()
        if not local_files:
            logger.error("No local files found")
            return False
        
        remote_files = self.get_remote_files()
        
        # Find files to upload
        files_to_upload = []
        if not remote_files:
            logger.info("No remote files found - this appears to be the first upload")
            logger.info("All local files will be uploaded")
            files_to_upload = list(local_files.keys())
            # Don't set stats['uploaded'] here - it will be set in the summary
        else:
            for rel_path, local_info in local_files.items():
                if rel_path not in remote_files:
                    files_to_upload.append(rel_path)
                else:
                    remote_info = remote_files[rel_path]
                    if (local_info['size'] != remote_info['size'] or 
                        local_info['hash'] != remote_info['hash']):
                        files_to_upload.append(rel_path)
                    else:
                        self.stats['skipped'] += 1
        
        # Print summary
        logger.info(f"Files scanned: {self.stats['scanned']}")
        logger.info(f"Files excluded: {self.stats['excluded']}")
        logger.info(f"Files to upload: {len(files_to_upload)}")
        logger.info(f"Files skipped: {self.stats['skipped']}")
        
        if dry_run:
            logger.info("DRY RUN - No files uploaded")
            if files_to_upload:
                logger.info("Files that would be uploaded:")
                for i, file_path in enumerate(files_to_upload[:10], 1):
                    logger.info(f"  {i}. {file_path}")
                if len(files_to_upload) > 10:
                    logger.info(f"  ... and {len(files_to_upload) - 10} more")
            return True
        
        if not files_to_upload:
            logger.info("All files are up to date!")
            return True
        
        # Upload files
        logger.info(f"Uploading {len(files_to_upload)} files...")
        start_time = time.time()
        success_count = 0
        
        for i, rel_path in enumerate(files_to_upload, 1):
            local_info = local_files[rel_path]
            local_path = Path(local_info['local_path'])
            
            logger.info(f"Uploading {i}/{len(files_to_upload)}: {rel_path}")
            if self.upload_file(local_path, rel_path):
                success_count += 1
            else:
                self.stats['errors'] += 1
        
        upload_time = time.time() - start_time
        logger.info(f"Upload complete: {success_count}/{len(files_to_upload)} successful")
        logger.info(f"Upload time: {upload_time:.1f} seconds")
        logger.info(f"Errors: {self.stats['errors']}")
        
        return success_count == len(files_to_upload)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Simple Epstein Browser Data Sync",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Setup SSH keys and test connection
  python sync_data.py --setup --host server.com --user username

  # Dry run - see what would be uploaded
  python sync_data.py --host server.com --user username --dry-run

  # Full sync
  python sync_data.py --host server.com --user username

  # With custom SSH port
  python sync_data.py --host server.com --user username --port 2222
        """
    )
    
    parser.add_argument('--host', required=True, help='Remote server hostname/IP')
    parser.add_argument('--user', required=True, help='Remote server username')
    parser.add_argument('--port', type=int, default=22, help='SSH port')
    parser.add_argument('--setup', action='store_true', help='Setup SSH keys and test connection')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be uploaded without uploading')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Automatically detect workspace root (go up from helpers/upload/ to project root)
    script_dir = Path(__file__).parent
    workspace_root = script_dir.parent.parent  # helpers/upload/ -> helpers/ -> project_root
    local_data_dir = workspace_root / "data"
    
    logger.info(f"Workspace root: {workspace_root}")
    logger.info(f"Local data directory: {local_data_dir}")
    logger.info(f"Remote directory: /data")
    
    uploader = SimpleUploader(
        local_dir=str(local_data_dir),
        remote_host=args.host,
        remote_user=args.user,
        remote_dir="/data",  # Just /data/ in workspace root
        ssh_port=args.port
    )
    
    if args.setup:
        logger.info("Setting up SSH keys...")
        if uploader.generate_ssh_key():
            public_key = uploader.get_public_key()
            if public_key:
                logger.info("SSH keys generated successfully!")
                
                # Try to copy key to server automatically
                logger.info("Attempting to copy key to server...")
                if uploader.copy_key_to_server():
                    logger.info("Key copied successfully! Testing connection...")
                    if uploader.test_connection():
                        logger.info("✅ Setup complete! You can now run sync commands.")
                    else:
                        logger.error("❌ Connection test failed. Check server configuration.")
                else:
                    logger.info("Automatic key copy failed. Manual setup required:")
                    logger.info(f"Add this public key to your server's ~/.ssh/authorized_keys:")
                    logger.info(f"{public_key}")
                    logger.info(f"Then test with: python sync_data.py --host {args.host} --user {args.user}")
        return
    
    success = uploader.sync(dry_run=args.dry_run)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
