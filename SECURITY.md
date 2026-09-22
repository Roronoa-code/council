# Security and authority boundaries

Council is a local decision-support coordinator, not a sandbox product. Its trust boundary assumes an uncompromised operating system, official installed CLIs and trusted administrator policy. CLI flags reduce tools/configuration exposure; they cannot contain a malicious executable, guarantee that every vendor telemetry path is disabled, or override administrator-enforced behaviour.

## Implemented defences

Workers run from separate temporary non-project directories. Codex uses read-only execution with shell, agent delegation, web search, apps/plugins/hooks/memory and discovered MCP endpoints disabled through documented configuration overrides. Claude uses safe mode, no built-in tools, explicit MCP denial and an empty strict MCP configuration. No permission-bypass flags or `--bare` are used. Required flags are not silently removed for compatibility.

Prompts travel through stdin; subprocesses use argv arrays and `shell=False`. Known Windows npm shims are resolved to their JavaScript entry point through node, never executed through cmd.exe with model text. Cancellation terminates the worker process tree/group on a best-effort OS basis. Output sizes, time and coordinator invocation counts are bounded. A malicious child can evade ordinary process-group containment; this is not a hardened multi-tenant sandbox.

Independent contexts and explicit untrusted-data framing reduce prompt-injection risk. Model output remains untrusted. Reports escape every dynamic HTML value, use a restrictive CSP and contain no JavaScript or remote assets. Markdown/JSON and handoff files must likewise be treated as data, never blindly executed or followed as higher-priority instructions.

## Authentication and spending

The project has no HTTP model API client. It strips common API-key, bearer-token, endpoint and cloud-provider overrides from child environments and requires a recognised saved subscription login. It does not copy credentials or print raw provider error logs. It does not modify login/configuration files, enable extra usage, purchase credits, or fall back to APIs. Provider accounts can still have paid extra usage enabled independently; disable it in the provider account when that matters. CLI/process caps are not hard dollar/token caps.

## Private artifacts

Inputs, excerpts, session metadata and decisions are sensitive. Run directories default outside repositories, use atomic checkpoints and include an ignore-all `.gitignore`. POSIX directory permissions are restricted; Windows relies on inherited OS ACLs. This is not encryption. Secure the user profile, backups and filesystem yourself. Common credential paths/patterns are rejected, but scanners are incomplete; review every context excerpt before sending it. No original source video or private run data should be published in this public repository.

## Reporting a problem

Do not include secrets, private prompts, authentication files or unredacted session logs in public issues. Provide a minimal synthetic reproduction, OS/Python/CLI versions, the failing stage and a redacted error category. For a security-sensitive issue, use the repository's private vulnerability reporting channel where enabled; otherwise contact the maintainer privately rather than publishing an exploit containing private data.
