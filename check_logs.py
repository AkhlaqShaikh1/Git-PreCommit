import subprocess
import sys
import re
import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger(__name__)


PROTECTED_PATHS = [
    'src/config/',
    'src/env/',
]


LOG_PATTERNS = [
    r'^\+.*console\.log',
    r'^\+.*\bprint\s*\(',
    r'^\+.*System\.out\.println',
    r'^\+.*\becho\s+',
    r'^\+.*(?<!logger\.)\blog\s*\('
]


FIX_PATTERNS = [
    r'^\s*console\.log.*',
    r'^\s*print\s*\(.*',
    r'^\s*System\.out\.println.*',
    r'^\s*echo\s+.*',
    r'^\s*(?<!logger\.)log\s*\(.*'
]


def get_staged_files():
    """Returns a list of staged file paths."""
    result = subprocess.run(["git", "diff", "--cached", "--name-only"], stdout=subprocess.PIPE, text=True)
    return result.stdout.strip().splitlines()


def is_protected(file):
    """Returns True if file path matches any protected path."""
    return any(file.startswith(path) for path in PROTECTED_PATHS)


def block_if_protected(files):
    """Blocks commit if any protected file is staged."""
    protected = [f for f in files if is_protected(f)]
    if protected:
        log.info("\n🚫 Commit blocked! Protected files have been modified:\n")
        for f in protected:
            log.info(f" • {f}")
        log.info("\nThese files/folders are protected and must not be changed.")
        sys.exit(1)


def check_for_logs(files):
    """Checks for unwanted console/print/log statements."""
    has_logs = False
    pattern = re.compile('|'.join(LOG_PATTERNS), re.IGNORECASE)

    for file in files:
        if is_protected(file):
            continue

        path = Path(file)
        if not path.exists():
            continue

        result = subprocess.run(["git", "diff", "--cached", file], stdout=subprocess.PIPE, text=True, encoding='utf-8')
        added_lines = [line for line in result.stdout.splitlines() if line.startswith('+') and not line.startswith('+++')]

        for line in added_lines:
            if pattern.search(line):
                log.info(f"⚠️  Log/print detected in {file}:\n   {line}")
                has_logs = True

    return has_logs


def auto_fix_logs(files):
    """Auto-removes bad console/print statements from modified files."""
    fix_patterns = [re.compile(p, re.IGNORECASE) for p in FIX_PATTERNS]
    fixed_files = []

    for file in files:
        if is_protected(file):
            continue

        path = Path(file)
        if not path.exists():
            continue

        original_lines = path.read_text(encoding='utf-8').splitlines()
        new_lines = []
        modified = False

        for line in original_lines:
            if any(p.match(line) for p in fix_patterns):
                log.info(f"🧹 Removed: {line.strip()} from {file}")
                modified = True
                continue
            new_lines.append(line)

        if modified:
            path.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
            fixed_files.append(file)

    if fixed_files:
        subprocess.run(["git", "add"] + fixed_files)
        log.info("\n✅ Fixed and re-staged: " + ", ".join(fixed_files))
    else:
        log.info("✅ No changes needed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--fix', action='store_true', help='Auto-remove log/print lines')
    args = parser.parse_args()

    staged_files = get_staged_files()
    if not staged_files:
        log.info("📦 No staged files to check.")
        sys.exit(0)

    # Block commit if protected paths were touched
    block_if_protected(staged_files)

    if args.fix:
        auto_fix_logs(staged_files)
        sys.exit(0)

    if check_for_logs(staged_files):
        log.info("\n❌ Please remove debug logs before committing.")
        sys.exit(1)
    else:
        log.info("✅ No unwanted logs found.")
