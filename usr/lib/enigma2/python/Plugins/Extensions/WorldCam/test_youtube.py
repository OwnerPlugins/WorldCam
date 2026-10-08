#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
WorldCam YouTube resolver test script.

Usage (from SSH on the decoder):

    cd /usr/lib/enigma2/python/Plugins/Extensions/WorldCam
    python3 test_youtube.py
        -> prints environment diagnostics

    python3 test_youtube.py "https://www.youtube.com/watch?v=VIDEO_ID"
        -> tries to resolve and print the direct stream URL
"""
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

import youtube_helper  # noqa: E402


def _print_diag():
    print("=== WorldCam YouTube diagnostics ===")
    for k, v in youtube_helper.get_diagnostics().items():
        print("  %-16s %s" % (k + ":", v))
    print()
    print("Usage: python3 %s <youtube_url>" % os.path.basename(__file__))


def main():
    if len(sys.argv) < 2:
        _print_diag()
        return 0

    url = sys.argv[1]
    print("Resolving: %s" % url)
    stream, error = youtube_helper.resolve_youtube(url)
    if stream:
        print("OK   -> %s" % stream)
        return 0
    print("FAIL -> %s" % error)
    return 1


if __name__ == "__main__":
    sys.exit(main())