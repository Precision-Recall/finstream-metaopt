import os
from chalice import Chalice, CORSConfig
from strands import Agent
from strands.models import BedrockModel
from strands.vended_plugins.skills import AgentSkills
from chalicelib.tools.context import firebase_context

# --- Agent setup ---
bedrock_model = BedrockModel(
    model_id="us.meta.llama4-maverick-17b-instruct-v1:0",
    temperature=0.7,
    top_p=0.9,
    streaming=False,
)

skills_plugin = AgentSkills(
    skills=[os.path.join(os.path.dirname(__file__), "chalicelib/skills/finstream-context")]
)

SYSTEM_PROMPT = """You are the Finstream assistant. You have access to:
1. firebase_context tool — fetches live data from Firebase. Call this first
   before answering anything about predictions, evaluations, drift, or
   model state. Never guess live values.
2. skills tool — loads the finstream-context skill when you need to understand
   how the system works (drift detection, MHO council, feature engineering etc.)"""

agent = Agent(
    model=bedrock_model,
    system_prompt=SYSTEM_PROMPT,
    tools=[firebase_context],
    plugins=[skills_plugin],
)

# --- Chalice app ---
cors = CORSConfig(allow_origin="*")
app = Chalice(app_name="chatbot-finstream")

@app.route("/", cors=cors)
def health():
    return {"status": "ok"}

@app.route("/chat", methods=["POST"], cors=cors, content_types=["application/json"])
def chat():
    body = app.current_request.json_body
    try:
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
