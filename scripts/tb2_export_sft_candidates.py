#!/usr/bin/env python3
"""Export accepted, sanitized TB2 SFT candidate records from a run ledger."""

from zharness.tb2.pretrain_prep import export_command


if __name__ == "__main__":
    raise SystemExit(export_command())

