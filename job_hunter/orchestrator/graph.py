from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from orchestrator.state import JobDepartmentGraphState
from orchestrator.nodes import OrchestratorNodes

class GraphBuilder:
    def __init__(self, nodes_impl: OrchestratorNodes):
        self.nodes_impl = nodes_impl
        
    def check_high_match(self, state: JobDepartmentGraphState) -> str:
        """Conditional routing based on presence of HIGH_MATCH jobs."""
        high_match = self.nodes_impl.repo.get_pending_jobs("HIGH_MATCH")
        if high_match:
            return "deepening"
        else:
            return "supervisor"

    def build(self, checkpointer=None):
        workflow = StateGraph(JobDepartmentGraphState)
        
        workflow.add_node("discovery", self.nodes_impl.discovery_node)
        workflow.add_node("filter", self.nodes_impl.filter_node)
        workflow.add_node("deepening", self.nodes_impl.deepening_node)
        workflow.add_node("tailoring", self.nodes_impl.tailor_node)
        workflow.add_node("supervisor", self.nodes_impl.supervisor_manager_node)
        workflow.add_node("submission", self.nodes_impl.submission_gate_node)
        
        workflow.add_edge(START, "discovery")
        workflow.add_edge("discovery", "filter")
        
        # Conditional edge
        workflow.add_conditional_edges(
            "filter",
            self.check_high_match,
            {
                "deepening": "deepening",
                "supervisor": "supervisor"
            }
        )
        
        workflow.add_edge("deepening", "tailoring")
        workflow.add_edge("tailoring", "supervisor")
        workflow.add_edge("supervisor", "submission")
        workflow.add_edge("submission", END)
        
        if checkpointer is None:
            checkpointer = MemorySaver()
        app = workflow.compile(checkpointer=checkpointer)
        return app
