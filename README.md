# Local AI

A fully installed local chat application for Windows and WSL. It provides a
FastAPI backend, a React + Vite interface managed with pnpm, SQLite configuration storage, automatic
GGUF model discovery, and lifecycle management for the official llama.cpp
runtime.

Release installers include the application runtime, Python packages, compiled
React UI, SQLite support, and a verified llama.cpp CPU fallback. End users do
not install Python, Node.js, pnpm, Git, GitHub CLI, or a database. The only
large user-supplied component is a licensed `.gguf` model.

## What is included

- Clean React/Vite chat interface with model controls and Local resources
  consolidated into Settings
- Local `.gguf` scanner with model size and selection controls
- Configurable context size, GPU layers, threads, parallel slots, RAM cache,
  flash attention, and automatic startup
- FastAPI REST API and built-in API documentation
- SQLite settings, searchable conversations, and model index under `data/`
- Local website/service resources with credentials kept in the OS keyring when available,
  or an encrypted owner-only local vault as the headless fallback
- Streaming chat with stop-generation, archive/delete, search, and secret-free JSON export
- Automatic public web research before every chat reply, with current-date context,
  source links, short-lived caching, bounded page retrieval, and private-network blocking
- Model-initiated local workspace tools for listing and reading files, creating folders,
  writing or editing files, moving or deleting paths, and running shell commands; every
  action requires explicit one-time approval and file operations stay inside the selected workspace
- Multi-file and folder context attachments with private local copies, PDF/Office/text
  extraction, SQLite full-text indexing, relevant-chunk retrieval, and per-file removal
- Local-first Cloud handoff with a progress state, capped Git/chat context, editable preview, and copy
- Live MCP server discovery and tool calls for stdio, Streamable HTTP, and
  legacy SSE, with direct support for Basic, bearer, API-key, custom-header,
  cookie, environment-variable, and OAuth authorization-code credentials
- Additional locally stored authentication templates for certificates, service
  accounts, SSH, and AWS setups that require a compatible MCP server/launcher
- Per-server MCP permissions, confirmation before tool execution, audit records,
  connection testing, capability summaries, and OAuth authorization code + PKCE
- Edit, duplicate, reconnect, or remove saved access for resources and MCP servers
- Guided OAuth configuration for GitHub, Gmail, Google Drive, Outlook, OneDrive,
  and Dropbox; provider registration and an MCP endpoint are still required
- Approved repository workspaces for Git-aware Cloud handoff context
- Local and MCP activity history with native expandable tool messages in chat
- Passphrase-encrypted `.laibak` backup and guarded configuration/conversation restore
- Live generation-speed and NVIDIA GPU telemetry with balanced, speed, quality,
  and low-memory presets
- GitHub-flavored Markdown, tables, highlighted code, copy/download controls,
  expandable tool output, and downloadable response files
- Managed llama.cpp start, stop, health, logs, and OpenAI-compatible chat proxy
- Loopback-only defaults: app `127.0.0.1:8181`, model `127.0.0.1:8180`
- Automated WSL/Linux and Windows setup scripts

The model, chat history, attachments, resources, and credentials remain local.
Automatic web research sends only the current question to a public search provider
and retrieves public HTTP/HTTPS pages; it never sends attached files, saved
credentials, configured resources, or earlier conversation messages.

## Install a release

Windows and WSL are separate operating environments and therefore receive
different release files. Do not install the WSL build as a native Windows app,
or copy either installation's database into the other while it is running.

### Native Windows

Download `Local-AI-Windows-Setup-X.Y.Z.exe` from the GitHub Releases page and
follow the machine-level wizard. Windows requests administrator approval once,
then installs the application under `C:\Program Files\Local AI` without opening
separate dependency installers. Each user’s private application data and models
live under `%LOCALAPPDATA%\Local AI`, where upgrades and uninstall preserve
them. The installer:

1. installs the compiled application;
2. reuses an existing `llama-server.exe` when available;
3. otherwise detects the GPU and quietly downloads the matching current
   official llama.cpp build with its published SHA-256 digest;
4. falls back to the bundled CPU runtime if optimization is unavailable;
5. initializes SQLite and registers a limited startup task for the signed-in user;
6. verifies the completed installation under Program Files in CI.

The wizard remains visible with an installation status while runtime detection
or download is in progress. A signed release avoids the unknown-publisher
warning; unsigned development builds can still trigger Windows SmartScreen.

### WSL

Download `Local-AI-WSL-Setup-X.Y.Z.run` inside WSL, then run:

```bash
chmod +x Local-AI-WSL-Setup-X.Y.Z.run
./Local-AI-WSL-Setup-X.Y.Z.run
```

The single file verifies its embedded payload and requests `sudo` once. It
installs the versioned application under `/opt/local-ai`, places the command in
`/usr/local/bin/local-ai`, stores private mutable data and models under
`/var/lib/local-ai`, installs and enables `/etc/systemd/system/local-ai.service`,
and registers a Windows sign-in trigger that wakes the detected WSL
distribution. systemd is required so the backend is always supervised. No
system Python, Node.js, pnpm, Git, or GitHub CLI is needed.

Place a `.gguf` file in the model folder shown by the app, open **Settings →
Model & runtime**, scan, select the model, and start it.

## Directory layout

```text
ai_project/
├── backend/                 FastAPI application
│   ├── app/
│   │   ├── services/        Model scanner and llama.cpp manager
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── main.py
│   │   └── run.py
│   └── requirements.txt
├── frontend/                React + Vite source and generated dist/
├── package.json             Root pnpm development commands
├── pnpm-lock.yaml           Reproducible frontend dependencies
├── pnpm-workspace.yaml      pnpm workspace definition
├── config/default.json      Safe defaults
├── data/                    Generated SQLite database
├── models/                  Put GGUF files here
├── runtime/logs/            llama.cpp output
├── scripts/setup.sh         WSL/Linux installation
├── scripts/setup.ps1        Windows installation
├── scripts/service.sh       WSL/Linux service management
├── scripts/windows-startup.ps1  Windows sign-in startup management
├── deploy/systemd/          User service and complete-stack target
├── run.sh
└── run.ps1
```

## WSL source installation for developers

Open Ubuntu/WSL in this directory and run:

```bash
chmod +x scripts/setup.sh run.sh
./scripts/setup.sh
```

The setup script:

1. Checks Python, Node.js, pnpm, and curl, installing missing Debian/Ubuntu
   packages when `apt-get` is available.
2. Installs the official llama.cpp runtime when it is not already available.
   The official installer detects CPU and GPU capabilities.
3. Creates `.venv` and installs the pinned Python dependencies.
4. Installs and compiles the React + Vite frontend with pnpm.
5. Creates the SQLite database and scans `models/`.

Then place a model in `models/` and start the app:

```bash
./run.sh
```

Open <http://127.0.0.1:8181>.

### Automatic WSL startup

The Linux setup installs a per-user systemd service when systemd is available.
It always starts the React/FastAPI application. During installation it detects
optional llama.cpp, embedding, file-watcher, and semantic-index user units and
adds only the units that actually exist on that computer to the stack target.
Manage the detected stack with:

```bash
./scripts/service.sh status
./scripts/service.sh start
./scripts/service.sh restart
./scripts/service.sh logs
```

For WSL, install the Windows sign-in trigger once from PowerShell:

```powershell
.\scripts\windows-startup.ps1 -Mode WSL
```

Windows cannot safely start a user's WSL distribution as the SYSTEM account
before sign-in. The scheduled task therefore runs ten seconds after the user's
Windows sign-in, wakes WSL, and asks systemd to start the complete Local AI
stack. The default WSL distribution and its configured default user are
detected automatically. systemd then supervises and restarts the Linux
processes installed on that computer.

## Windows source installation for developers

Keep the project on a Windows drive such as `C:\Users\you\ai_project`; do not
run the native Windows setup from a WSL UNC path. Open PowerShell in the project
directory and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
```

The script uses `winget` only when Python or Node.js is missing. It downloads
and runs the official hardware-detecting llama.cpp installer, creates a Windows
virtual environment, installs/builds the app, and initializes SQLite.

Place a `.gguf` model in `models\`, then run:

```powershell
.\run.ps1
```

Open <http://127.0.0.1:8181>.

To run a native Windows installation automatically at sign-in:

```powershell
.\scripts\windows-startup.ps1 -Mode Native
```

## First use

1. Open **Settings → Model & runtime**.
2. Select **Scan model directory** if your model is not already listed.
3. Choose a model.
4. Review **Settings → Host & performance**. On first start, the app detects
   the operating system, WSL status, CPU topology, available memory, GPU/backend,
   model size, storage, and installed runtime tools. It calculates conservative
   context, offload, thread, cache, and parallelism settings for that host.
5. Select **Start model** and wait for **Model ready**.
6. Use the blank chat composer.

Large contexts require substantial memory. If model loading fails, reduce
`Context`, `GPU layers`, or `Cache RAM MB`. Logs are stored at
`runtime/logs/llama-server.log`.

## Configuration

No `.env` file or manual path setup is required. Project, data, model, database,
home, WSL distribution, and optional-service paths are resolved on the current
computer rather than copied from the machine that built the package. The project uses
`127.0.0.1:8181` for the app, `127.0.0.1:8180` for llama.cpp, `models/` for GGUF
files, and `data/` for local state. It also searches the PATH, the official
llama.cpp installer location, common WSL build locations, and `runtime/` for the
llama.cpp executable.

Host recommendations are stored with a non-identifying hardware fingerprint.
They are recalculated after a CPU, memory, GPU, operating-system, or WSL-resource
change. A manual performance edit turns automatic tuning off; **Apply best
settings for this computer** enables it again. Explicit environment variables
always win.

Initial defaults are in `config/default.json`. Runtime changes made in the UI
are stored in `data/local-ai.db`. Advanced users can still provide process
environment variables; intentional overrides always take priority:

| Variable | Purpose |
|---|---|
| `LOCAL_AI_HOST` | App bind address |
| `LOCAL_AI_PORT` | App port |
| `LOCAL_AI_MODEL_HOST` | llama.cpp bind address |
| `LOCAL_AI_MODEL_PORT` | llama.cpp port |
| `LOCAL_AI_LLAMA_EXECUTABLE` | Explicit `llama`, `llama-server`, or `.exe` path |
| `LOCAL_AI_MODELS_DIR` | External models directory |
| `LOCAL_AI_DATA_DIR` | External database directory |
| `LOCAL_AI_DATABASE` | Explicit SQLite file |
| `LOCAL_AI_WORKSPACES_ROOT` | Root beneath which folders may be explicitly approved |

For privacy, keep both host settings on `127.0.0.1`. No cloud API key is
required, and the app does not download or upload model files.

## API

With the app running, interactive documentation is available at
<http://127.0.0.1:8181/api/docs>.

Important endpoints:

- `GET /api/health`
- `GET /api/config`
- `GET /api/system/profile`
- `POST /api/system/apply-recommended`
- `GET /api/models`
- `POST /api/models/scan`
- `POST /api/models/select`
- `GET|PATCH /api/settings`
- `GET|POST /api/resources`
- `PATCH /api/resources/{resource_id}`
- `POST /api/resources/{resource_id}/duplicate`
- `DELETE /api/resources/{resource_id}`
- `GET|POST /api/mcp-servers`
- `PATCH|DELETE /api/mcp-servers/{server_id}`
- `POST /api/mcp-servers/{server_id}/test`
- `POST /api/mcp-servers/{server_id}/call`
- `POST /api/mcp-servers/{server_id}/oauth/start`
- `GET|DELETE /api/mcp-audit`
- `GET|POST /api/workspaces`
- `PATCH|DELETE /api/workspaces/{workspace_id}`
- `GET|POST /api/conversations`
- `GET|PATCH|DELETE /api/conversations/{conversation_id}`
- `GET /api/context/capabilities`
- `GET|POST /api/conversations/{conversation_id}/context`
- `DELETE /api/conversations/{conversation_id}/context/{source_id}`
- `GET /api/runtime`
- `POST /api/runtime/start`
- `POST /api/runtime/stop`
- `GET /api/runtime/metrics`
- `POST /api/runtime/presets/{preset}`
- `POST /api/chat` and `POST /api/chat/stream`
- `POST /api/cloud-handoff`
- `GET /api/export` (never includes passwords, tokens, or vault contents)
- `POST /api/backup` and `POST /api/restore`

## Account connections

Provider wizards fill the documented authorization and token endpoints, but they
do not create provider applications or guess MCP server URLs. Register an OAuth
application with the provider, enter its client ID and approved localhost
redirect URI, enter the MCP server endpoint, save, then select **Connect**.
Credentials are encrypted locally, refreshed when a refresh token is available,
and exposed only to that MCP connection. **Remove access** deletes the local
credentials; use the provider's security page when provider-side revocation is
also required.

## Backups

Open **Settings → Backup**, choose a passphrase of at least ten characters, and
download the `.laibak` file. The encrypted backup contains settings,
conversations, approved workspaces, MCP records, resources, and credentials.
Attached file copies are intentionally not duplicated into backups; reattach
them after a restore when that conversation context is still needed.
Restore replaces current local data, requires a second confirmation, and should
be followed by an app restart. The passphrase cannot be recovered.

## Development and tests

```bash
.venv/bin/python -m pip install -r backend/requirements-dev.txt
PYTHONPATH=. .venv/bin/python -m pytest -q
pnpm install --frozen-lockfile
pnpm build
pnpm exec playwright install chromium
pnpm test:e2e
```

To use Vite development mode, run the backend on port 8181 and then:

```bash
pnpm dev
```

## Responsiveness architecture

The browser and API remain interactive while local work continues:

- llama.cpp runs as a separate below-normal-priority process, so model
  generation cannot block the React or FastAPI process;
- chat streams incremental NDJSON while the UI batches token rendering to a
  steady cadence instead of rerendering for every token;
- attachment uploads report transfer progress, then parse and index in bounded
  worker threads with limited concurrency and one-file-at-a-time memory use;
- database-heavy chat preparation, repository inspection, and Cloud handoff
  context gathering run outside the async event loop;
- settings-only data is loaded only when Settings opens, and large dialogs,
  Markdown rendering, and syntax highlighting are code-split;
- auto-scroll follows the answer only while the user remains near the bottom,
  so reading earlier content is not interrupted.

These controls favor UI/API latency over maximum batch throughput. Heavy jobs
show an explicit working state and remain cancellable where the underlying
operation supports cancellation.

## Build and publish releases

GitHub Actions contains independent Windows and WSL builders plus a tag-driven
release workflow. Pushing a tag such as `v1.2.0` stamps that version into both
compiled apps, performs platform smoke tests, exercises the WSL installer and
uninstaller, validates hashes, and publishes both installers with one combined
`SHA256SUMS.txt`. See [docs/RELEASING.md](docs/RELEASING.md).

## Updating

- Application dependencies are pinned in `backend/requirements.txt`,
  `frontend/package.json`, and `pnpm-lock.yaml`. Review release notes before
  changing them.
- The official llama.cpp installer supplies its current hardware-compatible
  build. Run the official installer again when you intentionally want to
  update llama.cpp.
- Back up the complete `data/` directory before changing database code. The
  encrypted fallback vault and its key are both required for recovery.

## Troubleshooting

- **No models found:** confirm the file ends in `.gguf` and is inside `models/`,
  then scan again.
- **llama.cpp not installed:** rerun the platform setup script.
- **Port already in use:** change `app_port` or `model_port` in
  `config/default.json` before first run, or update the SQLite setting.
- **Model immediately stops:** inspect `runtime/logs/llama-server.log` and lower
  the memory-related settings.
- **CUDA not used in WSL:** verify `nvidia-smi` works inside WSL, then reinstall
  llama.cpp so its installer can detect the GPU.
