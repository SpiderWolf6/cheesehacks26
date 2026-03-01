import logging
from orchestrator.engine import Orchestrator, DEFAULT_WWF_EARTH_DAY_BRIEF

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

orch = Orchestrator()
result = orch.run_full_pipeline("wwf-earth-day", DEFAULT_WWF_EARTH_DAY_BRIEF)

print(f"\nTotal sprints: {result['total_sprints']}")
print(f"Workspace: {result['workspace']}")
for sr in result["sprint_results"]:
    print(f"\nSprint {sr['sprint']}:")
    for tid, task_result in sr["tasks"].items():
        status = "PASS" if task_result["success"] else "FAIL"
        print(f"  [{status}] {task_result.get('summary', '')[:100]}")