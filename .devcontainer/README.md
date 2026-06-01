# JangLabs dev container

A reproducible, throwaway dev environment for the JangLabs monorepo. The
toolchain (Python 3.12, `uv`, `ruff`, `shellcheck`, `gh`, Node LTS) lives
*inside* the container; the repo is bind-mounted in, so your edits persist on
the host but package/build pollution does not. `podman rm` the container and the
host is pristine.

## Prerequisites (not installed on this box yet)

```sh
paru -S podman
npm i -g @devcontainers/cli   # or invoke ad-hoc with: npx @devcontainers/cli ...
```

Rootless podman needs a sub-uid/sub-gid range for your user. On Arch this is
`/etc/subuid` + `/etc/subgid` (e.g. `jangmanj:100000:65536`); `podman info` warns
if they're missing. `sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 jangmanj`
sets them, then `podman system migrate`.

## Bring it up (headless CLI)

Run from the repo root. `--docker-path podman` points the CLI at podman instead
of docker (the login shell here is fish):

```fish
devcontainer up --workspace-folder . --docker-path podman
```

Open a shell inside the running container:

```fish
devcontainer exec --workspace-folder . --docker-path podman bash
```

Rebuild after editing `devcontainer.json` or `postCreate.sh`:

```fish
devcontainer up --workspace-folder . --docker-path podman --remove-existing-container
```

## VS Code / VSCodium

Install the **Dev Containers** extension, set `dev.containers.dockerPath` to
`podman` in settings, then **Reopen in Container**.

## Per-lab Python dependencies

The image ships Python + `uv`; per-lab deps stay scoped to each lab:

```sh
cd theme && uv venv && uv pip install -r requirements.txt
```

## Notes

- **`--userns=keep-id`** (in `devcontainer.json` `runArgs`) maps your host UID
  (1000) to the container's `vscode` user so workspace files you create stay
  owned by you, not root. If you ever switch to Docker, drop that arg.
- The workspace mounts at `/workspaces/JangLabs` inside the container.
- `devcontainer.json` is kept as **strict JSON, no comments** — the host's
  `syntax-check-touched.sh` hook validates `.json` with `jq`, which rejects
  JSONC. Rationale for each field lives here instead.
