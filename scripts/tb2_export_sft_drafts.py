#!/usr/bin/env python3
"""Export TB2 diagnostic trajectories in SFT-compatible draft format."""

from zharness.tb2.pretrain_prep import export_drafts_command


if __name__ == "__main__":
    raise SystemExit(export_drafts_command())
