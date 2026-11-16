# Copyright (C) 2009 The Android Open Source Project
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

from typing import List, NamedTuple, Optional

import command
import error
import progress
import repo_logging


logger = repo_logging.RepoLogger(__file__)


class CheckoutBranchResult(NamedTuple):
    # Whether the Project is on the branch (i.e. branch exists and no errors)
    result: Optional[bool]
    project_idx: int
    error: Optional[Exception]


class _CheckoutResults(NamedTuple):
    """Project indexes by outcome, and the errors of the failed ones."""

    success: List[int]
    missing: List[int]
    failed: List[int]
    errors: List[Exception]


class CheckoutCommandError(error.RepoExitError):
    """Exception thrown when checkout command fails."""


class MissingBranchError(error.RepoExitError):
    """Exception thrown when no project has specified branch."""


class Checkout(command.Command):
    COMMON = True
    WORKSET_SUPPORT = True
    helpSummary = "Checkout a branch for development"
    helpUsage = """
%prog <branchname> [<project>...]
%prog (with -W <workset>)
"""
    helpDescription = """
The '%prog' command checks out an existing branch that was previously
created by 'repo start'.

The command is equivalent to:

  repo forall [<project>...] -c git checkout <branchname>

With the global option -W <workset> and no branch name, every project of the
workset checks out the branch recorded for it in the workset, e.g. to switch
to the task of the workset. See `repo help workset`.
"""
    PARALLEL_JOBS = command.DEFAULT_LOCAL_JOBS

    def ValidateOptions(self, opt, args):
        if not args and not self.workset:
            self.Usage()

    @classmethod
    def _ExecuteOne(cls, project_idx):
        """Checkout one project."""
        err = None
        result = None
        context = cls.get_parallel_context()
        project = context["projects"][project_idx]
        try:
            result = project.CheckoutBranch(context["branches"][project_idx])
        except error.GitError as e:
            err = e
        return CheckoutBranchResult(result, project_idx, err)

    def _Checkout(self, opt, projects, branches, title) -> _CheckoutResults:
        """Checkout branches[i] in projects[i], in parallel."""
        results = _CheckoutResults([], [], [], [])

        def _ProcessResults(_pool, pm, outputs):
            for output in outputs:
                if output.error is not None:
                    results.errors.append(output.error)
                    results.failed.append(output.project_idx)
                elif output.result:
                    results.success.append(output.project_idx)
                else:
                    results.missing.append(output.project_idx)
                pm.update(msg="")

        with self.ParallelContext():
            context = self.get_parallel_context()
            context["projects"] = projects
            context["branches"] = branches
            self.ExecuteInParallel(
                opt.jobs,
                self._ExecuteOne,
                range(len(projects)),
                callback=_ProcessResults,
                output=progress.Progress(title, len(projects), quiet=opt.quiet),
            )

        if results.failed:
            for idx in sorted(results.failed):
                logger.error(
                    "error: %s/: cannot checkout %s",
                    projects[idx].relpath,
                    branches[idx],
                )
        return results

    def _CheckoutBranch(self, opt, branch, projects) -> None:
        """Checkout |branch| in the |projects| having it."""
        results = self._Checkout(
            opt, projects, [branch] * len(projects), f"Checkout {branch}"
        )
        if results.failed:
            raise CheckoutCommandError(aggregate_errors=results.errors)
        if not results.success:
            msg = f"error: no project has branch {branch}"
            logger.error(msg)
            raise MissingBranchError(msg)

    def _CheckoutWorkset(self, opt, projects) -> None:
        """Checkout in every project the branch recorded in the workset."""
        recorded = {m.path: m.branch for m in self.workset_members}
        todo = []
        for project in projects:
            branch = recorded.get(project.RelPath(local=False))
            if branch:
                todo.append((project, branch))
            else:
                logger.warning(
                    "warning: workset '%s': %s has no branch, skipping",
                    self.workset,
                    project.RelPath(local=False),
                )
        if not todo:
            msg = f"error: workset '{self.workset}' records no branch"
            logger.error(msg)
            raise MissingBranchError(msg)

        projects = [p for p, _ in todo]
        branches = [b for _, b in todo]
        results = self._Checkout(
            opt, projects, branches, f"Checkout workset {self.workset}"
        )
        # Every branch was recorded on purpose: a missing one is an error.
        for idx in sorted(results.missing):
            logger.error(
                "error: %s/: branch %s does not exist",
                projects[idx].relpath,
                branches[idx],
            )
        if results.failed:
            raise CheckoutCommandError(aggregate_errors=results.errors)
        if results.missing:
            # The missing branches are already reported.
            raise MissingBranchError(
                f"workset '{self.workset}': missing branch"
            )

    def Execute(self, opt, args):
        all_manifests = not opt.this_manifest_only
        if args:
            projects = self.GetProjects(args[1:], all_manifests=all_manifests)
            self._CheckoutBranch(opt, args[0], projects)
        else:
            projects = self.GetProjects(None, all_manifests=all_manifests)
            self._CheckoutWorkset(opt, projects)
