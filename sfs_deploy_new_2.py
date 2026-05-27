#!/usr/bin/python3

import json, sys, fileinput, datetime, time
import os, shutil, collections
import argparse, socket, getpass
import subprocess, inspect

from pprint import pprint

# ─────────────────────────────────────────────
# Startup — change working dir to script's own
# directory (aligned with reference code)
# ─────────────────────────────────────────────
binFolder = os.path.dirname(os.path.realpath(__file__))
os.chdir(binFolder)

localHostName = socket.gethostname()

# echoVal: set to "echo" for dry-run/debug mode, "" for live
echoVal = ""

# Global state
pa      = None
envInfo = None

# Known components — extend this list as new components are added
KNOWN_COMPONENTS = ['TFG', 'PCT']


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


# ─────────────────────────────────────────────
# Component Resolution
# ─────────────────────────────────────────────

def getComponents():
    """
    Resolve the list of components to deploy.
    --component all      -> all known components [TFG, PCT]
    --component tfg      -> ['TFG']
    --component pct tfg  -> ['PCT', 'TFG']
    """
    if pa.component is None or pa.component == ['all']:
        return KNOWN_COMPONENTS
    # Normalise to uppercase to match directory names TFG / PCT
    return [c.upper() for c in pa.component]


# ─────────────────────────────────────────────
# Clean  (aligned with reference clean())
# ─────────────────────────────────────────────

def clean():
    """
    Remove existing release folder and symlink before fresh deploy.
    Mirrors reference code clean() pattern.
    """
    log('INFO', 'clean()')

    sfsReleaseFolder = pa.applRoot + 'SFS-' + pa.release     # applRoot/SFS-0.1.0
    sfsLink          = pa.applRoot + 'SFS'                   # applRoot/SFS
    configFolder     = pa.applRoot + 'config-' + pa.release  # applRoot/config-0.1.0
    configLink       = pa.applRoot + 'config'                # applRoot/config

    # Remove SFS symlink if exists
    if os.path.exists(sfsLink):
        cmd = 'rm -rf ' + sfsLink
        executeCommand(cmd)

    # Remove SFS release folder if exists
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

    sfsReleaseDir   = 'SFS-'    + pa.release                          # SFS-0.1.0
    configReleaseDir = 'config-' + pa.release                         # config-0.1.0
    sfsTargetDir    = pa.applRoot + sfsReleaseDir                     # applRoot/SFS-0.1.0
    configTargetDir = pa.applRoot + configReleaseDir                  # applRoot/config-0.1.0
    compOutputDir   = configTargetDir + '/' + comp                    # applRoot/config-0.1.0/TFG
    outputFilePath  = compOutputDir   + '/application.properties'     # final output

    # Paths
    compConfigJson   = './config/' + comp + '/config.json'            # staging repo
    templateFilePath = sfsTargetDir + '/' + comp + '/application.template.properties'

    # Step a: Read config.json from staging repo
    log('INFO', 'Reading config.json: ' + compConfigJson)
    configData = readJsonData(compConfigJson)

    # Step b: Read application.template.properties from extracted SFS dir
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

        print(param, envInfo[category][name])
        fileData = fileData.replace(param, envInfo[category][name])

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
        pa.applRoot + 'SFS-'    + pa.release,    # applRoot/SFS-0.1.0
        pa.applRoot + 'config-' + pa.release,     # applRoot/config-0.1.0
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
    Core deployment — mirrors reference deploy() pattern:
      1. clean()             — remove old release + symlinks
      2. Extract outer tar   — SFS-<release>.tar to temp staging area
      3. Find inner .tar     — recursively search inside temp folder (handles subdirectories)
      4. Extract each inner .tar — into applRoot/SFS-<release>/
      5. os.symlink          — applRoot/SFS -> applRoot/SFS-<release>
      6. fixPermissions()
    """
    log('INFO', 'deploy()')
    clean()

    sfsReleaseDir  = 'SFS-' + pa.release                    # SFS-0.1.0
    tarFileName    = sfsReleaseDir + '.tar'                  # SFS-0.1.0.tar
    sfsTargetDir   = pa.applRoot + sfsReleaseDir             # applRoot/SFS-0.1.0
    sfsLink        = pa.applRoot + 'SFS'                     # applRoot/SFS
    tempExtractDir = binFolder + '/tmp_extract'              # temp staging area for outer tar

    # Step 1: Verify outer tar exists in staging directory
    log('INFO', 'Checking tar artifact: ' + tarFileName)
    checkFileExists('./' + tarFileName)

    # Step 2: Create temp dir and extract outer tar into it
    createFolder(tempExtractDir)
    log('INFO', 'Extracting outer tar ' + tarFileName + ' to temp folder')
    cmd = 'tar -xf ' + tarFileName + ' -C ' + tempExtractDir
    status, result = executeCommand(cmd)
    if status != 0:
        log('DEBUG', 'ERROR: Failed to extract outer tar: ' + tarFileName)
        shutil.rmtree(tempExtractDir)
        sys.exit(1)
    log('INFO', 'Outer tar extraction successful')

    # Step 3: Recursively search for all inner .tar files inside temp extract folder
    # Using os.walk to handle cases where inner tars are inside a subdirectory
    # e.g. sfs-app-0.1.0/sfs-tfg-0.1.0.tar and sfs-app-0.1.0/sfs-pct-0.1.0.tar
    innerTars = []
    for root, dirs, files in os.walk(tempExtractDir):
        for f in files:
            if f.endswith('.tar'):
                innerTars.append(os.path.join(root, f))

    if not innerTars:
        log('DEBUG', 'ERROR: No inner .tar files found inside ' + tarFileName)
        shutil.rmtree(tempExtractDir)
        sys.exit(1)
    log('INFO', 'Found inner tar files: ' + str(innerTars))

    # Step 4: Create SFS release directory and extract each inner tar into it
    os.makedirs(sfsTargetDir)
    for innerTar in innerTars:
        log('INFO', 'Extracting inner tar: ' + innerTar + ' to ' + sfsTargetDir)
        cmd = 'tar -xf ' + innerTar + ' -C ' + sfsTargetDir
        status, result = executeCommand(cmd)
        if status != 0:
            log('DEBUG', 'ERROR: Failed to extract inner tar: ' + innerTar)
            shutil.rmtree(tempExtractDir)
            sys.exit(1)
        log('INFO', 'Inner tar extracted successfully: ' + innerTar)

    # Step 5: Clean up temp extract folder
    log('INFO', 'Cleaning up temp folder')
    shutil.rmtree(tempExtractDir)

    # Step 6: Verify expected component directories inside SFS release dir
    components = getComponents()
    for comp in components:
        compDir = sfsTargetDir + '/' + comp
        if not os.path.exists(compDir):
            log('DEBUG', 'ERROR: Expected component directory not found: ' + compDir)
            sys.exit(1)
        log('INFO', 'Verified component directory: ' + compDir)

    # Step 7: Create symlink applRoot/SFS -> applRoot/SFS-<release>
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
    sfsTargetDir = pa.applRoot + 'SFS-' + pa.release
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

    parser.add_argument('--applRoot',  nargs='?', help='Application Root / Deployment Home Directory',
                        required=True,  dest='applRoot')
    parser.add_argument('--action',    nargs='?', help='Action (deploy/validate)',
                        required=True,  dest='action')
    parser.add_argument('--env',       nargs='?', help='Environment e.g. cit01',
                        required=True,  dest='env')
    parser.add_argument('--release',   nargs='?', help='SFS Release version e.g. 0.1.0',
                        required=True,  dest='release')
    parser.add_argument('--type',      nargs='?', help='Deployment type: core / config / all',
                        required=False, dest='type',      default='all')
    parser.add_argument('--envFolder', nargs='?', help='Path to directory containing env.json',
                        required=False, dest='envFolder')
    parser.add_argument('--component', '--list', nargs='+',
                        help='Component name(s): tfg, pct or all',
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
    log('INFO', 'env       : ' + pa.env)
    log('INFO', 'release   : ' + pa.release)
    log('INFO', 'type      : ' + pa.type)
    log('INFO', 'envFolder : ' + pa.envFolder)
    log('INFO', 'component : ' + str(pa.component))

    # Verify applRoot exists
    checkFileExists(pa.applRoot)

    # Load env.json from envFolder (mirrors reference envInfo load)
    envInfo = readJsonData(pa.envFolder + '/env.json')


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
