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

"""E2E tests for worksets: `repo workset` and the global -W option."""

from typing import List

import harness


PATHS = ("a", "b", "c")


def _setup(host: harness.GitHost, client: harness.RepoClient) -> None:
    """A client with projects a, b & c, a on t1, b & c on t2.

    b also has t1, so it is a project of two tasks.
    """
    for path in PATHS:
        host.create_repo(f"platform/{path}", {"f": path})
    host.create_manifest(
        harness.manifest_xml(
            "\n".join(
                f'<project name="platform/{p}" path="{p}" />' for p in PATHS
            )
        )
    )
    client.init(host.manifest_url)
    client.sync()
    client.run("start", "t1", "a", "b")
    client.run("start", "t2", "b", "c")


def _branch(client: harness.RepoClient, path: str) -> str:
    return client.git(path, "symbolic-ref", "--short", "HEAD").strip()


def _entries(client: harness.RepoClient, name: str) -> List[str]:
    out = harness.run_git(
        "config",
        "--file",
        str(client.repodir / "manifests.git" / "config"),
        "--get-all",
        f"workset.{name}.project",
        env=client.env,
    )
    return out.split()


def test_workset_branches(
    host: harness.GitHost, client: harness.RepoClient
) -> None:
    """Worksets record a branch per project."""
    _setup(host, client)

    # Explicit branch, the checked out one by default.
    client.run("workset", "create", "w1", "a", "b:t1")
    assert _entries(client, "w1") == ["a:t1", "b:t1"]

    client.run("workset", "create", "w2", "b:t2", "c")
    assert _entries(client, "w2") == ["b:t2", "c:t2"]

    # No branch, then an update of the branch of a member, in place.
    client.run("workset", "add", "w2", "a:")
    client.run("workset", "update", "w2", "b:t1")
    assert _entries(client, "w2") == ["b:t1", "c:t2", "a:"]

    out = client.run("workset", "-v").stdout
    assert out.splitlines() == [
        "w1",
        "  a  t1",
        "  b  t1 (checked out: t2)",
        "w2",
        "  b  t1 (checked out: t2)",
        "  c  t2",
        "  a  -",
    ]

    client.run("workset", "remove", "w2", "c")
    assert _entries(client, "w2") == ["b:t1", "a:"]


def test_workset_add_update(
    host: harness.GitHost, client: harness.RepoClient
) -> None:
    """`add` takes new projects only, `update` existing ones only."""
    _setup(host, client)
    client.run("workset", "create", "w1", "a")

    result = client.run("workset", "add", "w1", "c", "a:t2", check=False)
    assert "already in workset 'w1': a" in result.stderr
    result = client.run("workset", "update", "w1", "b:t1", check=False)
    assert "not in workset 'w1': b" in result.stderr
    assert _entries(client, "w1") == ["a:t1"]

    # With no branch given, update records the checked out one.
    client.run("checkout", "t2", "b")
    client.run("workset", "add", "w1", "b:t1")
    client.run("workset", "update", "w1", "b")
    assert _entries(client, "w1") == ["a:t1", "b:t2"]


def test_workset_bad_branches(
    host: harness.GitHost, client: harness.RepoClient
) -> None:
    """Branches are rejected where they do not fit."""
    _setup(host, client)
    client.run("workset", "create", "w1", "a")

    result = client.run("workset", "remove", "w1", "a:t1", check=False)
    assert result.returncode != 0
    result = client.run("workset", "add", "w1", "b:bad..name", check=False)
    assert "not a valid branch name" in result.stderr
    assert _entries(client, "w1") == ["a:t1"]


def test_checkout_workset(
    host: harness.GitHost, client: harness.RepoClient
) -> None:
    """`repo -W <workset> checkout` checks out the recorded branches."""
    _setup(host, client)
    client.run("workset", "create", "w1", "a", "b:t1")
    client.run("workset", "create", "w2", "b:t2", "c", "a:")

    client.run("checkout", "t2", "b")
    client.run("-W", "w1", "checkout")
    assert [_branch(client, p) for p in PATHS] == ["t1", "t1", "t2"]

    result = client.run("-W", "w2", "checkout")
    assert "a has no branch, skipping" in result.stderr
    assert [_branch(client, p) for p in PATHS] == ["t1", "t2", "t2"]

    # A branch given on the command line is used for all the projects.
    client.run("-W", "w1", "checkout", "t2")
    assert [_branch(client, p) for p in PATHS] == ["t1", "t2", "t2"]


def test_checkout_workset_missing_branch(
    host: harness.GitHost, client: harness.RepoClient
) -> None:
    """A recorded branch that no longer exists fails the checkout."""
    _setup(host, client)
    client.run("workset", "create", "w1", "a:t1", "c:t1")

    result = client.run("-W", "w1", "checkout", check=False)
    assert result.returncode != 0
    assert "c/: branch t1 does not exist" in result.stderr
    # The other projects are still checked out.
    assert _branch(client, "a") == "t1"

    client.run("workset", "create", "w2", "a:")
    result = client.run("-W", "w2", "checkout", check=False)
    assert result.returncode != 0
    assert "records no branch" in result.stderr
