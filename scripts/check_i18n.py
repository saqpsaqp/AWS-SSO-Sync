#!/usr/bin/env python3
"""Fails if any i18n catalog's keys don't exactly match the English reference.

Run manually with `python3 scripts/check_i18n.py`; CI runs it on every
push/PR (see .github/workflows/ci.yml).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aws_sso_sync.i18n import CATALOGS, DEFAULT_LANGUAGE


def main() -> int:
    reference = set(CATALOGS[DEFAULT_LANGUAGE])
    ok = True
    for lang, catalog in CATALOGS.items():
        if lang == DEFAULT_LANGUAGE:
            continue
        missing = reference - set(catalog)
        extra = set(catalog) - reference
        if missing:
            print(f"[{lang}] missing keys: {sorted(missing)}")
            ok = False
        if extra:
            print(f"[{lang}] extra keys not in {DEFAULT_LANGUAGE}: {sorted(extra)}")
            ok = False

    if ok:
        print(f"OK - {len(CATALOGS)} catalog(s), {len(reference)} keys each, all in sync.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
