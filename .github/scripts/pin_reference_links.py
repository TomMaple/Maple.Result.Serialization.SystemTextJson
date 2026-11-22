#!/usr/bin/env python3
"""Pins the source links of the reference pages to the tag of a release.

Usage:
  pin_reference_links.py VERSION [REPOSITORY_ROOT]

Rewrites every source link of docs/Reference (`…/blob/<ref>/src/…`) to the tag of the release, `vVERSION`, with the
line of the declaration in the working tree: a link to `main` keeps its line, and a link to an earlier release gets
the line where the same declaration is now. Run it in the pull request that prepares a release, before Draft release
(docs/releasing.md); then `check_reference_docs.py --release VERSION` checks the result.

It refuses a version whose tag exists already, and a link whose declaration is not in the code any more: the check
reports those, and they are fixed first.

Python 3 without packages, as the other scripts of this folder.
"""

import os
import sys

# The script runs isolated (python3 -I), which leaves the folder of the script out of the module search path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_reference_docs import Checker, SOURCE_LINK, markdown_files, release_tag  # noqa: E402


def pin(root, tag):
    """Pins the links of every page; returns the problems, one line each. Nothing is written when there is any."""
    checker = Checker(root)
    problems, pinned, changed = [], 0, {}
    for page in sorted(markdown_files(root, os.path.join("docs", "Reference"))):
        full = os.path.join(root, page)
        with open(full, encoding="utf-8", newline="") as file:
            text = file.read()

        def replace(match):
            nonlocal pinned
            ref, path, number, _ = match.groups()
            line = number
            if number and ref in checker.tags:
                current = checker.current_line(path, ref, int(number))
                if current is None:
                    problems.append(f"{page}: the declaration at {os.path.basename(path)}#L{number} of {ref} is not in "
                                    f"the code any more, or changed: link the member to main first")
                    return match.group(0)
                line = str(current)
            old = f"/blob/{ref}/{path}" + (f"#L{number}" if number else "")
            new = f"/blob/{tag}/{path}" + (f"#L{line}" if line else "")
            pinned += old != new
            return match.group(0).replace(old, new, 1)

        pinned_text = SOURCE_LINK.sub(replace, text)
        if pinned_text != text:
            changed[full] = pinned_text

    if problems:
        print(f"No link pinned: {len(problems)} link(s) cannot be pinned to {tag}.", file=sys.stderr)
        return problems

    for full, pinned_text in changed.items():
        with open(full, "w", encoding="utf-8", newline="") as file:
            file.write(pinned_text)
    print(f"{pinned} source link(s) pinned to {tag}.", file=sys.stderr)
    return problems


def main(arguments):
    if not 1 <= len(arguments) <= 2 or arguments[0].startswith("-"):
        sys.exit(__doc__)
    tag = release_tag(arguments[0])
    if tag is None:
        sys.exit(f"'{arguments[0]}' is not a version (X.Y.Z or X.Y.Z-pre).")
    root = arguments[1] if len(arguments) > 1 else os.getcwd()
    if not os.path.isdir(os.path.join(root, "docs", "Reference")):
        sys.exit(f"No docs/Reference folder in '{root}'.")
    if tag in Checker(root).tags:
        sys.exit(f"The tag {tag} exists already: a release is pinned before it is published.")

    problems = pin(root, tag)
    for problem in problems:
        print(problem)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
