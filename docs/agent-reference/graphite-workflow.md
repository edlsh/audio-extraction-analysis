# Graphite Stacked PR Workflow

## Overview

This project uses Graphite (`gt`) for stacked PRs instead of raw git commands.

## Command Reference

| Instead of... | Use Graphite... | Purpose |
|---------------|-----------------|---------|
| `git commit` | `gt create -m "message"` | Create branch + commit |
| `git push` | `gt submit --no-interactive` | Submit stack to GitHub |
| `git rebase` | `gt restack` | Rebase stack on latest changes |
| `git checkout` | `gt checkout` | Interactive branch selection |
| `git pull` | `gt sync` | Sync trunk + rebase stacks |
| Update PR | `gt checkout <branch> && gt modify` | Add commits to existing PR |

## Creating a Stack

**CRITICAL**: Write code FIRST, then create branch.

```bash
# 1. Write code for first PR
# 2. Stage: git add <files>
# 3. Create branch: gt create -m "feat: description"
# 4. Repeat for each PR in stack
# 5. Submit entire stack: gt submit --no-interactive
```

## Stack Planning Template

Before coding, present stack structure for approval:

```markdown
## Proposed Stack Structure

1. **PR 1**: `feat: Add base interface`
   - Files: src/module/base.py
   
2. **PR 2**: `feat: Implement concrete` (builds on PR 1)
   - Files: src/module/impl.py
   
Proceed? (y/n)
```

## Rules

- ✅ Write code FIRST, then `gt create`
- ✅ Use `gt submit --no-interactive` to push
- ✅ Use `gt restack` after trunk updates
- ✅ Use `gt modify` to amend existing PRs
- ❌ NEVER use `git commit`, `git push`, or `git rebase` directly
