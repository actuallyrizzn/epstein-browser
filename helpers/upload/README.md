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

## Help

```bash
python sync_data.py --help
```

That's it. No bullshit.
