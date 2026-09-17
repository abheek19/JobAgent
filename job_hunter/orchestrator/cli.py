import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from langgraph.types import Command
import sys

from orchestrator.state import JobDepartmentGraphState

async def run_cli(app, thread_id: str, lane: str):
    console = Console()
    
    config = {"configurable": {"thread_id": thread_id}}
    
    initial_state = {
        "thread_id": thread_id,
        "lane": lane,
        "candidate_cv": {},
        "target_preferences": {},
        "pending_job_ids": [],
        "current_stage": "init",
        "human_decision": None,
        "active_alerts": [],
        "review_feedback": None
    }
    
    console.print(f"[bold blue]Starting Job Hunter Pipeline ({lane})[/bold blue]")
    
    # Start graph
    try:
        async for event in app.astream(initial_state, config, stream_mode="values"):
            stage = event.get("current_stage", "unknown")
            console.print(f"[dim]Transitioned to stage: {stage}[/dim]")
    except Exception as e:
        console.print(f"[bold red]Graph execution error: {e}[/bold red]")
        raise
        
    state = app.get_state(config)
    
    # Check if interrupted
    if state.next:
        console.print("\n[bold yellow]Pipeline paused for Human-in-the-Loop review.[/bold yellow]")
        
        alerts = []
        if state.tasks and state.tasks[0].interrupts:
            alerts = state.tasks[0].interrupts[0].value
            
        if not alerts:
            console.print("[bold green]No jobs require approval at this time.[/bold green]")
            # Resume with no decision just to finish the graph
            async for event in app.astream(Command(resume=None), config, stream_mode="values"):
                pass
            console.print("[bold green]Pipeline finished.[/bold green]")
            return
            
        for alert in alerts:
            table = Table(show_header=False, box=None)
            table.add_row("[bold]Company[/bold]", alert["company"])
            table.add_row("[bold]Role[/bold]", alert["role"])
            table.add_row("[bold]Match[/bold]", alert["match_evidence"])
            
            # Truncate summary for display
            summary = alert["business_summary"]
            if len(summary) > 100:
                summary = summary[:100] + "..."
            table.add_row("[bold]Summary[/bold]", summary)
            
            table.add_row("[bold]Contact[/bold]", alert["contact_name"])
            console.print(Panel(table, title=f"[bold green]Job ID: {alert['job_id']}[/bold green]", expand=False))
            
        console.print("\n[bold]Please review the pending applications above.[/bold]")
        decision = Prompt.ask("Action", choices=["APPROVE", "REJECT", "REVISE", "QUIT"])
        
        if decision == "QUIT":
            console.print("[bold red]Aborting review. Pipeline remains paused.[/bold red]")
            return
            
        console.print(f"\n[bold blue]Resuming graph with decision: {decision}[/bold blue]")
        
        try:
            async for event in app.astream(Command(resume=decision), config, stream_mode="values"):
                stage = event.get("current_stage", "unknown")
                console.print(f"[dim]Transitioned to stage: {stage}[/dim]")
        except Exception as e:
            console.print(f"[bold red]Graph resumption error: {e}[/bold red]")
            raise
            
    console.print("\n[bold green]Pipeline execution completed![/bold green]")
