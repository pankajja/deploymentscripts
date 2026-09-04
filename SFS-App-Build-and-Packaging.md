# SFS App — Build & Packaging Overview

**Audience:** DevOps, Engineering Managers
**Purpose:** A high-level view of how SFS components are built, packaged, and published — what happens, in what order, and why.

---

## 1. Overview

SFS ("Search File System" — *update if this expansion isn't correct*) is made up of several components that are built independently and then assembled into release packages. The build system uses a shared Jenkins pipeline definition so that every component follows the same process, while packaging is handled separately to combine build outputs into deployable artifacts.

In short: **components build individually → packaging jobs assemble them → finished artifacts are published to Nexus.**

---

## 2. Component Pipeline

Every SFS component builds through the same shared Jenkins pipeline (`cls-sfs-ci.jenkinsfile`) — one consistent process for checkout, build, quality checks, and packaging handoff, with room for each component to override specific settings where needed.

| Component | Feeds into (module) | Notes |
|---|---|---|
| `sfsparent` | *(none — parent POM only)* | Defines shared build settings that all other components inherit from |
| `sfscommon` | *(shared dependency)* | Built once, reused by other components (see Section 4) |
| `sfstfg` | `sfs-full-release` | |
| `sfspct` | `sfs-full-release` | |
| `sfssu` | `sfs-full-release` | |
| `sfsdb` | `sfs-db` | Skips the Maven build step — packaged differently from the others |

**Why this matters:** teams don't need to maintain separate build logic per component, and it's clear at a glance which components roll up into which release package.

---

## 3. Packaging Pipeline

Once components are built, they're grouped into **packaging modules** — these decide what gets bundled together and how it's delivered:

| Module | Built from | Release report |
|---|---|---|
| `sfs-full-release` | `sfstfg`, `sfspct`, `sfssu` | Included |
| `sfs-db` | `sfsdb` | Skipped |
| `sfs-deploy` | *(deployment-focused packaging)* | Skipped |
| `sfs_db_utils` | *(database utility packaging)* | Skipped |

`sfs-full-release` is the only module that generates a release report by default — the other three are marked to skip it, likely because they're supporting/utility packages rather than the primary customer-facing release.

Each module defines *what* to pull in from prior component builds, *where* to place it, and *how* to name the final files — using a version placeholder so the same definition works across every release.

---

## 4. Dependency Management

There are two layers of dependency in this system:

- **Build-time:** `sfsparent` acts as the parent project definition that other components build from, ensuring consistent build settings across the codebase.
- **Packaging-time:** `sfscommon` is explicitly flagged as a shared dependency (`isDependency: true`) and is built once, then reused across other components (e.g. `sfstfg`, `sfspct`) rather than each one building it separately. Packaging for those components waits until `sfscommon` is available.

**Why this matters:** it prevents packages from being built with outdated or missing shared components, and avoids redundant builds of the same shared code.

---

## 5. SCM & Branch Strategy

Each component's pipeline is tied to a specific source repository and a marker file (e.g. `pom.xml`) used to confirm the correct code is being built. This ensures builds always pull from the right place and validate that the repository is in the expected state before proceeding.

---

## 6. Quality Gates — Sonar & SBOM

Before a build is considered complete, it can go through:

- **Sonar analysis** — code quality and security scanning (configurable per component; some checks can be skipped where not applicable).
- **SBOM (Software Bill of Materials)** — a record of everything included in the build, for traceability and compliance. This can also be skipped for specific modules where not required.

**Why this matters:** these checks catch issues early and support audit/compliance needs without slowing down every build equally — they can be tuned per component.

---

## 7. Nexus Publishing

Finished packages are published to **Nexus**, the artifact repository, using standardized coordinates (group ID / artifact ID) so downstream teams and deployment tools can reliably pull the correct versioned artifact. Some packaging steps also validate artifacts against the Nexus repository before finalizing, catching issues before release.

---

## 8. End-to-End Flow

```
sfsparent (parent POM — build settings only)
        │
        ▼
sfscommon (shared dependency — built once)
        │
        ├──────────────┬──────────────┐
        ▼              ▼              ▼
    sfstfg          sfspct         sfssu          sfsdb
        │              │              │              │
        └──────┬───────┴──────────────┘              │
               ▼                                      ▼
        sfs-full-release                           sfs-db
        (release report included)              (release report skipped)

                                          sfs-deploy   sfs_db_utils
                                        (release report skipped)

        │                                      │              │
        ▼                                      ▼              ▼
                    Nexus Repository (versioned, published artifacts)
```

---

### Notes for reviewers
- Section 1's product description is inferred from naming conventions — please confirm/correct before publishing.
- The exact purpose of `sfs-deploy` and `sfs_db_utils` (beyond their names) isn't fully visible in the source config — worth a quick confirm from the team that owns them.
- This page intentionally omits JSON/config-level detail (build flags, file paths, version templating syntax) to keep it accessible to non-technical stakeholders. A technical appendix or linked page can be added separately if engineers need the deeper reference.
