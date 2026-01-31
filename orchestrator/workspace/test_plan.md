# Test Plan (M1-M4)

## Scope
- Sources: requirements/multi_agent_narrative_system_plan.md, requirements/系统架构与技术规格.md, orchestrator/memory/dev_plan.md
- Policy: minimal static validation (rg/test) until executable tests are available
- All commands use absolute paths so they can run from any working directory

## M1-T1 SnowflakeFlow 6 steps and panel markers
- Command: `rg -n 'snowflake-step-1' /home/zxh/ainovel_v3/project/frontend/src/views/SnowflakeFlow.vue`
  - Threshold: exit code = 0
- Command: `rg -n 'snowflake-step-2' /home/zxh/ainovel_v3/project/frontend/src/views/SnowflakeFlow.vue`
  - Threshold: exit code = 0
- Command: `rg -n 'snowflake-step-3' /home/zxh/ainovel_v3/project/frontend/src/views/SnowflakeFlow.vue`
  - Threshold: exit code = 0
- Command: `rg -n 'snowflake-step-4' /home/zxh/ainovel_v3/project/frontend/src/views/SnowflakeFlow.vue`
  - Threshold: exit code = 0
- Command: `rg -n 'snowflake-step-5' /home/zxh/ainovel_v3/project/frontend/src/views/SnowflakeFlow.vue`
  - Threshold: exit code = 0
- Command: `rg -n 'snowflake-step-6' /home/zxh/ainovel_v3/project/frontend/src/views/SnowflakeFlow.vue`
  - Threshold: exit code = 0
- Command: `rg -n 'snowflake-step-panel' /home/zxh/ainovel_v3/project/frontend/src/views/SnowflakeFlow.vue`
  - Threshold: exit code = 0

## M1-T2 SimulationConsole 3-column layout and linkage
- Command: `rg -n 'sim-panel-left' /home/zxh/ainovel_v3/project/frontend/src/views/SimulationConsole.vue`
  - Threshold: exit code = 0
- Command: `rg -n 'sim-panel-center' /home/zxh/ainovel_v3/project/frontend/src/views/SimulationConsole.vue`
  - Threshold: exit code = 0
- Command: `rg -n 'sim-panel-right' /home/zxh/ainovel_v3/project/frontend/src/views/SimulationConsole.vue`
  - Threshold: exit code = 0
- Command: `rg -n 'sim-log-panel' /home/zxh/ainovel_v3/project/frontend/src/views/SimulationConsole.vue`
  - Threshold: exit code = 0
- Command: `rg -n 'sim-control-panel' /home/zxh/ainovel_v3/project/frontend/src/views/SimulationConsole.vue`
  - Threshold: exit code = 0

## M1-T3 SceneEditor tree/tabs/context panel
- Command: `rg -n 'scene-tree' /home/zxh/ainovel_v3/project/frontend/src/views/SceneEditor.vue`
  - Threshold: exit code = 0
- Command: `rg -n 'scene-tabs' /home/zxh/ainovel_v3/project/frontend/src/views/SceneEditor.vue`
  - Threshold: exit code = 0
- Command: `rg -n 'scene-context-panel' /home/zxh/ainovel_v3/project/frontend/src/views/SceneEditor.vue`
  - Threshold: exit code = 0

## M1-T4 WorldManager tabs
- Command: `rg -n 'world-tab-entities' /home/zxh/ainovel_v3/project/frontend/src/views/WorldManager.vue`
  - Threshold: exit code = 0
- Command: `rg -n 'world-tab-relations' /home/zxh/ainovel_v3/project/frontend/src/views/WorldManager.vue`
  - Threshold: exit code = 0
- Command: `rg -n 'world-tab-anchors' /home/zxh/ainovel_v3/project/frontend/src/views/WorldManager.vue`
  - Threshold: exit code = 0
- Command: `rg -n 'world-tab-subplots' /home/zxh/ainovel_v3/project/frontend/src/views/WorldManager.vue`
  - Threshold: exit code = 0

## M2-T1 API client timeout and interceptors
- Command: `rg -n 'timeout' /home/zxh/ainovel_v3/project/frontend/src/api/index.ts`
  - Threshold: exit code = 0
- Command: `rg -n 'interceptors' /home/zxh/ainovel_v3/project/frontend/src/api/index.ts`
  - Threshold: exit code = 0

## M2-T2 Snowflake API covers step1-step6
- Command: `rg -n 'step1' /home/zxh/ainovel_v3/project/frontend/src/api/snowflake.ts`
  - Threshold: exit code = 0
- Command: `rg -n 'step2' /home/zxh/ainovel_v3/project/frontend/src/api/snowflake.ts`
  - Threshold: exit code = 0
- Command: `rg -n 'step3' /home/zxh/ainovel_v3/project/frontend/src/api/snowflake.ts`
  - Threshold: exit code = 0
- Command: `rg -n 'step4' /home/zxh/ainovel_v3/project/frontend/src/api/snowflake.ts`
  - Threshold: exit code = 0
- Command: `rg -n 'step5' /home/zxh/ainovel_v3/project/frontend/src/api/snowflake.ts`
  - Threshold: exit code = 0
- Command: `rg -n 'step6' /home/zxh/ainovel_v3/project/frontend/src/api/snowflake.ts`
  - Threshold: exit code = 0

## M2-T3 Snowflake data contract aligns types/store
- Command: `rg -n 'steps' /home/zxh/ainovel_v3/project/frontend/src/types/snowflake.ts`
  - Threshold: exit code = 0
- Command: `rg -n 'current_step' /home/zxh/ainovel_v3/project/frontend/src/types/snowflake.ts`
  - Threshold: exit code = 0
- Command: `rg -n 'steps' /home/zxh/ainovel_v3/project/frontend/src/stores/snowflake.ts`
  - Threshold: exit code = 0
- Command: `rg -n 'current_step' /home/zxh/ainovel_v3/project/frontend/src/stores/snowflake.ts`
  - Threshold: exit code = 0

## M3-T1 Subplots list API
- Command: `rg -n '/api/v1/roots/{root_id}/subplots' /home/zxh/ainovel_v3/project/backend/app/main.py`
  - Threshold: exit code = 0

## M3-T2 dirty_scenes returns SceneView[]
- Command: `rg -n 'dirty_scenes' /home/zxh/ainovel_v3/project/backend/app/main.py`
  - Threshold: exit code = 0
- Command: `rg -n 'SceneView' /home/zxh/ainovel_v3/project/backend/app/main.py`
  - Threshold: exit code = 0

## M3-T3 Structure subgraph relationships
- Command: `rg -n '\bHEAD\b' /home/zxh/ainovel_v3/project/backend/app/storage/schema.py`
  - Threshold: exit code = 0
- Command: `rg -n '\bPARENT\b' /home/zxh/ainovel_v3/project/backend/app/storage/schema.py`
  - Threshold: exit code = 0
- Command: `rg -n '\bINCLUDES\b' /home/zxh/ainovel_v3/project/backend/app/storage/schema.py`
  - Threshold: exit code = 0
- Command: `rg -n '\bOF_ORIGIN\b' /home/zxh/ainovel_v3/project/backend/app/storage/schema.py`
  - Threshold: exit code = 0

## M3-T4 Feedback detector divergence/repetition
- Command: `rg -n 'divergence' /home/zxh/ainovel_v3/project/backend/app/services/feedback_detector.py`
  - Threshold: exit code = 0
- Command: `rg -n 'repetition' /home/zxh/ainovel_v3/project/backend/app/services/feedback_detector.py`
  - Threshold: exit code = 0

## M4-T1 Remove google-generativeai dependency
- Command: `rg -n 'google-generativeai' /home/zxh/ainovel_v3/project/backend/pyproject.toml`
  - Threshold: exit code = 1

## M4-T2 Output structure alignment decision doc
- Command: `test -f /home/zxh/ainovel_v3/orchestrator/workspace/structure_alignment.md`
  - Threshold: exit code = 0

## M4-T3 Directory structure alignment (Topone/Storage Port)
- Command: `rg -n 'Topone' /home/zxh/ainovel_v3/project/backend/app/main.py`
  - Threshold: exit code = 0
- Command: `rg -n 'Storage' /home/zxh/ainovel_v3/project/backend/app/main.py`
  - Threshold: exit code = 0
