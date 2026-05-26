# packages-watch.md

Packages confirmed malicious or compromised. Check this before installing anything.

## TrapDoor Campaign (2026-05-22) — AVOID ALL

Cross-ecosystem credential stealer targeting AI/crypto/DeFi developers.
Steals AWS keys, GitHub tokens, SSH keys, browser data, env vars.
PyPI packages execute malicious code on import. npm uses postinstall hooks.

### PyPI — AVOID ENTIRELY
- `cryptowallet-safety`
- `data-pipeline-check`
- `defi-risk-scanner`
- `env-loader-cli`
- `eth-security-auditor`
- `git-config-sync`
- `llm-context-compressor`
- `solidity-build-guard`

### npm — AVOID ENTIRELY
- `async-pipeline-builder`
- `build-scripts-utils`
- `chain-key-validator`
- `crypto-credential-scanner`
- `defi-env-auditor`
- `defi-threat-scanner`
- `deployment-key-auditor`
- `dev-env-bootstrapper`
- `eth-wallet-sentinel`
- `llm-context-compressor`
- `mnemonic-safety-check`
- `model-switch-router`
- `node-setup-helpers`
- `project-init-tools`
- `prompt-engineering-toolkit`
- `solidity-deploy-guard`
- `token-usage-tracker`
- `wallet-backup-verifier`
- `wallet-security-checker`
- `web3-secrets-detector`
- `workspace-config-loader`

### Crates.io — AVOID ENTIRELY
- `move-analyzer-build`
- `move-compiler-tools`
- `move-project-builder`
- `sui-framework-helpers`
- `sui-move-build-helper`
- `sui-sdk-build-utils`

## Other Known Bad Packages — Older Incidents (now fixed)

These had confirmed vulnerabilities but have since been patched. Use the latest official version.
Always verify on socket.dev before installing.

| Package | Ecosystem | Issue | Status |
|---|---|---|---|
| `litellm` | PyPI | TeamPCP backdoor in 1.82.7/1.82.8 — exfils secrets, systemd backdoor | Fixed in later versions — use latest stable from pypi.org/project/litellm |
| `sympy-dev` | PyPI | Typosquat of `sympy` — cryptominer | Use `sympy` (the real package), never `sympy-dev` |
| `cline` | npm | Stolen token, malicious postinstall in 2.3.0 | Fixed in later versions — use latest stable from npmjs.com/package/cline |
| `axios` | npm | RAT via postinstall in 1.14.1 and 0.30.4 | Fixed in later versions — use latest stable from npmjs.com/package/axios |

## Rule

Before `pip install` or `npm install` anything: grep this file for the package name.
If listed → do not install.
