# SFS Deployment & Operations Scripts

## Overview

| Script | Language | Purpose |
|---|---|---|
| `sfs_deploy_new.py` | Python 3 | Core and config deployment of SFS application |
| `sfs_ops.py` | Python 3 | Keytab generation, stop/start/status of SFS components |

---

## Directory Structure

### Staging Directory (where scripts run from)
```
sfs-deploy-0.1.2/
    ├── sfs_deploy_new.py
    ├── sfs_ops.py
    └── config/
            ├── tfg/
            │    ├── config.json
            │    ├── application.template.properties
            │    └── SQLJDBCDriver.template.conf
            ├── pct/
            │    ├── config.json
            │    ├── application.template.properties
            │    └── SQLJDBCDriver.template.conf
            └── su/
                 ├── config.json
                 ├── application.template.properties
                 └── SQLJDBCDriver.template.conf
```

### Deployment Server
```
/cls/appl/                          ← applRoot
    ├── sfs-app-0.1.2/              ← core deployment
    │    ├── tfg-0.1.2/
    │    ├── tfg  →  tfg-0.1.2
    │    ├── pct-0.1.2/
    │    ├── pct  →  pct-0.1.2
    │    ├── su-0.1.2/
    │    └── su   →  su-0.1.2
    ├── sfs-app  →  sfs-app-0.1.2   ← symlink
    ├── sfsconfig-0.1.2/            ← config deployment
    │    ├── tfg/
    │    │    ├── application.properties
    │    │    └── SQLJDBCDriver.conf
    │    ├── pct/
    │    │    ├── application.properties
    │    │    └── SQLJDBCDriver.conf
    │    └── su/
    │         ├── application.properties
    │         └── SQLJDBCDriver.conf
    ├── sfsconfig  →  sfsconfig-0.1.2
    ├── env/
    │    └── envInfo.json
    ├── logs/                        ← log files
    │    ├── sfs_deploy_YYYYMMDD_HHMMSS.log
    │    └── sfs_ops_YYYYMMDD_HHMMSS.log
    └── sfsbin/
         └── sfs_ops.py

/cls/release/                       ← release artefacts
    ├── sfs-app-0.1.2.tar
    └── sfs-deploy-0.1.2.tar
```

---

## sfs_deploy_new.py

### Purpose
Handles core and config deployment of the SFS application.

### Prerequisites
- Python 3.x
- `applRoot` directory exists (`/cls/appl/`)
- `envInfo.json` available at `applRoot/env/` (for config/all deploy)
- `sfs-app-<release>.tar` available at `/cls/release/`
- `config/<comp>/config.json` and template files in staging directory

### CLI Arguments

| Argument | Group | Description |
|---|---|---|
| `--applRoot` | Required | Deployment home directory e.g. `/cls/appl` |
| `--action` | Required | `deploy` or `validate` |
| `--release` | Required | Release version e.g. `0.1.2` |
| `--type` | Required | `core` / `config` / `all` |
| `--envFolder` | Conditional | Path to `envInfo.json` dir (required for config/all) |
| `--releasePath` | Optional | Path to tar file (default: `/cls/release`) |
| `--component` | Optional | `tfg` / `pct` / `su` / `all` (default: `all`) |

### Example Commands

```bash
# Core deployment only
python3 sfs_deploy_new.py \
    --applRoot /cls/appl \
    --action deploy \
    --release 0.1.2 \
    --type core \
    --component all

# Config deployment only
python3 sfs_deploy_new.py \
    --applRoot /cls/appl \
    --action deploy \
    --release 0.1.2 \
    --type config \
    --envFolder /cls/appl/env \
    --component all

# Full deployment (core + config)
python3 sfs_deploy_new.py \
    --applRoot /cls/appl \
    --action deploy \
    --release 0.1.2 \
    --type all \
    --envFolder /cls/appl/env \
    --component all

# Specific component only
python3 sfs_deploy_new.py \
    --applRoot /cls/appl \
    --action deploy \
    --release 0.1.2 \
    --type all \
    --envFolder /cls/appl/env \
    --component tfg
```

### Known Components
```python
KNOWN_COMPONENTS = ['tfg', 'pct', 'su']
```

### config.json Structure
```json
{
    "application.template.properties": [
        "env.applRoot",
        "env.environment",
        "server.port"
    ],
    "SQLJDBCDriver.template.conf": [
        "db.keyTabFilePath",
        "db.userDomain"
    ]
}
```

### envInfo.json Structure
```json
{
    "tfg": {
        "env":    { "applRoot": "/cls/appl", "environment": "cit01" },
        "coredb": { "dbName": "CITCOR", "dbPort": "10000", "userName": "netbs1dbc" },
        "server": { "port": "8080" },
        "db":     { "keyTabFilePath": "/cls/appl/env/rds_usr_keytab/sfsdbcit1_auto.keytab",
                    "userDomain": "sfsdbcit1@CLSNONPROD.LOCAL" }
    },
    "pct": { ... },
    "su":  { ... }
}
```

### Log File
```
/cls/appl/logs/sfs_deploy_YYYYMMDD_HHMMSS.log
```
- File → DEBUG + INFO (detailed)
- Console → INFO only (minimal)

---

## sfs_ops.py

### Purpose
Handles keytab generation and stop/start/status of SFS components (TFG, PCT, StatementUtility).

### Prerequisites
- Python 3.x
- `$APP_HOME` environment variable set to `/cls/appl/sfs`
- `$APP_CONFIG` environment variable set to `/cls/appl/sfsconfig`
- `$JAVA_HOME` environment variable set
- Delinea enrollment active on server (for keytab action)
- Script copied to `/cls/appl/sfsbin/`

### CLI Arguments

| Argument | Group | Description |
|---|---|---|
| `--action` | Required | `keytab` / `stop` / `start` / `status` |
| `--env` | Conditional | Environment e.g. `cit01` (required for keytab/start) |
| `--dbUser` | Conditional | DB username e.g. `sfsdbcit1` (required for keytab/start) |
| `--component` | Optional | `tfg` / `pct` / `su` / `all` (default: `all`) |

### Example Commands

```bash
# Generate keytab only
./sfs_ops.py --action keytab --env cit01 --dbUser sfsdbcit1

# Stop all components (su → pct → tfg)
./sfs_ops.py --action stop

# Stop specific component
./sfs_ops.py --action stop --component su

# Start all (keytab → tfg → pct → su)
./sfs_ops.py --action start --env cit01 --dbUser sfsdbcit1

# Start specific component
./sfs_ops.py --action start --env cit01 --dbUser sfsdbcit1 --component tfg

# Status of all components
./sfs_ops.py --action status

# Status of specific component
./sfs_ops.py --action status --component pct
```

### Component Details

| Component | Process Name | Start Script | Stop Script |
|---|---|---|---|
| `tfg` | `TemplateFileGenerator` | `start_tfg.sh` | `stop_tfg.sh` |
| `pct` | `PCT` | `start_pct.sh` | `stop_pct.sh` |
| `su` | `statementutility` | `start_su.sh` | `stop_su.sh` |

### Stop/Start Order

```
Stop order  : su  →  pct  →  tfg
Start order : tfg →  pct  →  su  (keytab generated first)
```

### Domain Logic
```
cit*, sit*, uat*  →  CLSNONPROD.LOCAL
prod*             →  CLSPROD.LOCAL
```

### Status Output Example
```
COMPONENT            STATUS     PID
---------------------------------------------
TFG                  RUNNING    12345
PCT                  STOPPED    -
SU                   RUNNING    12346
```

### Log File
```
/cls/appl/logs/sfs_ops_YYYYMMDD_HHMMSS.log
```
- File → DEBUG + INFO (detailed)
- Console → INFO only (minimal)

---

## Adding a New Component

### 1. `sfs_deploy_new.py`
```python
KNOWN_COMPONENTS = ['tfg', 'pct', 'su', 'new_comp']
```

### 2. `sfs_ops.py`
```python
KNOWN_COMPONENTS    = ['tfg', 'pct', 'su', 'new_comp']
COMP_PROCESS_MAP    = { ..., 'new_comp': 'NewCompProcessName' }
STOP_ORDER          = ['new_comp', 'su', 'pct', 'tfg']
START_ORDER         = ['tfg', 'pct', 'su', 'new_comp']
```

### 3. Add config files in staging
```
config/new_comp/
    ├── config.json
    ├── application.template.properties
    └── SQLJDBCDriver.template.conf
```

### 4. Add section in `envInfo.json`
```json
{
    "new_comp": {
        "env": { ... },
        "server": { "port": "xxxx" }
    }
}
```
