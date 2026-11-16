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

import os
import re
from typing import Collection, List, Optional, Set, Tuple

import command
import error
import git_command
import repo_logging
import worksets


logger = repo_logging.RepoLogger(__file__)


class WorksetCommandError(error.SilentRepoExitError):
    """The workset command failed (errors are already logged)."""


# A Windows path with a drive letter, e.g. C:\src\project, has no branch.
_DRIVE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _SplitBranch(arg: str) -> Tuple[str, Optional[str]]:
    """Split a <project>[:<branch>] argument.

    Returns:
        The project, and the branch: None when not given, "" when given empty
        to record no branch.
    """
    project, sep, branch = arg.rpartition(":")
    if not sep or (len(project) == 1 and _DRIVE_PATH_RE.match(arg)):
        return arg, None
    return project, branch


class Workset(command.Command):
    COMMON = False
    helpSummary = "Manage worksets of projects"
    helpUsage = """
%prog [-v]
%prog create <workset> <project>[:<branch>]...
%prog add <workset> <project>[:<branch>]...
%prog update <workset> <project>[:<branch>]...
%prog remove <workset> <project>...
%prog delete <workset>...
"""
    helpDescription = """
A workset is a named set of projects, local to this client checkout.
It is meant for the projects you change together for a task, each on its
own local branch. Unlike manifest groups, it does not modify the manifest
nor what `repo sync` fetches.

Every project of a workset records the local branch used for it, if any.
Give it as <project>:<branch>. With <project> alone, the branch currently
checked out in the project is recorded, none if the project is on a detached
HEAD or not checked out yet. Use <project>: to record no branch.

Worksets are stored in .repo/manifests.git/config and use project paths
relative to the outermost manifest.

Use the global option -W <workset> (or --workset) to limit other commands to
the projects of a workset, e.g. `repo -W light status`. `repo -W <workset>
checkout` checks out the recorded branch of every project, to switch to the
task.

With no subcommand, list the worksets. With -v, also list their projects
and branches, and the branch checked out when it differs.

'create' makes a new workset from the given projects.

'add' adds projects to an existing workset. Projects that are not checked
out yet can be added too.

'update' changes the recorded branch of projects already in a workset.

'remove' removes projects from a workset. Removing the last project deletes
the workset.
"""

    _SUBCOMMANDS = ("create", "add", "update", "remove", "delete")

    # Paths of all the projects, relative to the outer manifest. Only computed
    # if a project argument cannot be found otherwise.
    _all_paths: Optional[Set[str]] = None

    def ValidateOptions(self, opt, args):
        if not args:
            return

        sub = args[0]
        if sub not in self._SUBCOMMANDS:
            self.OptionParser.error(f"unknown subcommand '{sub}'")

        names = args[1:]
        projects = []
        if sub in ("create", "add", "update", "remove"):
            if len(names) < 2:
                self.Usage()
            names, projects = names[:1], names[1:]
        elif not names:
            self.Usage()

        for name in names:
            if not worksets.IsValidName(name):
                self.OptionParser.error(f"'{name}' is not a valid workset name")

        for arg in projects:
            project, branch = _SplitBranch(arg)
            if branch is None:
                continue
            if sub == "remove":
                self.OptionParser.error(
                    f"'{arg}': a branch cannot be given here, only a project"
                )
            if not project:
                self.OptionParser.error(f"'{arg}': missing project")
            if branch and not git_command.IsValidBranchName(branch):
                self.OptionParser.error(
                    f"'{branch}' is not a valid branch name"
                )

    def _Resolve(
        self, opt, arg: str, stale: Collection[str] = ()
    ) -> List[Tuple]:
        """Resolve a project argument.

        Projects that are not checked out yet are accepted. GetProjects() can
        only find them by name, so their paths are resolved here, relative to
        the current directory like other paths. So are the |stale| paths, that
        are no longer in the manifest.

        Returns:
            (path relative to the outer manifest, project or None) tuples.
        """
        all_manifests = not opt.this_manifest_only
        try:
            projects = self.GetProjects(
                [arg], missing_ok=True, all_manifests=all_manifests
            )
        except error.NoSuchProjectError:
            if self._all_paths is None:
                self._all_paths = {
                    p.RelPath(local=False)
                    for p in self.GetProjects(
                        None, missing_ok=True, all_manifests=all_manifests
                    )
                }
            path = os.path.relpath(
                os.path.abspath(arg), self.manifest.outer_client.topdir
            ).replace("\\", "/")
            if path not in self._all_paths and path not in stale:
                raise
            return [(path, None)]
        return [(p.RelPath(local=False), p) for p in projects]

    def _ResolvePaths(
        self, opt, args: List[str], stale: Collection[str] = ()
    ) -> List[str]:
        """Resolve project arguments to paths relative to the outer manifest."""
        return [
            path for arg in args for path, _ in self._Resolve(opt, arg, stale)
        ]

    def _ResolveMembers(self, opt, args: List[str]) -> List[worksets.Member]:
        """Resolve <project>[:<branch>] arguments to workset members."""
        result = []
        for arg in args:
            project_arg, branch = _SplitBranch(arg)
            for path, project in self._Resolve(opt, project_arg):
                if branch is None and project is not None and project.Exists:
                    result.append(worksets.Member(path, project.CurrentBranch))
                else:
                    result.append(worksets.Member(path, branch or None))
        return result

    @staticmethod
    def _Fail(message: str) -> None:
        logger.error("error: %s", message)
        raise WorksetCommandError()

    def _GetExisting(self, groups, name: str) -> List[worksets.Member]:
        members = groups.Get(name)
        if members is None:
            self._Fail(f"no such workset '{name}'")
        return members

    def _List(self, opt, groups) -> None:
        projects = None
        for name in groups.Names():
            print(name)
            if not opt.verbose:
                continue
            if projects is None:
                projects = {
                    p.RelPath(local=False): p
                    for p in self.manifest.outer_client.all_projects
                }
            members = groups.Get(name)
            width = max((len(m.path) for m in members), default=0)
            for member in members:
                line = (
                    "  "
                    + member.path.ljust(width)
                    + "  "
                    + (member.branch or "-")
                )
                project = projects.get(member.path)
                if member.branch and project is not None and project.Exists:
                    current = project.CurrentBranch
                    if current != member.branch:
                        line += f" (checked out: {current or 'detached HEAD'})"
                print(line.rstrip())

    def _Create(self, opt, groups, name: str, args: List[str]) -> None:
        if groups.Get(name) is not None:
            self._Fail(f"workset '{name}' already exists")

        groups.Set(name, self._ResolveMembers(opt, args))
        if not opt.quiet:
            count = worksets.CountProjects(len(groups.Get(name)))
            print(f"Created workset '{name}' with {count}")

    def _Add(self, opt, groups, name: str, args: List[str]) -> None:
        members = self._GetExisting(groups, name)
        added = self._ResolveMembers(opt, args)
        current = {m.path for m in members}
        present = sorted({m.path for m in added if m.path in current})
        if present:
            self._Fail(
                f"already in workset '{name}': {', '.join(present)} "
                "(use 'update' to change the branch)"
            )
        groups.Set(name, members + added)

    def _Update(self, opt, groups, name: str, args: List[str]) -> None:
        members = self._GetExisting(groups, name)
        updated = {m.path: m for m in self._ResolveMembers(opt, args)}
        missing = sorted(set(updated) - {m.path for m in members})
        if missing:
            self._Fail(f"not in workset '{name}': {', '.join(missing)}")
        groups.Set(name, [updated.get(m.path, m) for m in members])

    def _Remove(self, opt, groups, name: str, args: List[str]) -> None:
        members = self._GetExisting(groups, name)
        paths = [m.path for m in members]
        to_remove = set(self._ResolvePaths(opt, args, stale=paths))
        missing = sorted(to_remove - set(paths))
        if missing:
            self._Fail(f"not in workset '{name}': {', '.join(missing)}")

        remaining = [m for m in members if m.path not in to_remove]
        if remaining:
            groups.Set(name, remaining)
        else:
            groups.Delete(name)
            if not opt.quiet:
                print(f"Deleted workset '{name}' (no project left)")

    def _Delete(self, opt, groups, names: List[str]) -> None:
        for name in names:
            self._GetExisting(groups, name)
        for name in names:
            groups.Delete(name)

    def Execute(self, opt, args):
        groups = self.GetWorksets()
        if not args:
            self._List(opt, groups)
            return

        sub, rest = args[0], args[1:]
        if sub == "create":
            self._Create(opt, groups, rest[0], rest[1:])
        elif sub == "add":
            self._Add(opt, groups, rest[0], rest[1:])
        elif sub == "update":
            self._Update(opt, groups, rest[0], rest[1:])
        elif sub == "remove":
            self._Remove(opt, groups, rest[0], rest[1:])
        elif sub == "delete":
            self._Delete(opt, groups, rest)
