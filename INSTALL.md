# Install Rung

Rung is a Hermes Agent plugin: a Desktop pane, a `hermes rung` command and agent tools over one local
SQLite store. These steps install it into a Hermes home and prove the install.

## Before you start

- Hermes Agent with the Desktop app, on macOS or Linux.
- Python 3.10 or newer (the one Hermes runs on).
- Git, for `hermes plugins install` to fetch the repository.

Rung's data lives in its own store under the Hermes home (`plugin-data/rung/rung.db`). Installing,
updating or removing the plugin never edits a project folder.

## Install

Run these in a terminal. `HERMES_HOME` is the Hermes home to install into; leave it unset for the
default `~/.hermes`. `RUNG_REPO` is where Rung comes from; leave it unset for the GitHub repository.

```bash
export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
RUNG_REPO="${RUNG_REPO:-https://github.com/miguelangeloazevedo/rung}"
hermes plugins install "$RUNG_REPO" --enable --yes-deps
hermes plugins validate "$HERMES_HOME/plugins/rung"
hermes plugins list | grep rung
hermes rung doctor
```

What each line proves:

| Step | Expected |
| --- | --- |
| `hermes plugins install` | Rung cloned into `$HERMES_HOME/plugins/rung` and enabled. |
| `hermes plugins validate` | Exit 0. |
| `hermes plugins list` | A `rung` row marked enabled. |
| `hermes rung doctor` | Every check `ok`, last line `rung doctor: PASS`, exit 0. |

## Open the pane

1. Restart the Hermes Desktop app so it loads the new plugin.
2. Pick **Rung** in the sidebar. On a store with no project it opens on the start screen with
   **Try the sample project** and **New project**.

## Update and remove

```bash
hermes plugins update rung        # newer Rung; the store migrates on next open
hermes plugins uninstall rung     # removes the plugin; the store and every project stay
```

To remove Rung's data as well, delete `$HERMES_HOME/plugin-data/rung/` after uninstalling.

## When something is off

`hermes rung doctor` names each check it ran. A failing check prints its fix on the next line, for
example a project whose folder moved:

```text
FAIL  project csvtidy folder: /Users/you/work/csvtidy
      fix: restore the folder, or change it: Rung pane, csvtidy, Project settings
rung doctor: FAIL (1)
```

Run the doctor last after any install or update:

```bash
hermes rung doctor
```
