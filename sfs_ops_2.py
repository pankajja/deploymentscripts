#!/usr/bin/python3

# =============================================================================
# sfs_ops.py — SFS Operations Script (Python)
# Handles keytab generation, stop/start/status of SFS components
# =============================================================================

import os
import sys
import subprocess
import argparse
import datetime
import logging
import socket

# ── Global Variables ──────────────────────────────────────────────────────────
APP_HOME     = os.environ.get('APP_HOME', '')
LOG_DIR      = '/home/claude/applroot/logs'
SERVICE_BIN  = '/cls/appl/sfsbin'
KEYTAB_DIR   = '/cls/appl/env/rds_usr_keytab'

# Known components — base names
KNOWN_COMPONENTS = ['tfg', 'pct', 'su']

# Component process identifiers for ps grep
COMP_PROCESS_MAP = {
    'tfg' : 'TemplateFileGenerator',
    'pct' : 'PCT',
    'su'  : 'statementutility'
}

# Stop order — reverse of start
STOP_ORDER  = ['su', 'pct', 'tfg']
START_ORDER = ['tfg', 'pct', 'su']

# Global state
pa     = None
logger = None


# ── Logging Setup ─────────────────────────────────────────────────────────────

def setupLogging():
    """
    Set up logging:
    - File    → /cls/appl/logs/sfs_ops_YYYYMMDD_HHMMSS.log  (DEBUG + INFO)
    - Console → INFO only (minimal)
    """
    global logger

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    logFile   = LOG_DIR + '/sfs_ops_' + timestamp + '.log'

    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    logger = logging.getLogger('sfs_ops')
    logger.setLevel(logging.DEBUG)

    # File handler — detailed
    fh = logging.FileHandler(logFile)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        '%(asctime)s: %(levelname)s: %(message)s', '%Y-%m-%d %H:%M:%S'))

    # Console handler — minimal INFO only
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(
        '%(asctime)s: %(levelname)s: %(message)s', '%Y-%m-%d %H:%M:%S'))

    logger.addHandler(fh)
    logger.addHandler(ch)
    logger.info('Log file: ' + logFile)


def log(level, msg):
    """Wrapper for logger."""
    if level == 'DEBUG':
        logger.debug(msg)
    elif level == 'INFO':
        logger.info(msg)
    elif level == 'ERROR':
        logger.error(msg)
    else:
        logger.info(msg)


# ── Utility ───────────────────────────────────────────────────────────────────

def executeCommand(cmd):
    """Run a shell command and return (status, result)."""
    log('DEBUG', 'Execute: ' + cmd)
    status, result = subprocess.getstatusoutput(cmd)
    log('DEBUG', 'Status: ' + str(status))
    if result:
        log('DEBUG', 'Output: ' + result)
    return status, result


def validateAppHome():
    """Check APP_HOME is set and exists."""
    if not APP_HOME:
        log('ERROR', 'APP_HOME environment variable is not set')
        sys.exit(1)
    if not os.path.exists(APP_HOME):
        log('ERROR', 'APP_HOME does not exist: ' + APP_HOME)
        sys.exit(1)
    log('DEBUG', 'APP_HOME: ' + APP_HOME)


def getComponents():
    """
    Resolve component list from --component arg.
    'all' → STOP_ORDER or START_ORDER depending on action.
    """
    if pa.component is None or pa.component == ['all']:
        return None    # caller decides order
    return [c.lower() for c in pa.component]


def getDomain():
    """
    Derive Delinea domain from --env argument.
    cit*, sit*, uat* → CLSNONPROD.LOCAL
    prod*            → CLSPROD.LOCAL
    """
    env = pa.env.lower()
    if env.startswith('cit') or env.startswith('sit') or env.startswith('uat'):
        return 'CLSNONPROD.LOCAL'
    elif env.startswith('prod'):
        return 'CLSPROD.LOCAL'
    else:
        log('ERROR', 'Cannot derive domain for env: ' + pa.env)
        sys.exit(1)


# ── Keytab Generation ─────────────────────────────────────────────────────────

def actionKeytab():
    """Generate keytab file using dzdo and ktutil."""
    log('INFO', '--- Starting Keytab Generation ---')

    domain      = getDomain()
    principal   = pa.dbUser + '@' + domain
    keytabFile  = KEYTAB_DIR + '/' + pa.dbUser + '_auto.keytab'

    log('INFO', 'Domain     : ' + domain)
    log('INFO', 'DB User    : ' + pa.dbUser)
    log('INFO', 'Principal  : ' + principal)
    log('INFO', 'Keytab File: ' + keytabFile)

    # Get password from Delinea vault
    log('INFO', 'Retrieving account password')
    status, ktPasswd = executeCommand(
        '/usr/bin/dzdo /usr/bin/cgetaccount -s -T domain ' + domain + '/' + pa.dbUser)
    if status != 0:
        log('ERROR', 'Failed to retrieve password for ' + pa.dbUser)
        sys.exit(1)

    # Generate keytab using ktutil
    log('INFO', 'Starting Keytab cmds')
    ktutilInput = (
        'addent -password -p ' + principal + ' -k 1 -e aes256-cts-hmac-sha1-96\n'
        + ktPasswd + '\n'
        + 'wkt ' + keytabFile + '\n'
        + 'q\n'
    )

    proc = subprocess.Popen(
        ['/usr/bin/ktutil'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    stdout, stderr = proc.communicate(input=ktutilInput.encode())

    if proc.returncode != 0:
        log('ERROR', 'Keytab generation failed: ' + stderr.decode())
        sys.exit(1)

    log('INFO', 'Done with Keytab cmds')
    log('INFO', 'Keytab file created: ' + keytabFile)
    log('INFO', '--- Keytab Generation Completed Successfully ---')


# ── Stop ──────────────────────────────────────────────────────────────────────

def stopComponent(comp):
    """Stop a single component."""
    stopScript = APP_HOME + '/' + comp + '/bin/stop_' + comp + '.sh'
    log('INFO', 'Stopping ' + comp.upper() + ': ' + stopScript)

    if not os.path.isfile(stopScript):
        log('ERROR', 'Stop script not found: ' + stopScript)
        sys.exit(1)

    status, result = executeCommand(stopScript)
    if status != 0:
        log('ERROR', 'Failed to stop ' + comp.upper())
        sys.exit(1)
    log('INFO', comp.upper() + ' stopped successfully')


def actionStop():
    """
    Stop components.
    If --component all → stop in order: su → pct → tfg
    If specific component → stop only that one
    """
    log('INFO', '--- Starting SFS Stop ---')

    components = getComponents()
    if components is None:
        components = STOP_ORDER    # su → pct → tfg
        log('INFO', 'Stop order: ' + ' → '.join(components))

    for comp in components:
        stopComponent(comp)

    log('INFO', '--- SFS Stop Completed Successfully ---')


# ── Start ─────────────────────────────────────────────────────────────────────

def startComponent(comp):
    """Start a single component."""
    startScript = APP_HOME + '/' + comp + '/bin/start_' + comp + '.sh'
    log('INFO', 'Starting ' + comp.upper() + ': ' + startScript)

    if not os.path.isfile(startScript):
        log('ERROR', 'Start script not found: ' + startScript)
        sys.exit(1)

    status, result = executeCommand(startScript)
    if status != 0:
        log('ERROR', 'Failed to start ' + comp.upper())
        sys.exit(1)
    log('INFO', comp.upper() + ' started successfully')


def actionStart():
    """
    Start components.
    Always generates keytab first then:
    If --component all → start in order: tfg → pct → su
    If specific component → start only that one
    """
    log('INFO', '--- Starting SFS Start ---')

    # Step 1: Generate keytab first
    log('INFO', 'Step 1: Generating keytab before start')
    actionKeytab()

    # Step 2: Start components
    components = getComponents()
    if components is None:
        components = START_ORDER    # tfg → pct → su
        log('INFO', 'Start order: ' + ' → '.join(components))

    for comp in components:
        startComponent(comp)

    log('INFO', '--- SFS Start Completed Successfully ---')


# ── Status ────────────────────────────────────────────────────────────────────

def getComponentStatus(comp):
    """
    Check if component is running using ps command.
    Returns (isRunning, pid)
    """
    processName = COMP_PROCESS_MAP.get(comp, comp)
    cmd = 'ps -eaf | grep ' + processName + ' | grep -v grep | awk \'{print $2}\''
    status, output = executeCommand(cmd)

    pid = output.strip()
    if pid:
        return True, pid
    return False, None


def actionStatus():
    """
    Show status of components using ps command.
    If --component all → show all components
    If specific → show only that one
    """
    log('INFO', '--- SFS Component Status ---')

    components = getComponents()
    if components is None:
        components = KNOWN_COMPONENTS

    print('')
    print('{:<20} {:<10} {}'.format('COMPONENT', 'STATUS', 'PID'))
    print('-' * 45)

    for comp in components:
        isRunning, pid = getComponentStatus(comp)
        if isRunning:
            status = 'RUNNING'
            pidStr = pid
        else:
            status = 'STOPPED'
            pidStr = '-'
        print('{:<20} {:<10} {}'.format(comp.upper(), status, pidStr))
        log('INFO', comp.upper() + ': ' + status + ' (pid: ' + pidStr + ')')

    print('')
    log('INFO', '--- Status Check Completed ---')


# ── Argument Parsing ──────────────────────────────────────────────────────────

def init():
    """Parse CLI arguments."""
    global pa

    parser = argparse.ArgumentParser(description='SFS Operations Script')

    # Required arguments
    required = parser.add_argument_group('required arguments')
    required.add_argument('--action', nargs='?',
                          help='Action: keytab / stop / start / status',
                          required=True, dest='action')

    # Conditional arguments
    conditional = parser.add_argument_group(
        'conditional arguments (required for --action keytab and start)')
    conditional.add_argument('--env', nargs='?',
                             help='Environment e.g. cit01 (required for keytab/start)',
                             required=False, dest='env')
    conditional.add_argument('--dbUser', nargs='?',
                             help='DB username e.g. sfsdbcit1 (required for keytab/start)',
                             required=False, dest='dbUser')

    # Optional arguments
    optional = parser.add_argument_group('optional arguments')
    optional.add_argument('--component', nargs='+',
                          help='Component(s): tfg / pct / su / all (default: all)',
                          required=False, dest='component')

    pa = parser.parse_args()

    # Defaults
    if pa.component is None:
        pa.component = ['all']

    log('INFO', '--- SFS Ops Arguments ---')
    log('INFO', 'action    : ' + pa.action)
    log('INFO', 'env       : ' + str(pa.env))
    log('INFO', 'dbUser    : ' + str(pa.dbUser))
    log('INFO', 'component : ' + str(pa.component))


# ── Validation ────────────────────────────────────────────────────────────────

def validate():
    """Validate arguments."""
    # Valid actions
    validActions = ['keytab', 'stop', 'start', 'status']
    if pa.action.lower() not in validActions:
        log('ERROR', 'Invalid action: ' + pa.action
            + '. Valid values: ' + ', '.join(validActions))
        sys.exit(1)

    # --env and --dbUser required for keytab and start
    if pa.action.lower() in ['keytab', 'start']:
        if not pa.env:
            log('ERROR', '--env is required for --action ' + pa.action)
            sys.exit(1)
        if not pa.dbUser:
            log('ERROR', '--dbUser is required for --action ' + pa.action)
            sys.exit(1)

    # Validate component names
    components = getComponents()
    if components:
        for comp in components:
            if comp not in KNOWN_COMPONENTS:
                log('ERROR', 'Unknown component: ' + comp
                    + '. Valid: ' + ', '.join(KNOWN_COMPONENTS))
                sys.exit(1)

    # Validate APP_HOME for stop/start/status
    if pa.action.lower() in ['stop', 'start', 'status']:
        validateAppHome()

    log('INFO', 'Validation passed')


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    setupLogging()
    log('INFO', 'Begin: SFS Operations')

    init()
    validate()

    action = pa.action.lower()

    if action == 'keytab':
        actionKeytab()
    elif action == 'stop':
        actionStop()
    elif action == 'start':
        actionStart()
    elif action == 'status':
        actionStatus()


main()
