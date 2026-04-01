#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Shared pytest fixtures for Doc2ArchAgent validation tests."""

import sys
from pathlib import Path

import pytest

# Add tools/ to path so we can import validate
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def valid_dir():
    return FIXTURES_DIR / "valid"


@pytest.fixture
def invalid_dir():
    return FIXTURES_DIR / "invalid"
