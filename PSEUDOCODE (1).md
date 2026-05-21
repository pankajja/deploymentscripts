# SFS Deploy - Pseudo Code

## Starting Point
- Script changes its working directory to its own location
- Reads command line arguments
- Loads env.json file

---

## Command Line Arguments
- applRoot  : where the application is installed
- action    : deploy or validate
- env       : environment name e.g cit01
- release   : version number e.g 0.1.0
- type      : core or config or all
- envFolder : where env.json is kept
- component : tfg or pct or all

---

## main()
- call init()
- if action is deploy
    - if type is core   then call sfsDeploy()
    - if type is config then call sfsConfigDeploy()
    - if type is all    then call sfsDeploy() and sfsConfigDeploy()
- if action is validate then call validate()

---

## init()
- parse all command line arguments
- if component not given set it to all
- if envFolder not given set it to applRoot/env
- check applRoot exists else exit
- load env.json into envInfo variable

---

## sfsDeploy()
- call clean()
- check tar file SFS-<release>.tar.gz exists else exit
- create folder applRoot/SFS-<release>
- extract tar file into applRoot
- check TFG and PCT folders exist inside extracted folder else exit
- create symlink  applRoot/SFS pointing to applRoot/SFS-<release>
- call fixPermissions()

---

## sfsConfigDeploy()
- check applRoot/SFS-<release> exists else exit
- create folder applRoot/config-<release>
- call configure()
- create symlink applRoot/config pointing to applRoot/config-<release>
- call fixPermissions()

---

## configure()
- for each component call configureSfsComponent()

---

## configureSfsComponent()
- read config.json from staging config folder
- read application.template.properties from applRoot/SFS-<release>/<comp>
- for each param listed in config.json
    - split param by dot to get category and name
      e.g  coredb.dbPort  →  category=coredb  name=dbPort
    - get value from env.json using category and name
      e.g  envInfo[coredb][dbPort]  =  10000
    - replace param placeholder in template with actual value
- write final content as application.properties
  into applRoot/config-<release>/<comp> folder

---

## clean()
- remove applRoot/SFS symlink if exists
- remove applRoot/SFS-<release> folder if exists
- remove applRoot/config symlink if exists
- remove applRoot/config-<release> folder if exists

---

## validate()
- check applRoot/SFS-<release> folder exists
- check applRoot/SFS symlink exists
- check applRoot/config-<release> folder exists
- check applRoot/config symlink exists
- for each component
    - check component folder exists inside SFS-<release>
    - check component folder exists inside config-<release>
    - check application.properties file exists inside config-<release>/<comp>
- print success message

---

## fixPermissions()
- get list of folders that exist from SFS-<release> and config-<release>
- run chmod 750 on those folders
- run chown with current user on those folders

---

## Utility Functions

### readJsonData()
- check file exists else exit
- read and return json content

### checkFileExists()
- if file not found print error and exit

### createFolder()
- if folder not present run mkdir

### executeCommand()
- if echoVal is set prepend it to command (used for dry run)
- run the command and return status and output

### getComponents()
- if component is all return TFG and PCT
- else return whatever component was passed

### log()
- print current timestamp with log level and message
