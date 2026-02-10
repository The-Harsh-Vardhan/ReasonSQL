"""Quick test for AgentAction field fix."""
print("Testing AgentAction field fix...")

try:
    from models.schemas import AgentAction
    
    # Test creating AgentAction with all required fields
    action = AgentAction(
        agent_name="test_agent",
        action="test_action",
        input_summary="test input",
        output_summary="test output"
    )
    print("✓ AgentAction creation successful")
    print(f"  Agent: {action.agent_name}")
    print(f"  Action: {action.action}")
    print(f"  Input Summary: {action.input_summary}")
    print(f"  Output Summary: {action.output_summary}")
    
    # Try creating without input_summary - should fail
    try:
        bad_action = AgentAction(
            agent_name="test",
            action="test",
            output_summary="test"
        )
        print("✗ FAIL: Should have required input_summary!")
    except Exception as e:
        print(f"✓ Correctly rejects missing input_summary: {type(e).__name__}")
    
    print("\n✅ All AgentAction field validations passed!")
    
except Exception as e:
    print(f"✗ FAIL: {e}")
    import traceback
    traceback.print_exc()
