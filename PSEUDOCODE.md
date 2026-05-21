# sfs_deploy_new.py — Pseudo Code

---

## GLOBALS
```
workdir          = script's own directory   (os.chdir on startup)
KNOWN_COMPONENTS = [TFG, PCT]
pa               = None                     (CLI args namespace)
envInfo          = None                     (env.json content)
echoVal          = ""                       (set to "echo" for dry-run)
```

---

## MAIN FLOW

```
main()
    │
    ├── init()
    │
    ├── IF action == "deploy"
    │       IF type == "core"    → sfsDeploy()
    │       IF type == "config"  → sfsConfigDeploy()
    │       IF type == "all"     → sfsDeploy()
    │                              sfsConfigDeploy()
    │
    └── IF action == "validate"  → validate()
```

---

## FUNCTION: init()
```
PARSE cli args
    --applRoot   (required)  deployment home directory
    --action     (required)  deploy / validate
    --env        (required)  environment name e.g. cit01
    --release    (required)  release version  e.g. 0.1.0
    --type       (optional)  core / config / all  [default: all]
    --envFolder  (optional)  path to env.json dir [default: applRoot/env]
    --component  (optional)  tfg / pct / all      [default: all]

SET defaults
    component = all           IF not provided
    envFolder = applRoot/env  IF not provided

NORMALISE paths
    applRoot  → ensure trailing slash
    envFolder → remove trailing slash

CHECK applRoot exists           EXIT if not

LOAD envInfo = readJsonData(envFolder/env.json)
```

---

## FUNCTION: sfsDeploy()      [--type core]
```
clean()

CHECK SFS-<release>.tar.gz exists in staging dir    EXIT if not

CREATE applRoot/SFS-<release>/

EXTRACT SFS-<release>.tar.gz → applRoot/            EXIT if fails

FOR each component in getComponents()
    CHECK applRoot/SFS-<release>/<COMP>/ exists      EXIT if not

CREATE symlink
    applRoot/SFS → applRoot/SFS-<release>

fixPermissions()
```

---

## FUNCTION: sfsConfigDeploy()     [--type config]
```
CHECK applRoot/SFS-<release>/ exists                EXIT if not

CREATE applRoot/config-<release>/

configure()

CREATE symlink
    applRoot/config → applRoot/config-<release>

fixPermissions()
```

---

## FUNCTION: configure()
```
FOR each component in getComponents()
    configureSfsComponent(comp)
```

---

## FUNCTION: configureSfsComponent(comp)
```
SET paths
    compConfigJson   = ./config/<COMP>/config.json
    templateFilePath = applRoot/SFS-<release>/<COMP>/application.template.properties
    compOutputDir    = applRoot/config-<release>/<COMP>/
    outputFilePath   = applRoot/config-<release>/<COMP>/application.properties

READ compConfigJson    → configData         EXIT if not found
READ templateFilePath  → fileData           EXIT if not found

FOR each param in configData["application.template.properties"]
    category = param.split('.')[0]          e.g. "coredb"
    name     = param.split('.')[1]          e.g. "dbPort"
    value    = envInfo[category][name]      e.g. "10000"
    REPLACE  param → value in fileData

CREATE compOutputDir   IF not exists

WRITE fileData → outputFilePath             (application.properties)
```

---

## FUNCTION: clean()
```
IF applRoot/SFS exists          → REMOVE (symlink)
IF applRoot/SFS-<release> exists → REMOVE (folder)
IF applRoot/config exists       → REMOVE (symlink)
IF applRoot/config-<release> exists → REMOVE (folder)
```

---

## FUNCTION: validate()
```
CHECK applRoot/SFS-<release>/    exists    EXIT + ERROR if not
CHECK applRoot/SFS               exists    EXIT + ERROR if not
CHECK applRoot/config-<release>/ exists    EXIT + ERROR if not
CHECK applRoot/config            exists    EXIT + ERROR if not

FOR each component in getComponents()
    CHECK applRoot/SFS-<release>/<COMP>/                   exists
    CHECK applRoot/config-<release>/<COMP>/                exists
    CHECK applRoot/config-<release>/<COMP>/application.properties exists
    EXIT + ERROR if any missing

PRINT "Successfully validated the SFS deployment"
```

---

## FUNCTION: fixPermissions()
```
SET folders = existing folders from
    [applRoot/SFS-<release>, applRoot/config-<release>]

IF folders not empty
    chmod -R 750  <folders>
    chown -R <current_user>  <folders>
```

---

## UTILITY FUNCTIONS

```
readJsonData(jsonFile)
    checkFileExists(jsonFile)
    RETURN json.load(jsonFile)

checkFileExists(fileName)
    IF not exists → LOG error + EXIT

createFolder(folder)
    IF not exists → mkdir -p <folder>

executeCommand(cmd)
    IF echoVal != "" → PREPEND echoVal to cmd
    RUN cmd via subprocess.getstatusoutput
    RETURN (status, result)

getComponents()
    IF component == "all" → RETURN KNOWN_COMPONENTS
    ELSE                  → RETURN [comp.upper() for comp in pa.component]

log(logLevel, msg)
    PRINT timestamp + logLevel + msg
```

---

## PLACEHOLDER REPLACEMENT — KEY LOGIC

```
param    = "coredb.dbPort"
           │       │
           │       └── name     = "dbPort"
           └────────── category = "coredb"

value = envInfo["coredb"]["dbPort"]   →  "10000"

fileData.replace("coredb.dbPort", "10000")
```
