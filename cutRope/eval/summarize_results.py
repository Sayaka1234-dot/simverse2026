import json
import os
from pathlib import Path
from collections import defaultdict

def summarize():
    eval_dir = Path(__file__).resolve().parent
    results_root = eval_dir / "results"
    
    if not results_root.exists():
        print(f"Results directory not found at {results_root}")
        return

    model_dirs = [d for d in results_root.iterdir() if d.is_dir()]
    
    if not model_dirs:
        print("No model result directories found.")
        return

    summary = []
    
    for model_dir in sorted(model_dirs):
        model_name = model_dir.name
        json_files = list(model_dir.glob("*.json"))
        
        if not json_files:
            continue
            
        total = len(json_files)
        won = 0
        total_stars = 0
        total_score = 0
        total_time = 0
        won_time = 0
        
        status_counts = defaultdict(int)
        failure_reasons = defaultdict(int)
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                eval_data = data.get("evaluation", {})
                status = eval_data.get("evaluation_status")
                is_won = eval_data.get("won", False)
                
                status_counts[status] += 1
                
                if is_won:
                    won += 1
                    total_stars += eval_data.get("stars", 0)
                    total_score += eval_data.get("score", 0)
                    won_time += eval_data.get("time", 0)
                else:
                    reason = eval_data.get("reason", "unknown")
                    failure_reasons[reason] += 1
                
                total_time += eval_data.get("time", 0)
                
            except Exception as e:
                print(f"Error reading {json_file}: {e}")

        pass_rate = (won / total * 100) if total > 0 else 0
        avg_stars = (total_stars / won) if won > 0 else 0
        avg_score = (total_score / won) if won > 0 else 0
        avg_time_won = (won_time / won) if won > 0 else 0
        avg_time_all = (total_time / total) if total > 0 else 0
        
        summary.append({
            "Model": model_name,
            "Total": total,
            "Won": won,
            "Pass Rate": f"{pass_rate:.2f}%",
            "Avg Stars (Won)": f"{avg_stars:.2f}",
            "Avg Score (Won)": f"{avg_score:.2f}",
            "Avg Time (Won)": f"{avg_time_won:.2f}s",
            "Status": dict(status_counts),
            "Failure Reasons": dict(failure_reasons)
        })

    # Print table
    header = f"{'Model':<40} | {'Total':<5} | {'Won':<5} | {'Pass Rate':<10} | {'Avg Stars':<10}"
    print(header)
    print("-" * len(header))
    for s in summary:
        print(f"{s['Model']:<40} | {s['Total']:<5} | {s['Won']:<5} | {s['Pass Rate']:<10} | {s['Avg Stars (Won)']:<10}")
        
    print("\nDetailed Status Counts:")
    for s in summary:
        print(f"{s['Model']}: {s['Status']}")

    print("\nFailure Reasons (for non-wins):")
    for s in summary:
        if s['Failure Reasons']:
            print(f"{s['Model']}: {s['Failure Reasons']}")

if __name__ == "__main__":
    summarize()
