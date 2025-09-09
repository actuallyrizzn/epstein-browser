# Simple Upload Script

One script to rule them all: `sync_data.py`

## Quick Start

```bash
# 1. Setup SSH keys
python sync_data.py --setup --host your-server.com --user your-username

# 2. Add the public key to your server's ~/.ssh/authorized_keys

# 3. Dry run (see what would be uploaded)
python sync_data.py --host your-server.com --user your-username --dry-run

# 4. Full sync
python sync_data.py --host your-server.com --user your-username
```

## Features

- **Idempotent**: Only uploads changed files, skips unchanged ones
- **Smart Caching**: Caches file manifests for faster subsequent runs
- **SSH Key Auth**: No password prompts, automatic key management
- **Windows 11 Optimized**: Works perfectly on Windows development
- **MP4 Exclusion**: Automatically skips video files
- **Path Detection**: Automatically finds workspace and data directories

## Caching System

The script now includes intelligent caching to make subsequent runs much faster:

```bash
# Normal run (uses cache if available)
python sync_data.py --host your-server.com --user your-username

# Force fresh scan (ignore cache)
python sync_data.py --host your-server.com --user your-username --no-cache

# Clear cache
python sync_data.py --host your-server.com --user your-username --clear-cache
```

**Cache Benefits:**
- First run: Scans all files (takes time)
- Subsequent runs: Uses cached file lists (much faster!)
- Cache expires after 24 hours automatically
- Cache is invalidated if paths or settings change

## Help

```bash
python sync_data.py --help
```

That's it. No bullshit.
