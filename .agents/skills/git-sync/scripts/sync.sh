#!/bin/bash

# A helper script for the git-sync agent skill to establish 100% parity with the remote.

echo "🔄 Fetching from remote and pruning deleted branches..."
git fetch --prune

echo ""
echo "🗑️  Deleting local branches that have been deleted on the remote..."
# Find all local branches tracking a remote branch that is now 'gone', and delete them
git branch -vv | grep ': gone]' | awk '{print $1}' | xargs -r git branch -D

echo ""
echo "⬇️  Pulling latest changes for the current branch..."
git pull origin $(git branch --show-current)

echo ""
echo "✅ Local repository is now synced with the remote!"
