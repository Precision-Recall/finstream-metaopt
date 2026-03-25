import os
from strands import Agent
from strands.models import BedrockModel
from tools.context import firebase_context
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands.vended_plugins.skills import AgentSkills
#Creating a BedrockModel

bedrock_model = BedrockModel(
    model_id="meta.llama4-maverick-17b-instruct-v1:0",
    temperature=0.7,
    top_p=0.9 
)

# Point to your skills directory
skills_plugin = AgentSkills(
    skills=[
        os.path.join(os.path.dirname(__file__), "skills/finstream-context")
    ]
)

SYSTEM_PROMPT = """You are the Finstream assistant. You have access to:
1. firebase_context tool — fetches live data from Firebase. Call this first
   before answering anything about predictions, evaluations, drift, or 
   model state. Never guess live values.
2. skills tool — loads the finstream-context skill when you need to understand
   how the system works (drift detection, MHO council, feature engineering etc.)"""

#Creating an Agent
app = BedrockAgentCoreApp()
def create_agent() -> Agent:
    return Agent(
        model=bedrock_model,
        system_prompt=SYSTEM_PROMPT,
        tools=[firebase_context],
        plugins=[skills_plugin]
    )

agent = create_agent()

@app.entrypoint
def chatbot(request):
    try:
        body = request.json()

        message = body.get("message", "")
        history = body.get("history", [])

        conversation = ""
        for turn in history:
            conversation += f"{turn['role']}: {turn['content']}\n"

        conversation += f"user: {message}"

        response = agent(conversation)

        return {"response": str(response)}

    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    app.run()