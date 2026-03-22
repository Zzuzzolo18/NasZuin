#!/bin/bash
# Restore files moved by nvme_move.sh back to NVME (replacing symlinks with real files)
# Usage: sudo bash restore_symlinks.sh [--dry-run]
#
# This script finds symlinks in /mnt/nvme/naszuin that point to /mnt/hdd1,
# copies the real file back, and removes the symlink.
NVME_BASE="/mnt/nvme/naszuin/davide/zenfone6"
HDD_BASE="/mnt/hdd1"
DRY_RUN=false
RESTORED=0
ERRORS=0
SKIPPED=0
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "=== DRY RUN MODE (no changes will be made) ==="
fi
echo "Starting restore at $(date)"
echo "Scanning for symlinks in $NVME_BASE..."
# Count total symlinks first
TOTAL=$(find "$NVME_BASE" -type l 2>/dev/null | wc -l)
echo "Found $TOTAL symlinks to check"
echo ""
# Process symlinks one by one with progress
COUNT=0
find "$NVME_BASE" -type l -print0 2>/dev/null | while IFS= read -r -d '' link; do
    COUNT=$((COUNT + 1))
    # Get the symlink target
    target=$(readlink "$link")
    # Only process links pointing to HDD
    if [[ "$target" != "$HDD_BASE"* ]]; then
        SKIPPED=$((SKIPPED + 1))
        continue
    fi
    # Check target file exists
    if [[ ! -f "$target" ]]; then
        echo "[$COUNT/$TOTAL] BROKEN: $link -> $target"
        ERRORS=$((ERRORS + 1))
        continue
    fi
    # Get file size for display
    SIZE=$(stat -c%s "$target" 2>/dev/null || echo "?")
    SIZE_MB=$(echo "scale=1; $SIZE / 1048576" | bc 2>/dev/null || echo "?")
    if $DRY_RUN; then
        echo "[$COUNT/$TOTAL] WOULD RESTORE: $(basename "$link") (${SIZE_MB}MB)"
    else
        # Remove symlink, copy real file back
        rm "$link"
        if cp "$target" "$link"; then
            # Set ownership to davide
            chown davide:davide "$link"
            RESTORED=$((RESTORED + 1))
            # Progress every 50 files
            if (( RESTORED % 50 == 0 )); then
                echo "[$COUNT/$TOTAL] Progress: $RESTORED files restored..."
            fi
        else
            echo "[$COUNT/$TOTAL] ERROR copying: $target -> $link"
            # Re-create symlink if copy failed
            ln -s "$target" "$link"
            ERRORS=$((ERRORS + 1))
        fi
    fi
done
echo ""
echo "=== Done at $(date) ==="
echo "Restored: $RESTORED | Errors: $ERRORS | Skipped: $SKIPPED | Total checked: $TOTAL"
