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

"""Storage for worksets.

A workset is a named list of projects, local to one client checkout, each
with the local branch used for it, if any. Unlike manifest groups, it does
not change the manifest nor what `repo sync` fetches: it only selects
projects for commands.

Worksets are stored in the manifest project config
(.repo/manifests.git/config), one <path>:<branch> entry per project, with
an empty branch when the project has none:

  [workset "light"]
      project = vendor/qcom/opensource/lights:led-fix
      project = device/acme/board:led-dt
      project = build_scripts:

Git does not allow ':' in branch names, so the entry is split at its last
':'. Paths are relative to the outermost manifest, so a workset may span
submanifests.
"""

import re
from typing import Iterable, List, NamedTuple, Optional

import git_config


_SECTION = "workset"
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class Member(NamedTuple):
    """A project of a workset."""

    # Path relative to the outermost manifest.
    path: str
    # Local branch used for the project in this workset, if any.
    branch: Optional[str] = None

    def Format(self) -> str:
        """The config entry for this member."""
        return self.path + ":" + (self.branch or "")

    @classmethod
    def Parse(cls, value: str) -> "Member":
        """Parse a config entry, as written by Format()."""
        path, sep, branch = value.rpartition(":")
        if not sep:
            # No branch separator, e.g. a hand-written entry.
            return cls(value)
        return cls(path, branch or None)


def CountProjects(count: int) -> str:
    """Return "1 project" or "<count> projects"."""
    return f"{count} project" + ("" if count == 1 else "s")


def IsValidName(name: str) -> bool:
    """Whether |name| can be used as a workset name."""
    return bool(_NAME_RE.match(name)) and not name.endswith(".")


class Worksets:
    """Worksets of a client checkout."""

    def __init__(self, configfile: str):
        """Initialize.

        Args:
            configfile: Path of the config file holding the worksets, usually
                the outermost manifest project config.
        """
        self._configfile = configfile

    def _config(self) -> git_config.GitConfig:
        # A fresh object for every access: GitConfig caches the section list
        # and does not refresh it on writes. No defaults on purpose, worksets
        # only make sense for this client.
        return git_config.GitConfig(configfile=self._configfile)

    @staticmethod
    def _key(name: str) -> str:
        return f"{_SECTION}.{name}.project"

    def Names(self) -> List[str]:
        """All workset names, sorted."""
        return sorted(self._config().GetSubSections(_SECTION))

    def Get(self, name: str) -> Optional[List[Member]]:
        """Members of workset |name|, or None if it does not exist."""
        config = self._config()
        if not config.HasSection(_SECTION, name):
            return None
        values = config.GetString(self._key(name), all_keys=True) or []
        return [Member.Parse(x) for x in values]

    def Set(self, name: str, members: Iterable[Member]) -> None:
        """Create or replace workset |name| with |members|.

        The order is kept. A project listed more than once keeps its first
        position and its last branch.
        """
        by_path = {}
        for member in members:
            by_path[member.path] = member
        values = [m.Format() for m in by_path.values()]
        self._config().SetString(self._key(name), values)

    def Delete(self, name: str) -> None:
        """Delete workset |name|."""
        self._config().SetString(self._key(name), None)
