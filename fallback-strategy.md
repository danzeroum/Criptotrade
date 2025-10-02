# Progressive Fallback Strategy

The BuildToValue orchestration layer embeds progressive fallback pathways to maintain service continuity whenever a pattern fails or becomes unreliable.

## Fallback Hierarchy

1. **Primary Pattern → Simplified Pattern**  
   When a high-complexity capability fails health checks, orchestration diverts execution to a simplified pattern variant with reduced requirements.
2. **Simplified Pattern → Human Intervention**  
   If the simplified pattern still cannot satisfy acceptance criteria, the system escalates to a human operator with full telemetry and context packages.
3. **Human Intervention → Safe Mode**  
   When human assistance is unavailable or exceeds configured latency budgets, the agent transitions to safe mode with minimal capabilities enabled.

## Example Scenario

- **Planning (complex)** → **Prompt Chaining (simpler)** → **Human-in-the-loop**

## Governance Rules

- Fallback transitions are logged in the agent decision ledger with timestamps, trace identifiers, and rationale codes.
- Guardrails must validate state consistency before and after each fallback handoff.
- Safe mode restricts the agent to read-only tools, pre-approved prompts, and static knowledge sources until manual recovery is completed.
