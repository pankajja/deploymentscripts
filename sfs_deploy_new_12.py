#!/usr/bin/python3

import json, sys, fileinput, datetime, time
import os, shutil, collections
import argparse, socket, getpass
import subprocess, inspect

from pprint import pprint

# ─────────────────────────────────────────────
# Startup — change working dir to script's own
# staging directory so all relative paths
# (tar, config/) resolve correctly regardless
# of where the script is called from
# ─────────────────────────────────────────────
stagingDir = os.path.dirname(os.path.realpath(__file__))
os.chdir(stagingDir)

localHostName = socket.gethostname()

# echoVal: set to "echo" for dry-run/debug mode, "" for live
echoVal = ""

# Global state
pa      = None
envInfo = None

# Known components — always use base names without version
# e.g. 'tfg' not 'tfg-0.1.0' — version is appended by the code
KNOWN_COMPONENTS = ['tfg', 'pct']


# ─────────────────────────────────────────────
# Utility Functions
# ─────────────────────────────────────────────

def readJsonData(jsonFile):
    """Check file exists, print path, then read and parse JSON."""
    checkFileExists(jsonFile)
    print(jsonFile)
    with open(jsonFile) as dataFile:
        jsonData = json.load(dataFile)
    return jsonData


def log(logLevel, msg):
    """Timestamped logger — prints TIMESTAMP: LEVEL: message."""
    timeSuffix = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
    print(timeSuffix)
    print(str(timeSuffix) + ': ' + logLevel + ': ' + msg)


def executeCommand(cmd):
    """
    Run a shell command using getstatusoutput.
    If echoVal is set, prepend it (e.g. 'echo') for dry-run mode.
    Returns (status, result).
    """
    if echoVal != "":
        cmd = echoVal + " " + cmd

    log('DEBUG', cmd)
    (status, result) = subprocess.getstatusoutput(cmd)
    log('DEBUG', 'Command Status: ' + str(status))
    if result is not None and len(result) > 0:
        log('DEBUG', 'Console Output: ' + ''.join(result))
    return status, result


def createFolder(folder):
    """Create a directory (mkdir -p) if it does not exist."""
    if not os.path.exists(folder):
        log('DEBUG', 'Creating ' + folder)
        cmd = 'mkdir -p ' + folder
        executeCommand(cmd)


def checkFileExists(fileName):
    """Exit with error if a required file is missing."""
    if not os.path.exists(fileName):
        log('DEBUG', 'ERROR: ' + fileName + " doesn't exist. Please refer to the deployment guide")
        sys.exit(1)


def getEnvInfo(category, name):
    """Safe accessor for nested envInfo keys — returns None if not found."""
    global envInfo
    if envInfo is None:
        return None
    if category in envInfo and name in envInfo[category]:
        return envInfo[category][name]
    return None


# ─────────────────────────────────────────────
# Component Resolution
# ─────────────────────────────────────────────

def getComponents():
    """
    Resolve the list of components to deploy.
    --component all      -> all known components [tfg, pct]
    --component tfg      -> ['tfg']
    --component pct tfg  -> ['pct', 'tfg']
    """
    if pa.component is None or pa.component == ['all']:
        return KNOWN_COMPONENTS
    # Normalise to lowercase to match directory names tfg / pct
    return [c.lower() for c in pa.component]


# ─────────────────────────────────────────────
# Clean  (aligned with reference clean())
# ─────────────────────────────────────────────

def clean():
    """
    Remove existing release folder and symlink before fresh deploy.
    Mirrors reference code clean() pattern.
    """
    log('INFO', 'clean()')

    sfsReleaseFolder = pa.applRoot + 'sfs-app-' + pa.release   # applRoot/sfs-app-0.1.0
    sfsLink          = pa.applRoot + 'sfs-app'                 # applRoot/sfs-app
    configFolder     = pa.applRoot + 'config-' + pa.release    # applRoot/config-0.1.0
    configLink       = pa.applRoot + 'config'                  # applRoot/config

    # Remove sfs-app symlink if exists
    if os.path.exists(sfsLink):
        cmd = 'rm -rf ' + sfsLink
        executeCommand(cmd)

    # Remove sfs-app release folder if exists
    if os.path.exists(sfsReleaseFolder):
        cmd = 'rm -rf ' + sfsReleaseFolder
        executeCommand(cmd)

    # Remove config symlink if exists
    if os.path.exists(configLink):
        cmd = 'rm -rf ' + configLink
        executeCommand(cmd)

    # Remove config release folder if exists
    if os.path.exists(configFolder):
        cmd = 'rm -rf ' + configFolder
        executeCommand(cmd)


# ─────────────────────────────────────────────
# Configure  (aligned with reference configure())
# ─────────────────────────────────────────────

def configure():
    """
    Config deployment — for each component:
      a. Read config/<COMP>/config.json from staging repo
      b. Read application.template.properties from extracted SFS dir
      c. Replace dot-notation placeholders with values from env.json
      d. Write application.properties -> applRoot/config-<release>/<COMP>/
    Mirrors reference code configure() -> configuretradeapi() pattern.
    """
    log('INFO', 'configure()')

    components = getComponents()
    for comp in components:
        configureSfsComponent(comp)


def configureSfsComponent(comp):
    """
    Configure a single SFS component — mirrors reference configuretradeapi().
    Reads template, replaces placeholders, writes application.properties.
    """
    log('INFO', 'configureSfsComponent: ' + comp)

    configReleaseDir = 'config-' + pa.release                         # config-0.1.0
    configTargetDir  = pa.applRoot + configReleaseDir                 # applRoot/config-0.1.0
    compOutputDir    = configTargetDir + '/' + comp                   # applRoot/config-0.1.0/pct
    outputFilePath   = compOutputDir   + '/application.properties'    # final output

    # Resolve config folder — try base name first e.g. config/pct/
    # if not found try versioned name e.g. config/pct-0.1.0/
    compConfigDir = './config/' + comp
    if not os.path.exists(compConfigDir):
        compConfigDir = './config/' + comp + '-' + pa.release
        if not os.path.exists(compConfigDir):
            log('DEBUG', 'ERROR: config folder not found for component: ' + comp
                + ' — tried ./config/' + comp + ' and ./config/' + comp + '-' + pa.release)
            sys.exit(1)
    log('INFO', 'Using config folder: ' + compConfigDir)

    compConfigJson   = compConfigDir + '/config.json'
    templateFilePath = compConfigDir + '/application.template.properties'

    # Step a: Read config.json from staging repo
    log('INFO', 'Reading config.json: ' + compConfigJson)
    configData = readJsonData(compConfigJson)

    # Step b: Read application.template.properties from staging repo
    log('INFO', 'Reading template file: ' + templateFilePath)
    checkFileExists(templateFilePath)
    with open(templateFilePath) as f:
        fileData = f.read()
    f.close()

    # Step c: Replace dot-notation placeholders using envInfo
    #
    #   config.json lists params like "env.applRoot", "coredb.dbPort"
    #   Split on '.' -> category = "env",    name = "applRoot"
    #                -> envInfo["env"]["applRoot"] = "/cls/appl"
    #   Replace "env.applRoot" in template with "/cls/appl"
    #
    templateFileName = 'application.template.properties'
    if templateFileName not in configData:
        log('DEBUG', 'ERROR: No param list found for ' + templateFileName
            + ' in ' + compConfigJson)
        sys.exit(1)

    log('INFO', 'Replacing placeholders for component: ' + comp)
    for param in configData[templateFileName]:
        category = param.split('.')[0]    # e.g. "env"
        name     = param.split('.')[1]    # e.g. "applRoot"

        # Safe lookup — gives clear error if param not found in envInfo
        value = getEnvInfo(category, name)
        if value is None:
            log('DEBUG', 'ERROR: No value found in envInfo for param: '
                + param + ' (category=' + category + ', name=' + name + ')')
            sys.exit(1)
        print(param, value)
        fileData = fileData.replace(param, value)

    # Step d: Write application.properties to config release dir
    createFolder(compOutputDir)
    log('INFO', 'Configuring ' + outputFilePath)
    with open(outputFilePath, 'w') as f:
        f.write(fileData)
    f.close()

    log('INFO', 'Component ' + comp + ' configured successfully.')


# ─────────────────────────────────────────────
# Fix Permissions  (aligned with reference fixPermissions())
# ─────────────────────────────────────────────

def fixPermissions():
    """
    Apply chmod and chown on deployed folders that exist.
    Mirrors reference code fixPermissions() pattern.
    """
    log('INFO', 'fixPermissions()')

    allFolders = [
        pa.applRoot + 'sfs-app-' + pa.release,   # applRoot/sfs-app-0.1.0
        pa.applRoot + 'config-'  + pa.release,   # applRoot/config-0.1.0
    ]

    # Only act on folders that actually exist at this point
    folders = [f for f in allFolders if os.path.exists(f)]

    if not folders:
        log('DEBUG', 'No folders to apply permissions on.')
        return

    # Apply permissions
    cmd = 'chmod -R 750 ' + ' '.join(folders)
    executeCommand(cmd)

    # Apply ownership
    cmd = 'chown -R ' + getpass.getuser() + ' ' + ' '.join(folders)
    executeCommand(cmd)


# ─────────────────────────────────────────────
# Core Deployment  (--type core)
# ─────────────────────────────────────────────

def sfsDeploy():
    """
    Core deployment — handles 3 levels of tar extraction:
      Level 1: sfs-app-0.1.0.tar           (outer tar)
      Level 2: sfs-tfg-0.1.0.tar           (component tar inside level 1)
      Level 3: tfg.tar or pct-0.1.0.tar    (inner tar inside level 2)

      1. clean()           — remove old release + symlinks
      2. Extract Level 1   — to tmp_extract
      3. Find Level 2 tars — sfs-tfg-0.1.0.tar, sfs-pct-0.1.0.tar
      4. Extract Level 2   — each to its own temp subdir
      5. Find Level 3 tars — tfg.tar, pct-0.1.0.tar
      6. Extract Level 3   — into applRoot/sfs-app-<release>/
      7. Cleanup           — guaranteed via try/finally
      8. Rename + symlink  — tfg -> tfg-0.1.0, pct -> pct-0.1.0
      9. Create top symlink — applRoot/sfs-app -> applRoot/sfs-app-<release>
     10. fixPermissions()
    """
    log('INFO', 'deploy()')
    clean()

    sfsReleaseDir  = 'sfs-app-' + pa.release                 # sfs-app-0.1.0
    tarFileName    = sfsReleaseDir + '.tar'                   # sfs-app-0.1.0.tar
    sfsTargetDir   = pa.applRoot + sfsReleaseDir              # applRoot/sfs-app-0.1.0
    sfsLink        = pa.applRoot + 'sfs-app'                  # applRoot/sfs-app
    tempExtractDir = stagingDir + '/tmp_extract'              # temp staging area

    # Step 1: Verify outer tar exists in staging directory
    log('INFO', 'Checking tar artifact: ' + tarFileName)
    checkFileExists('./' + tarFileName)

    # Step 2: Create temp dir — remove stale content from previous run
    if os.path.exists(tempExtractDir):
        shutil.rmtree(tempExtractDir)
    createFolder(tempExtractDir)

    try:
        # Step 3: Extract Level 1 — outer tar into temp dir
        log('INFO', 'Extracting Level 1 tar: ' + tarFileName)
        cmd = 'tar -xf ' + tarFileName + ' -C ' + tempExtractDir
        status, result = executeCommand(cmd)
        if status != 0:
            log('DEBUG', 'ERROR: Failed to extract Level 1 tar: ' + tarFileName)
            sys.exit(1)
        log('INFO', 'Level 1 extraction successful')

        # Step 4: Find Level 2 tars — sfs-tfg-0.1.0.tar, sfs-pct-0.1.0.tar
        level2Tars = []
        for root, dirs, files in os.walk(tempExtractDir):
            for f in files:
                if f.endswith('.tar'):
                    level2Tars.append(os.path.join(root, f))

        if not level2Tars:
            log('DEBUG', 'ERROR: No Level 2 .tar files found inside ' + tarFileName)
            sys.exit(1)
        log('INFO', 'Found Level 2 tar files: ' + str(level2Tars))

        # Step 5: Create SFS release directory if not exists
        if not os.path.exists(sfsTargetDir):
            os.makedirs(sfsTargetDir)

        # Step 6: For each Level 2 tar — extract to temp subdir then find Level 3 tar
        for level2Tar in level2Tars:
            log('INFO', 'Processing Level 2 tar: ' + level2Tar)

            # Extract Level 2 tar to its own temp subdir
            level2ExtractDir = tempExtractDir + '/level2_' + os.path.basename(level2Tar).replace('.tar', '')
            createFolder(level2ExtractDir)

            cmd = 'tar -xf ' + level2Tar + ' -C ' + level2ExtractDir
            status, result = executeCommand(cmd)
            if status != 0:
                log('DEBUG', 'ERROR: Failed to extract Level 2 tar: ' + level2Tar)
                sys.exit(1)
            log('INFO', 'Level 2 extraction successful: ' + level2Tar)

            # Step 7: Find Level 3 tars inside Level 2 extract dir
            # e.g. tfg.tar or pct-0.1.0.tar
            level3Tars = []
            for root, dirs, files in os.walk(level2ExtractDir):
                for f in files:
                    if f.endswith('.tar'):
                        level3Tars.append(os.path.join(root, f))

            if not level3Tars:
                log('DEBUG', 'ERROR: No Level 3 .tar files found inside: ' + level2Tar)
                sys.exit(1)
            log('INFO', 'Found Level 3 tar files: ' + str(level3Tars))

            # Step 8: Extract each Level 3 tar into sfsTargetDir
            for level3Tar in level3Tars:
                log('INFO', 'Extracting Level 3 tar: ' + level3Tar + ' to ' + sfsTargetDir)
                cmd = 'tar -xf ' + level3Tar + ' -C ' + sfsTargetDir
                status, result = executeCommand(cmd)
                if status != 0:
                    log('DEBUG', 'ERROR: Failed to extract Level 3 tar: ' + level3Tar)
                    sys.exit(1)
                log('INFO', 'Level 3 tar extracted successfully: ' + level3Tar)

    finally:
        # Always cleanup temp folder — whether deployment succeeds or fails
        if os.path.exists(tempExtractDir):
            log('INFO', 'Cleaning up temp folder: ' + tempExtractDir)
            shutil.rmtree(tempExtractDir)
            log('INFO', 'Temp folder cleaned up successfully')

    # Step 9: For each component — check what Level 3 tar extracted
    # IF tfg/       extracted → rename to tfg-0.1.0  then create symlink forcefully
    # IF tfg-0.1.0/ extracted → skip rename           then create symlink forcefully
    components = getComponents()
    for comp in components:
        compDir        = sfsTargetDir + '/' + comp                    # applRoot/sfs-app-0.1.0/tfg
        compVersionDir = sfsTargetDir + '/' + comp + '-' + pa.release # applRoot/sfs-app-0.1.0/tfg-0.1.0
        compLink       = sfsTargetDir + '/' + comp                    # applRoot/sfs-app-0.1.0/tfg (symlink)

        if os.path.exists(compVersionDir):
            # tfg-0.1.0/ already exists after extraction — skip rename
            log('INFO', 'Versioned directory already exists after extraction, skipping rename: ' + compVersionDir)
        elif os.path.isdir(compDir) and not os.path.islink(compDir):
            # tfg/ extracted as real directory — rename to tfg-0.1.0/
            log('INFO', 'Renaming ' + compDir + ' to ' + compVersionDir)
            os.rename(compDir, compVersionDir)
            # Verify rename was successful
            if not os.path.exists(compVersionDir):
                log('DEBUG', 'ERROR: Rename failed — versioned directory not found: ' + compVersionDir)
                sys.exit(1)
            log('INFO', 'Verified versioned directory: ' + compVersionDir)
        else:
            log('DEBUG', 'ERROR: Neither ' + compDir + ' nor ' + compVersionDir + ' found after extraction')
            sys.exit(1)

        # Create symlink forcefully — ln -fs (works whether symlink exists or not)
        log('INFO', 'Creating component symlink: ' + compLink + ' -> ' + compVersionDir)
        cmd = 'ln -fs ' + compVersionDir + ' ' + compLink
        executeCommand(cmd)

    # Step 10: Create symlink applRoot/sfs-app -> applRoot/sfs-app-<release>
    log('INFO', 'Creating symlink: ' + sfsLink + ' -> ' + sfsTargetDir)
    os.symlink(sfsTargetDir, sfsLink)

    fixPermissions()

    log('INFO', '--- SFS Core Deployment Completed Successfully ---')



# ─────────────────────────────────────────────
# Config Deployment  (--type config)
# ─────────────────────────────────────────────

def sfsConfigDeploy():
    """
    Config deployment — mirrors reference deploy() + configure() pattern:
      1. clean()        — remove old config release + symlink
      2. configure()    — replace placeholders, write application.properties
      3. os.symlink     — applRoot/config -> applRoot/config-<release>
      4. fixPermissions()
    """
    log('INFO', 'sfsConfigDeploy()')

    configReleaseDir = 'config-' + pa.release              # config-0.1.0
    configTargetDir  = pa.applRoot + configReleaseDir      # applRoot/config-0.1.0
    configLink       = pa.applRoot + 'config'              # applRoot/config

    # Step 1: Verify SFS extracted directory exists
    sfsTargetDir = pa.applRoot + 'sfs-app-' + pa.release
    checkFileExists(sfsTargetDir)

    # Step 2: Create config release directory
    os.makedirs(configTargetDir)

    # Step 3: Configure all components
    configure()

    # Step 4: Create symlink applRoot/config -> applRoot/config-<release>
    log('INFO', 'Creating symlink: ' + configLink + ' -> ' + configTargetDir)
    os.symlink(configTargetDir, configLink)

    fixPermissions()

    log('INFO', '--- SFS Config Deployment Completed Successfully ---')


# ─────────────────────────────────────────────
# Validate  (aligned with reference validate())
# ─────────────────────────────────────────────

def validate():
    log('INFO', 'Validation code we will add in later iteration or future enhancement')


# ─────────────────────────────────────────────
# Init  (aligned with reference init())
# ─────────────────────────────────────────────

def init():
    """
    Parse CLI arguments and load envInfo global.
    Mirrors reference code init() pattern.
    """
    global pa, envInfo

    parser = argparse.ArgumentParser(description='SFS Deployment')

    # Required arguments
    required = parser.add_argument_group('required arguments')
    required.add_argument('--applRoot',  nargs='?', help='Application Root / Deployment Home Directory',
                          required=True,  dest='applRoot')
    required.add_argument('--action',    nargs='?', help='Action (deploy/validate)',
                          required=True,  dest='action')
    required.add_argument('--release',   nargs='?', help='SFS Release version e.g. 0.1.0',
                          required=True,  dest='release')
    required.add_argument('--type',      nargs='?', help='Deployment type: core / config / all',
                          required=True,  dest='type')

    # Conditional arguments — required only for --type config or --type all
    conditional = parser.add_argument_group('conditional arguments (required for --type config or --type all)')
    conditional.add_argument('--env',       nargs='?', help='Environment e.g. cit01',
                             required=False, dest='env')
    conditional.add_argument('--envFolder', nargs='?', help='Path to directory containing env.json',
                             required=False, dest='envFolder')

    # Optional arguments
    optional = parser.add_argument_group('optional arguments')
    optional.add_argument('--component', '--list', nargs='+',
                          help='Component name(s): tfg, pct or all (default: all)',
                          required=False, dest='component')

    pa = parser.parse_args()

    # Defaults
    if pa.component is None:
        pa.component = ['all']

    # Trailing slash normalisation (same as reference code)
    if pa.applRoot[-1:] != '/':
        pa.applRoot = pa.applRoot + '/'

    # envFolder defaults to applRoot/env if not provided
    if pa.envFolder is None:
        pa.envFolder = pa.applRoot + 'env'
    elif pa.envFolder[-1:] == '/':
        pa.envFolder = pa.envFolder[:-1]

    log('INFO', '--- SFS Deploy Arguments ---')
    log('INFO', 'applRoot  : ' + pa.applRoot)
    log('INFO', 'action    : ' + pa.action)
    log('INFO', 'env       : ' + str(pa.env))
    log('INFO', 'release   : ' + pa.release)
    log('INFO', 'type      : ' + pa.type)
    log('INFO', 'envFolder : ' + pa.envFolder)
    log('INFO', 'component : ' + str(pa.component))

    # Verify applRoot exists
    checkFileExists(pa.applRoot)

    # Load env info only when needed i.e. config or all deploy
    # Not required for core deploy
    # Filename pattern: <env>_envInfo.json e.g. cit01_envInfo.json
    if pa.type.lower() in ['config', 'all']:
        if pa.env is None:
            log('DEBUG', 'ERROR: --env is required for --type config or --type all')
            sys.exit(1)
        envInfo = readJsonData(pa.envFolder + '/' + pa.env + '_envInfo.json')


# ─────────────────────────────────────────────
# Main Entry Point  (aligned with reference main())
# ─────────────────────────────────────────────

def main():
    log('INFO', 'Begin: Deploying SFS')

    init()

    if pa.action.lower() == 'deploy':

        deployType = pa.type.lower()

        if deployType == 'core':
            sfsDeploy()

        elif deployType == 'config':
            sfsConfigDeploy()

        elif deployType == 'all':
            sfsDeploy()
            sfsConfigDeploy()

        else:
            log('DEBUG', 'ERROR: Invalid type: ' + pa.type
                + '. Valid values are: core, config, all')
            sys.exit(1)

    elif pa.action.lower() == 'validate':
        validate()

    else:
        log('ERROR', 'Invalid action: ' + pa.action
            + '. Valid values are: deploy, validate')
        sys.exit(1)


main()
