# Implementation Summary: Intelligent Agent Crash Handling

**Date**: 2026-02-19
**Status**: ✅ Complete

## Changes Made

### 1. Modified `orchestrator_v2/team/monitor.py`
- Updated `_create_crash_analysis_task()` to create tasks in `tasks/blocked/` instead of `tasks/available/`
- Changed task title to indicate user intervention needed
- Updated description to clarify Assistant's role: analyze and report, not fix orchestrator code
- Task status set to `blocked` to prevent automatic pickup

### 2. Updated `orchestrator_v2/agents/prompts/assistant.md`
- Replaced old crash handling workflow with new user-controlled approach
- Added clear problem categorization table
- Included incident report template
- Added Feishu notification instructions
- Clarified: Assistant analyzes/reports, user fixes/resumes

### 3. Added CLI Command `orchestrator_v2/harness/entrypoint.py`
- New command: `python -m orchestrator_v2 resume-agent <agent_id>`
- Clears crash history and resumes suspended agent
- Monitor will restart agent on next check (~60 seconds)

### 4. Created `decisions/incidents/README.md`
- Documentation for incident report workflow
- Report format specification
- Retention policy

## Key Principle

**Assistant analyzes and reports, user fixes and resumes.**

This keeps orchestrator code stable and under user control, while providing intelligent crash diagnosis.

## Technical Isolation (Already Exists)

The system already prevents agents from modifying orchestrator code through:

1. **Git isolation**: `orchestrator_v2/` is gitignored (line 38 in .gitignore)
2. **Docker isolation**: Code is in read-only `/opt/orchestrator_v2/`
3. **Working directory restriction**: Agents work in `/home/agent/workspace`
4. **Pre-receive hooks**: Validate all pushes

## Workflow

1. Monitor detects 3+ crashes in 30 minutes
2. Monitor creates blocked task: `[系统故障] Agent X 反复崩溃 - 需要用户介入`
3. Assistant analyzes crash logs
4. Assistant creates incident report in `decisions/incidents/INCIDENT-{timestamp}.md`
5. Assistant sends Feishu notification with problem category and fix recommendations
6. User fixes the issue (code/config/environment)
7. User runs: `python -m orchestrator_v2 resume-agent <agent_id>`
8. Monitor restarts agent on next check

## Testing

To test the implementation:

```bash
# Simulate crashes
docker kill orch-agent-implementer-1  # 3 times with 5 second intervals

# Expected: Monitor creates blocked task after 3rd crash

# After Assistant creates incident report:
python -m orchestrator_v2 resume-agent implementer-1

# Expected: Agent resumes on next monitor check
```

## Files Modified

- `orchestrator_v2/team/monitor.py` (not tracked by git - orchestrator code)
- `orchestrator_v2/agents/prompts/assistant.md` (not tracked by git - orchestrator code)
- `orchestrator_v2/harness/entrypoint.py` (not tracked by git - orchestrator code)
- `decisions/incidents/README.md` (tracked, committed: 157a369)

## Notes

- Orchestrator files are not tracked by git (intentionally gitignored)
- Changes are active in the running system
- No code changes needed in `crash_tracker.py` - already implemented correctly
