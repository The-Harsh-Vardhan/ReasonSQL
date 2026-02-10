"""Show AGENT_PIPELINE.md summary"""
import os

file_path = "AGENT_PIPELINE.md"

if os.path.exists(file_path):
    size = os.path.getsize(file_path)
    
    print("="*70)
    print("AGENT PIPELINE DOCUMENTATION CREATED")
    print("="*70)
    print()
    print(f"File: {file_path}")
    print(f"Size: {size:,} bytes ({size/1024:.1f} KB)")
    print()
    print("Contents Overview:")
    print("  - Pipeline Overview (visual diagram)")
    print("  - 12 Agent Detailed Descriptions")
    print("  - Batch-by-Batch Flow Explanation")
    print("  - Self-Correction Loop Visualization")
    print("  - Performance Metrics & Timing")
    print("  - LLM Call Distribution")
    print("  - Agent Roles Summary (LLM vs Rule-based)")
    print("  - Critical Decision Points")
    print("  - Complete Example Pipeline Trace")
    print("  - Key Innovations")
    print()
    print("Sections:")
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        sections = [line.strip() for line in lines if line.startswith('##')]
        for i, section in enumerate(sections[:15], 1):
            print(f"  {i}. {section}")
    
    print()
    print("="*70)
    print("VIEW THE FILE:")
    print(f"  code {file_path}")
    print("  OR open it in your editor")
    print("="*70)
else:
    print(f"Error: {file_path} not found")
