#!/usr/bin/env python3
"""
Architecture Compliance Checker
Enforces Polymarket Bot architecture standards

Usage:
    python check_architecture.py --check-timeout file.py
    python check_architecture.py --check-except file.py
    python check_architecture.py --check-datetime file.py
    python check_architecture.py --check-threads file.py
    python check_architecture.py --check-cache file.py
    python check_architecture.py --all file.py
"""

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import List, Tuple


class ArchitectureChecker:
    """Check code compliance with architecture standards"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.content = Path(filepath).read_text()
        self.lines = self.content.split('\n')
        self.errors = []

    def check_requests_timeout(self) -> List[str]:
        """Check all requests.get/post have timeout parameter"""
        errors = []
        pattern = r'requests\.(get|post|put|delete|patch)\s*\('

        for i, line in enumerate(self.lines, 1):
            if re.search(pattern, line):
                # Check if timeout is in this line or next 3 lines
                context = '\n'.join(self.lines[i-1:min(i+3, len(self.lines))])
                if 'timeout=' not in context and 'timeout =' not in context:
                    errors.append(
                        f"{self.filepath}:{i}: requests call missing timeout parameter\n"
                        f"  {line.strip()}\n"
                        f"  Fix: Add timeout=10 parameter"
                    )

        return errors

    def check_bare_except(self) -> List[str]:
        """Check for bare except blocks"""
        errors = []
        pattern = r'except\s*:'

        for i, line in enumerate(self.lines, 1):
            if re.search(pattern, line):
                errors.append(
                    f"{self.filepath}:{i}: Bare except block (no exception type)\n"
                    f"  {line.strip()}\n"
                    f"  Fix: Use 'except SpecificException as e:' or 'except Exception as e:'"
                )

        return errors

    def check_datetime_utc(self) -> List[str]:
        """Check datetime.now() uses timezone.utc"""
        errors = []
        pattern = r'datetime\.now\(\s*\)'  # Matches datetime.now() with no args

        for i, line in enumerate(self.lines, 1):
            if re.search(pattern, line):
                # Skip if it's in a comment
                if line.strip().startswith('#'):
                    continue

                errors.append(
                    f"{self.filepath}:{i}: datetime.now() without timezone\n"
                    f"  {line.strip()}\n"
                    f"  Fix: Use datetime.now(timezone.utc)"
                )

        return errors

    def check_thread_safety(self) -> List[str]:
        """Check for potential thread safety issues"""
        errors = []

        # Check for Thread usage without Lock
        has_thread = 'Thread(' in self.content or 'threading.Thread' in self.content
        has_lock = 'Lock()' in self.content or 'threading.Lock' in self.content

        if has_thread and not has_lock:
            errors.append(
                f"{self.filepath}: File uses Thread but no Lock found\n"
                f"  Warning: Ensure shared mutable state is protected with locks\n"
                f"  Fix: Add 'from threading import Lock' and protect shared data"
            )

        # Check for common shared state patterns
        shared_state_patterns = [
            (r'self\.\w+\s*=\s*\{\}', 'dict'),
            (r'self\.\w+\s*=\s*\[\]', 'list'),
        ]

        for pattern, state_type in shared_state_patterns:
            for i, line in enumerate(self.lines, 1):
                if re.search(pattern, line) and has_thread:
                    # Check if there's a lock usage within next 50 lines
                    context = '\n'.join(self.lines[i-1:min(i+50, len(self.lines))])
                    if 'with ' not in context or 'lock' not in context.lower():
                        errors.append(
                            f"{self.filepath}:{i}: Potential thread-unsafe {state_type}\n"
                            f"  {line.strip()}\n"
                            f"  Warning: If modified by threads, protect with Lock"
                        )

        return errors

    def check_cache_expiration(self) -> List[str]:
        """Check caches have clear methods"""
        errors = []

        # Find cache definitions
        cache_pattern = r'self\.(\w*cache\w*)\s*=\s*\{\}'

        caches_found = set()
        for i, line in enumerate(self.lines, 1):
            match = re.search(cache_pattern, line)
            if match:
                cache_name = match.group(1)
                caches_found.add(cache_name)

        # Check if there's a clear_cache method
        has_clear_method = 'def clear_cache' in self.content or 'def clear_' in self.content

        if caches_found and not has_clear_method:
            errors.append(
                f"{self.filepath}: Found caches but no clear_cache() method\n"
                f"  Caches: {', '.join(sorted(caches_found))}\n"
                f"  Fix: Add clear_cache() method to clear all caches"
            )

        return errors

    def check_all(self) -> List[str]:
        """Run all checks"""
        all_errors = []
        all_errors.extend(self.check_requests_timeout())
        all_errors.extend(self.check_bare_except())
        all_errors.extend(self.check_datetime_utc())
        all_errors.extend(self.check_thread_safety())
        all_errors.extend(self.check_cache_expiration())
        return all_errors


def main():
    parser = argparse.ArgumentParser(description='Check architecture compliance')
    parser.add_argument('--check-timeout', action='store_true',
                        help='Check requests have timeout')
    parser.add_argument('--check-except', action='store_true',
                        help='Check for bare except blocks')
    parser.add_argument('--check-datetime', action='store_true',
                        help='Check datetime uses UTC')
    parser.add_argument('--check-threads', action='store_true',
                        help='Check thread safety')
    parser.add_argument('--check-cache', action='store_true',
                        help='Check cache expiration')
    parser.add_argument('--all', action='store_true',
                        help='Run all checks')
    parser.add_argument('files', nargs='+', help='Files to check')

    args = parser.parse_args()

    all_errors = []

    for filepath in args.files:
        if not filepath.endswith('.py'):
            continue

        checker = ArchitectureChecker(filepath)
        errors = []

        if args.all:
            errors = checker.check_all()
        else:
            if args.check_timeout:
                errors.extend(checker.check_requests_timeout())
            if args.check_except:
                errors.extend(checker.check_bare_except())
            if args.check_datetime:
                errors.extend(checker.check_datetime_utc())
            if args.check_threads:
                errors.extend(checker.check_thread_safety())
            if args.check_cache:
                errors.extend(checker.check_cache_expiration())

        all_errors.extend(errors)

    if all_errors:
        print("\n" + "="*80)
        print("ARCHITECTURE COMPLIANCE ERRORS")
        print("="*80 + "\n")

        for error in all_errors:
            print(error)
            print()

        print("="*80)
        print(f"Total: {len(all_errors)} architecture violations found")
        print("See ARCHITECTURE.md for standards")
        print("="*80)
        sys.exit(1)
    else:
        print(f"✅ All architecture checks passed for {len(args.files)} file(s)")
        sys.exit(0)


if __name__ == '__main__':
    main()
