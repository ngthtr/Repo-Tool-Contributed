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

"""Unittests for the worksets.py module."""

from pathlib import Path

import pytest

import worksets


@pytest.mark.parametrize(
    "value,member",
    [
        ("a/b:topic", worksets.Member("a/b", "topic")),
        ("a/b:feature/x", worksets.Member("a/b", "feature/x")),
        ("a/b:", worksets.Member("a/b", None)),
        ("a/b", worksets.Member("a/b", None)),
        ("a:b/c:topic", worksets.Member("a:b/c", "topic")),
    ],
)
def test_member_parse(value: str, member: worksets.Member) -> None:
    """Entries are split at the last ':'."""
    assert worksets.Member.Parse(value) == member


def test_member_format_round_trip() -> None:
    """Format() writes what Parse() reads back."""
    for member in (
        worksets.Member("a/b", "topic"),
        worksets.Member("a/b"),
        worksets.Member("a:b", "x"),
    ):
        assert worksets.Member.Parse(member.Format()) == member


@pytest.fixture
def groups(tmp_path: Path) -> worksets.Worksets:
    return worksets.Worksets(str(tmp_path / "config"))


def test_get_missing(groups: worksets.Worksets) -> None:
    assert groups.Get("light") is None
    assert groups.Names() == []


def test_set_get(groups: worksets.Worksets) -> None:
    members = [
        worksets.Member("b", "topic"),
        worksets.Member("a"),
        worksets.Member("c", "other"),
    ]
    groups.Set("light", members)
    assert groups.Get("light") == members
    assert groups.Names() == ["light"]


def test_set_duplicates(groups: worksets.Worksets) -> None:
    """A duplicated project keeps its first position and its last branch."""
    groups.Set(
        "light",
        [
            worksets.Member("a", "x"),
            worksets.Member("b"),
            worksets.Member("a", "y"),
        ],
    )
    assert groups.Get("light") == [
        worksets.Member("a", "y"),
        worksets.Member("b"),
    ]


def test_set_single(groups: worksets.Worksets) -> None:
    groups.Set("light", [worksets.Member("a", "x")])
    assert groups.Get("light") == [worksets.Member("a", "x")]


def test_delete(groups: worksets.Worksets) -> None:
    groups.Set("light", [worksets.Member("a", "x")])
    groups.Set("dark", [worksets.Member("b")])
    groups.Delete("light")
    assert groups.Get("light") is None
    assert groups.Names() == ["dark"]
