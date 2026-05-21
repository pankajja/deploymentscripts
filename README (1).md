# sfs_deploy_new.py — SFS Deployment Script

## Overview
Python 3 deployment script for SFS (Smart Financial Services) releases.
Handles core artifact deployment, config file generation, and post-deploy validation.

---

## Repo Structure (Staging Directory)

```
sfs-deploy/
    ├── sfs_deploy_new.py          ← deployment script
    ├── config/
    │    ├── TFG/
    │    │    └── config.json      ← placeholder list for TFG
    │    └── PCT/
    │         └── config.json      ← placeholder list for PCT
    └── SFS-0.1.0.tar.gz           ← artifact (placed here before deploy)
```

---

## Prerequisites

| What | Where |
|------|-------|
| `SFS-<release>.tar.gz` | Staging directory (same as script) |
| `config/<COMP>/config.json` | Staging directory (same as script) |
| `env.json` | `applRoot/env/env.json` (on deployment server) |

---

## CLI Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--applRoot` | Yes | Deployment home directory e.g. `/cls/appl` |
| `--action` | Yes | `deploy` or `validate` |
| `--env` | Yes | Environment name e.g. `cit01` |
| `--release` | Yes | SFS release version e.g. `0.1.0` |
| `--type` | No | `core` / `config` / `all` (default: `all`) |
| `--envFolder` | No | Path to `env.json` dir (default: `applRoot/env`) |
| `--component` | No | `tfg` / `pct` / `all` (default: `all`) |

---

## Example Commands

```bash
# Full deployment (core + config)
python3 sfs_deploy_new.py \
    --applRoot /cls/appl \
    --action deploy \
    --env cit01 \
    --release 0.1.0 \
    --type all \
    --component all

# Core only
python3 sfs_deploy_new.py \
    --applRoot /cls/appl \
    --action deploy \
    --env cit01 \
    --release 0.1.0 \
    --type core

# Config only
python3 sfs_deploy_new.py \
    --applRoot /cls/appl \
    --action deploy \
    --env cit01 \
    --release 0.1.0 \
    --type config

# Specific component
python3 sfs_deploy_new.py \
    --applRoot /cls/appl \
    --action deploy \
    --env cit01 \
    --release 0.1.0 \
    --type all \
    --component tfg

# Validate after deployment
python3 sfs_deploy_new.py \
    --applRoot /cls/appl \
    --action validate \
    --env cit01 \
    --release 0.1.0
```

---

## Pseudo Code

```
PROGRAM sfs_deploy_new
    SET workdir = script's own directory
    SET KNOWN_COMPONENTS = [TFG, PCT]

    ─────────────────────────────────────
    FUNCTION main()
    ─────────────────────────────────────
        init()
        IF action == deploy
            IF type == core  → sfsDeploy()
            IF type == config → sfsConfigDeploy()
            IF type == all   → sfsDeploy() + sfsConfigDeploy()
        IF action == validate → validate()

    ─────────────────────────────────────
    FUNCTION init()
    ─────────────────────────────────────
        PARSE cli args (applRoot, action, env, release, type, envFolder, component)
        SET defaults (component=all, envFolder=applRoot/env)
        NORMALISE trailing slashes on applRoot, envFolder
        CHECK applRoot exists
        LOAD envInfo from envFolder/env.json

    ─────────────────────────────────────
    FUNCTION sfsDeploy()           [--type core]
    ─────────────────────────────────────
        clean()
        CHECK SFS-<release>.tar.gz exists in staging dir
        CREATE applRoot/SFS-<release>/
        EXTRACT SFS-<release>.tar.gz → applRoot/
        FOR each component
            VERIFY applRoot/SFS-<release>/<COMP>/ exists
        CREATE symlink applRoot/SFS → applRoot/SFS-<release>
        fixPermissions()

    ─────────────────────────────────────
    FUNCTION sfsConfigDeploy()     [--type config]
    ─────────────────────────────────────
        CHECK applRoot/SFS-<release>/ exists
        CREATE applRoot/config-<release>/
        configure()
        CREATE symlink applRoot/config → applRoot/config-<release>
        fixPermissions()

    ─────────────────────────────────────
    FUNCTION configure()
    ─────────────────────────────────────
        FOR each component
            configureSfsComponent(comp)

    ─────────────────────────────────────
    FUNCTION configureSfsComponent(comp)
    ─────────────────────────────────────
        READ  config/<COMP>/config.json          ← from staging repo
        READ  applRoot/SFS-<release>/<COMP>/
              application.template.properties    ← from extracted tar
        FOR each param in config.json
            category = param.split('.')[0]       e.g. "coredb"
            name     = param.split('.')[1]       e.g. "dbPort"
            value    = envInfo[category][name]   e.g. "10000"
            REPLACE  param with value in template content
        WRITE applRoot/config-<release>/<COMP>/application.properties

    ─────────────────────────────────────
    FUNCTION clean()
    ─────────────────────────────────────
        REMOVE applRoot/SFS       (symlink)
        REMOVE applRoot/SFS-<release>/
        REMOVE applRoot/config    (symlink)
        REMOVE applRoot/config-<release>/

    ─────────────────────────────────────
    FUNCTION validate()
    ─────────────────────────────────────
        CHECK applRoot/SFS-<release>/   exists
        CHECK applRoot/SFS              symlink exists
        CHECK applRoot/config-<release>/ exists
        CHECK applRoot/config            symlink exists
        FOR each component
            CHECK applRoot/SFS-<release>/<COMP>/            exists
            CHECK applRoot/config-<release>/<COMP>/         exists
            CHECK applRoot/config-<release>/<COMP>/
                  application.properties                    exists
        PRINT success

    ─────────────────────────────────────
    FUNCTION fixPermissions()
    ─────────────────────────────────────
        FOR each folder that exists
            chmod -R 750  applRoot/SFS-<release>/
                          applRoot/config-<release>/
            chown -R <user> (same folders)
```

---

## Placeholder Replacement — How It Works

```
config.json                   env.json                     application.template.properties
─────────────────             ────────────────────         ───────────────────────────────
"application.                 {                            app.root=env.applRoot
 template.properties":[         "env": {                  spring.datasource.
  "env.applRoot",                 "applRoot":"/cls/appl"   portNumber=coredb.dbPort
  "coredb.dbPort",              },                        spring.datasource.
  ...                           "coredb": {                databaseName=coredb.dbName
]                                 "dbPort": "10000"        ...
                                },
                              }
        │                           │                              │
        └───────── split('.')  ─────┘                             │
                  [category][name]                                 │
                       │                                          │
                       └──────────── replace() ───────────────────┘
                                          │
                                          ▼
                              application.properties
                              ──────────────────────
                              app.root=/cls/appl
                              spring.datasource.portNumber=10000
                              spring.datasource.databaseName=CITCOR
```

---

## Output Directory Structure (after --type all)

```
applRoot/
    ├── SFS-0.1.0/                          ← extracted tar
    │    ├── TFG/
    │    │    └── application.template.properties
    │    └── PCT/
    │         └── application.template.properties
    │
    ├── SFS  ──────────────► SFS-0.1.0/     ← symlink
    │
    ├── config-0.1.0/                        ← configured files
    │    ├── TFG/
    │    │    └── application.properties     ← placeholders replaced
    │    └── PCT/
    │         └── application.properties     ← placeholders replaced
    │
    ├── config  ────────────► config-0.1.0/  ← symlink
    │
    └── env/
         └── env.json
```

---

## Adding a New Component

1. Add component name to `KNOWN_COMPONENTS` in the script:
```python
KNOWN_COMPONENTS = ['TFG', 'PCT', 'NEW_COMP']
```
2. Add `config/NEW_COMP/config.json` to the staging repo
3. Ensure `NEW_COMP/application.template.properties` is inside the tar
