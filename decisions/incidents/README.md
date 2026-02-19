# Incident Reports

This directory contains reports for system incidents, particularly agent crashes.

## Report Format

Each incident report follows this structure:

- **Filename**: `INCIDENT-{timestamp}.md`
- **Content**: Problem summary, crash logs, root cause analysis, recommended fixes

## Workflow

1. Monitor detects repeated agent crashes (3+ in 30 minutes)
2. Monitor creates blocked assistant task with crash logs
3. Assistant analyzes logs and creates incident report here
4. Assistant notifies user via Feishu
5. User fixes the issue
6. User runs: `python -m orchestrator_v2 resume-agent <agent_id>`
7. Monitor restarts agent on next check

## Report Retention

- Keep reports for debugging and pattern analysis
- Archive old reports after 30 days
