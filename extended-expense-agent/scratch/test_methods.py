from expense_agent.agent_runtime_app import agent_runtime

print(dir(agent_runtime))
if hasattr(agent_runtime, 'create_session'):
    print("Has create_session")
