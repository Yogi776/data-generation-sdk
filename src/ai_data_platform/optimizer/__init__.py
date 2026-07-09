"""Performance planning layer: size a generation run before executing it.

Pure analysis over the Plan-IR (`GenerationPlan`) — estimates memory, recommends
batch size / parallelism / format / partitioning, classifies runtime, and emits
an execution plan with actionable optimization warnings. No generation, no I/O.
"""

from ai_data_platform.optimizer.complexity_analyzer import analyze_complexity
from ai_data_platform.optimizer.execution_planner import plan_execution
from ai_data_platform.optimizer.memory_estimator import estimate_memory

__all__ = ["analyze_complexity", "estimate_memory", "plan_execution"]
