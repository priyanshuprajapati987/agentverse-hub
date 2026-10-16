"""Test AgentVerse Hub backend"""
from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

# Test health
r = client.get('/health')
print('Health:', r.json())

# Test agents list
r = client.get('/api/agents/')
data = r.json()
print(f'Agents: {data["total"]} total')

# Test categories
r = client.get('/api/agents/categories')
cats = r.json()
for c in cats['categories']:
    print(f'  {c["name"]}: {c["count"]} agents')

# Test run agent
print()
print('Testing Python Developer agent...')
r = client.post('/api/agents/run', json={
    'agent_id': 'python-dev',
    'message': 'Write a hello world in Python',
})
data = r.json()
print(f'Success: {data["success"]}')
print(f'Output: {data["output"][:300]}')
