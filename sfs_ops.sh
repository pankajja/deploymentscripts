#!/bin/bash

# =============================================================================
# sfs_ops.sh — SFS Operations Script
# Handles keytab generation, stop and start of SFS components
# =============================================================================

# ── Global Variables ──────────────────────────────────────────────────────────
SERVICE_USER="sfsapp"
KEYTAB_DIR="/cls/appl/env/rds_usr_keytab"

# ── Logging ───────────────────────────────────────────────────────────────────
log() {
    local level=$1
    local msg=$2
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "${timestamp}: ${level}: ${msg}"
}

# ── Usage ─────────────────────────────────────────────────────────────────────
usage() {
    echo ""
    echo "Usage: ./sfs_ops.sh --env <env> --action <action> [--dbUser <dbUser>]"
    echo ""
    echo "Required arguments:"
    echo "  --env     <env>     Environment e.g. cit01, sit01, uat01, prod"
    echo "  --action  <action>  Action to perform: keytab / stop / start"
    echo ""
    echo "Conditional arguments (required for --action keytab):"
    echo "  --dbUser  <dbUser>  DB username e.g. sfsdbcit1"
    echo ""
    echo "Examples:"
    echo "  ./sfs_ops.sh --env cit01 --action keytab --dbUser sfsdbcit1"
    echo "  ./sfs_ops.sh --env cit01 --action stop"
    echo "  ./sfs_ops.sh --env cit01 --action start"
    echo ""
    exit 1
}

# ── Parse Arguments ───────────────────────────────────────────────────────────
parse_args() {
    ENV=""
    ACTION=""
    DB_USER=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --env)
                ENV="$2"
                shift 2
                ;;
            --action)
                ACTION="$2"
                shift 2
                ;;
            --dbUser)
                DB_USER="$2"
                shift 2
                ;;
            -h|--help)
                usage
                ;;
            *)
                log "ERROR" "Unknown argument: $1"
                usage
                ;;
        esac
    done

    log "INFO" "--- SFS Ops Arguments ---"
    log "INFO" "env    : ${ENV}"
    log "INFO" "action : ${ACTION}"
    log "INFO" "dbUser : ${DB_USER}"
}

# ── Validate Arguments ────────────────────────────────────────────────────────
validate_args() {
    # Check required args
    if [[ -z "$ENV" ]]; then
        log "ERROR" "--env is required"
        usage
    fi

    if [[ -z "$ACTION" ]]; then
        log "ERROR" "--action is required"
        usage
    fi

    # Validate action value
    if [[ "$ACTION" != "keytab" && "$ACTION" != "stop" && "$ACTION" != "start" ]]; then
        log "ERROR" "Invalid action: ${ACTION}. Valid values are: keytab, stop, start"
        exit 1
    fi

    # dbUser required for keytab action
    if [[ "$ACTION" == "keytab" && -z "$DB_USER" ]]; then
        log "ERROR" "--dbUser is required for --action keytab"
        usage
    fi

    # Check APP_HOME is set
    if [[ -z "$APP_HOME" ]]; then
        log "ERROR" "APP_HOME environment variable is not set"
        exit 1
    fi

    log "INFO" "Validation passed"
}

# ── Derive Domain ─────────────────────────────────────────────────────────────
get_domain() {
    # cit*, sit*, uat* → CLSNONPROD.LOCAL
    # prod*            → CLSPROD.LOCAL
    if [[ "$ENV" == cit* || "$ENV" == sit* || "$ENV" == uat* ]]; then
        echo "CLSNONPROD.LOCAL"
    elif [[ "$ENV" == prod* ]]; then
        echo "CLSPROD.LOCAL"
    else
        log "ERROR" "Cannot derive domain for env: ${ENV}"
        exit 1
    fi
}

# ── Keytab Generation ─────────────────────────────────────────────────────────
action_keytab() {
    log "INFO" "--- Starting Keytab Generation ---"

    local domain
    domain=$(get_domain)
    log "INFO" "Domain    : ${domain}"
    log "INFO" "DB User   : ${DB_USER}"
    log "INFO" "Keytab Dir: ${KEYTAB_DIR}"

    local principal="${DB_USER}@${domain}"
    local keytab_file="${KEYTAB_DIR}/${DB_USER}_auto.keytab"

    log "INFO" "Principal  : ${principal}"
    log "INFO" "Keytab File: ${keytab_file}"

    # Get password using dzdo
    log "INFO" "Retrieving account password"
    local kt_passwd
    kt_passwd=$(dzdo /bin/cgetaccount -s -T domain "${domain}/${DB_USER}")
    if [[ $? -ne 0 ]]; then
        log "ERROR" "Failed to retrieve password for ${DB_USER}"
        exit 1
    fi

    log "INFO" "Starting Keytab cmds"

    # Generate keytab using ktutil
    /usr/bin/ktutil <<EOF
addent -password -p ${principal} -k 1 -e aes256-cts-hmac-sha-96
${kt_passwd}
wkt ${keytab_file}
q
EOF

    if [[ $? -ne 0 ]]; then
        log "ERROR" "Keytab generation failed"
        exit 1
    fi

    log "INFO" "Done with Keytab cmds"
    log "INFO" "Keytab file created: ${keytab_file}"
    log "INFO" "--- Keytab Generation Completed Successfully ---"
}

# ── Stop Components ───────────────────────────────────────────────────────────
action_stop() {
    log "INFO" "--- Starting SFS Stop ---"
    log "INFO" "Stop order: PCT first then TFG"

    # Stop PCT first
    local pct_stop="${APP_HOME}/sfs/pct/bin/stop_pct.sh"
    log "INFO" "Stopping PCT: ${pct_stop}"
    if [[ ! -f "$pct_stop" ]]; then
        log "ERROR" "PCT stop script not found: ${pct_stop}"
        exit 1
    fi
    dzdo -iu "${SERVICE_USER}" "${pct_stop}"
    if [[ $? -ne 0 ]]; then
        log "ERROR" "Failed to stop PCT"
        exit 1
    fi
    log "INFO" "PCT stopped successfully"

    # Stop TFG second
    local tfg_stop="${APP_HOME}/sfs/tfg/bin/stop_tfg.sh"
    log "INFO" "Stopping TFG: ${tfg_stop}"
    if [[ ! -f "$tfg_stop" ]]; then
        log "ERROR" "TFG stop script not found: ${tfg_stop}"
        exit 1
    fi
    dzdo -iu "${SERVICE_USER}" "${tfg_stop}"
    if [[ $? -ne 0 ]]; then
        log "ERROR" "Failed to stop TFG"
        exit 1
    fi
    log "INFO" "TFG stopped successfully"

    log "INFO" "--- SFS Stop Completed Successfully ---"
}

# ── Start Components ──────────────────────────────────────────────────────────
action_start() {
    log "INFO" "--- Starting SFS Start ---"
    log "INFO" "Start order: TFG first then PCT"

    # Start TFG first
    local tfg_start="${APP_HOME}/sfs/tfg/bin/start_tfg.sh"
    log "INFO" "Starting TFG: ${tfg_start}"
    if [[ ! -f "$tfg_start" ]]; then
        log "ERROR" "TFG start script not found: ${tfg_start}"
        exit 1
    fi
    dzdo -iu "${SERVICE_USER}" "${tfg_start}"
    if [[ $? -ne 0 ]]; then
        log "ERROR" "Failed to start TFG"
        exit 1
    fi
    log "INFO" "TFG started successfully"

    # Start PCT second
    local pct_start="${APP_HOME}/sfs/pct/bin/start_pct.sh"
    log "INFO" "Starting PCT: ${pct_start}"
    if [[ ! -f "$pct_start" ]]; then
        log "ERROR" "PCT start script not found: ${pct_start}"
        exit 1
    fi
    dzdo -iu "${SERVICE_USER}" "${pct_start}"
    if [[ $? -ne 0 ]]; then
        log "ERROR" "Failed to start PCT"
        exit 1
    fi
    log "INFO" "PCT started successfully"

    log "INFO" "--- SFS Start Completed Successfully ---"
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
    log "INFO" "Begin: SFS Operations"

    parse_args "$@"
    validate_args

    case "$ACTION" in
        keytab)
            action_keytab
            ;;
        stop)
            action_stop
            ;;
        start)
            action_start
            ;;
    esac
}

main "$@"
