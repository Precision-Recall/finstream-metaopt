import os
from dotenv import load_dotenv
from strands_builder import AgentCoreRuntime

load_dotenv()

runtime = AgentCoreRuntime(
    agent_name="finstream-chatbot",
    entry_point="agentConfig:handler",
    requirements_file="requirements.txt",
    environment={
        "FIREBASE_PROJECT_ID": os.getenv("FIREBASE_PROJECT_ID"),
        "FIREBASE_API_KEY":    os.getenv("FIREBASE_API_KEY"),
    },
    region="us-east-1"
)

endpoint = runtime.deploy()
print(f"\n✅ Deployed successfully")
print(f"Endpoint: {endpoint}")
print(f"\nAdd this to Render env vars:")
print(f"CHATBOT_URL = {endpoint}")