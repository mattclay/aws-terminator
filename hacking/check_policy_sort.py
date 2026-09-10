#!/usr/bin/env python
"""Check that Action and Resource lists in IAM policy YAML files are sorted alphabetically (case-insensitive).

Usage:
    python hacking/check_policy_sort.py          # check only
    python hacking/check_policy_sort.py --fix    # fix in place
"""
import glob
import re
import sys
from typing import Any

import yaml

LIST_FIELDS = ('Action', 'Resource')


def check_file(path: str) -> list[str]:
    """Validate that Action and Resource lists in a policy file are sorted case-insensitively."""
    errors: list[str] = []
    with open(path) as f:
        policy: dict[str, Any] = yaml.safe_load(f)

    for statement in policy.get('Statement', []):
        sid: str = statement.get('Sid', '<no Sid>')
        for field in LIST_FIELDS:
            values: list[str] | str = statement.get(field, [])
            if isinstance(values, str):
                continue
            sorted_values: list[str] = sorted(values, key=str.casefold)
            if values != sorted_values:
                lines: list[str] = []
                for actual, expected in zip(values, sorted_values):
                    if actual != expected:
                        lines.append(f'    {actual}')
                lines.append(f'  Expected order:')
                for v in sorted_values:
                    lines.append(f'    {v}')
                errors.append(
                    f'{path}: statement "{sid}" has unsorted {field.lower()}s:\n'
                    + '\n'.join(lines)
                )
    return errors


def fix_file(path: str) -> bool:
    """Sort Action and Resource lists in place, preserving comments attached to each entry."""
    with open(path) as f:
        lines = f.readlines()

    result: list[str] = []
    i = 0
    changed = False
    field_pattern = re.compile(r'^(\s+)(' + '|'.join(LIST_FIELDS) + r'):\s*$')

    while i < len(lines):
        line = lines[i]
        field_match = field_pattern.match(line)

        if field_match:
            result.append(line)
            i += 1

            j = i
            while j < len(lines) and not re.match(r'^(\s+)- ', lines[j]):
                if not re.match(r'^\s*#', lines[j]):
                    break
                j += 1

            indent_match = re.match(r'^(\s+)- ', lines[j]) if j < len(lines) else None
            if not indent_match:
                continue

            action_indent = indent_match.group(1)
            comment_re = re.compile(
                rf'^{re.escape(action_indent)}#|^{re.escape(action_indent)}  #'
            )
            entry_re = re.compile(rf'^{re.escape(action_indent)}- ')
            entries: list[tuple[list[str], str]] = []
            pending_comments: list[str] = []

            while i < len(lines):
                if entry_re.match(lines[i]):
                    entries.append((pending_comments, lines[i]))
                    pending_comments = []
                    i += 1
                elif comment_re.match(lines[i]):
                    pending_comments.append(lines[i])
                    i += 1
                else:
                    break

            if pending_comments:
                for cl in pending_comments:
                    result.append(cl)

            sorted_entries = sorted(entries, key=lambda e: e[1].casefold())
            if sorted_entries != entries:
                changed = True
            for comments, entry_line in sorted_entries:
                result.extend(comments)
                result.append(entry_line)
        else:
            result.append(line)
            i += 1

    if changed:
        with open(path, 'w') as f:
            f.writelines(result)
    return changed


def main() -> int:
    """Check all policy files and report any unsorted lists."""
    fix = '--fix' in sys.argv

    paths: list[str] = glob.glob('aws/policy/*.yaml')
    if not paths:
        print('No policy files found', file=sys.stderr)
        return 1

    if fix:
        fixed: list[str] = []
        for path in sorted(paths):
            if fix_file(path):
                fixed.append(path)
        if fixed:
            print(f'Fixed sort order in {len(fixed)} file(s):')
            for path in fixed:
                print(f'  {path}')
        else:
            print(f'All lists in {len(paths)} policy files are already sorted.')

        errors: list[str] = []
        for path in sorted(paths):
            errors.extend(check_file(path))
        if errors:
            print('\nWARNING: Some lists are still unsorted after fix:', file=sys.stderr)
            for error in errors:
                print(error, file=sys.stderr)
            return 1

        return 0

    all_errors: list[str] = []
    for path in sorted(paths):
        all_errors.extend(check_file(path))

    if all_errors:
        print('Policy sort errors:\n', file=sys.stderr)
        for error in all_errors:
            print(error, file=sys.stderr)
        print(f'\nFound {len(all_errors)} unsorted list(s).', file=sys.stderr)
        print('\nRun with --fix to auto-sort.', file=sys.stderr)
        return 1

    print(f'All lists in {len(paths)} policy files are sorted.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
