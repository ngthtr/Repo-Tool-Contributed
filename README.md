# repo

## Workset feature (this branch)

This branch adds **worksets** to repo: named sets of projects that you change
together for one task, each on its own local branch (e.g. a HAL, its kernel
driver and the device config). A workset is local to your client checkout: it
does not change the manifest nor what `repo sync` fetches.

### Manage worksets: `repo workset`

```sh
repo workset [-v]                                  # list worksets (-v: projects and branches)
repo workset create <workset> <project>[:<branch>]...
repo workset add    <workset> <project>[:<branch>]...
repo workset update <workset> <project>[:<branch>]...  # change recorded branches
repo workset remove <workset> <project>...
repo workset delete <workset>...
```

- `<project>:<branch>` records the branch to use for the project.
  With `<project>` alone, the branch currently checked out is recorded.
- Worksets are stored in `.repo/manifests.git/config`, so they survive
  `repo sync`, and may span submanifests.

### Use a workset with other commands: `-W/--workset`

```sh
repo -W light status
repo -W light start my-topic
repo --workset light forall -c git log -1 --oneline
repo -W task-a checkout     # check out the recorded branch in every project
```

- With no project argument, the command runs on the projects of the workset.
  Projects given on the command line must belong to the workset.
- Supported commands: abandon, branches, checkout, diff, forall, grep, info,
  list, overview, prune, rebase, stage, start, status, upload.
  Other commands (including `sync`) reject `-W`.
- `repo -W <workset> checkout` with no branch switches every project to the
  branch recorded for it, to switch between tasks.

The branch also fixes global options taking their value as a separate
argument, e.g. `repo --color never status`.

---

Repo is a tool built on top of Git.  Repo helps manage many Git repositories,
does the uploads to revision control systems, and automates parts of the
development workflow.  Repo is not meant to replace Git, only to make it
easier to work with Git.  The repo command is an executable Python script
that you can put anywhere in your path.

* Homepage: <https://gerrit.googlesource.com/git-repo/>
* Mailing list: [repo-discuss on Google Groups][repo-discuss]
* Bug reports: <https://issues.gerritcodereview.com/issues?q=is:open%20componentid:1370071>
* Source: <https://gerrit.googlesource.com/git-repo/>
* Overview: <https://source.android.com/source/developing.html>
* Docs: <https://source.android.com/source/using-repo.html>
* [repo Manifest Format](./docs/manifest-format.md)
* [repo Hooks](./docs/repo-hooks.md)
* [Contributing](./CONTRIBUTING.md)
* Running Repo in [Microsoft Windows](./docs/windows.md)
* GitHub mirror: <https://github.com/GerritCodeReview/git-repo>
* Postsubmit tests: <https://github.com/GerritCodeReview/git-repo/actions>

## Contact

Please use the [repo-discuss] mailing list or [issue tracker] for questions.

You can [file a new bug report][new-bug] under the "repo" component.

Please do not e-mail individual developers for support.
They do not have the bandwidth for it, and often times questions have already
been asked on [repo-discuss] or bugs posted to the [issue tracker].
So please search those sites first.

## Install

Many distros include repo, so you might be able to install from there.
```sh
# Debian/Ubuntu.
$ sudo apt-get install repo

# Gentoo.
$ sudo emerge dev-vcs/repo
```

You can install it manually as well as it's a single script.
```sh
$ mkdir -p ~/.bin
$ PATH="${HOME}/.bin:${PATH}"
$ curl https://storage.googleapis.com/git-repo-downloads/repo > ~/.bin/repo
$ chmod a+rx ~/.bin/repo
```

## Shell Completion

Repo includes completion scripts for Bash and Zsh.

### Bash

To enable completion in Bash, source `completion.bash` in your `~/.bashrc`:

```sh
source /path/to/git-repo/completion.bash
```

### Zsh

To enable completion in Zsh, you can either:

1.  Copy or symlink `completion.zsh` to a file named `_repo` in a directory in your `$fpath`:
    ```sh
    mkdir -p ~/.zsh/completion
    # You can copy the file:
    cp /path/to/git-repo/completion.zsh ~/.zsh/completion/_repo
    # Or symlink it:
    ln -s /path/to/git-repo/completion.zsh ~/.zsh/completion/_repo
    ```
    Then add that directory to your `fpath` in `~/.zshrc` before `compinit`:
    ```zsh
    fpath=(~/.zsh/completion $fpath)
    autoload -Uz compinit
    compinit
    ```

2.  Or source the file directly and call `compdef` in your `~/.zshrc`:
    ```zsh
    source /path/to/git-repo/completion.zsh
    compdef _repo repo
    ```


[new-bug]: https://issues.gerritcodereview.com/issues/new?component=1370071
[issue tracker]: https://issues.gerritcodereview.com/issues?q=is:open%20componentid:1370071
[repo-discuss]: https://groups.google.com/forum/#!forum/repo-discuss
