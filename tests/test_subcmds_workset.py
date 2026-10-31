# Copyright (C) 2026 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unittests for the subcmds/workset.py module."""

from typing import Optional

import pytest

from subcmds import workset


@pytest.mark.parametrize(
    "arg,project,branch",
    [
        ("a/b", "a/b", None),
        ("a/b:topic", "a/b", "topic"),
        ("a/b:feature/x", "a/b", "feature/x"),
        ("a/b:", "a/b", ""),
        ("name:with:colons:topic", "name:with:colons", "topic"),
        # Windows paths with a drive letter.
        ("C:\\src\\a", "C:\\src\\a", None),
        ("c:/src/a", "c:/src/a", None),
        ("C:\\src\\a:topic", "C:\\src\\a", "topic"),
    ],
)
def test_split_branch(arg: str, project: str, branch: Optional[str]) -> None:
    """<project>[:<branch>] arguments are split at the last ':'."""
    assert workset._SplitBranch(arg) == (project, branch)
