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

SYSTEM_PROMPT = """You are Finstream AI, a helpful assistant for the Finstream concept-drift monitoring platform.

## Tools available
1. firebase_context — fetches live data (predictions, evaluations, drift events, model state) from Firebase.
   Call this FIRST whenever the user asks about live values, today's prediction, drift status, model weights,
   or anything that requires up-to-date data. Never guess or fabricate live values.
2. skills — loads the finstream-context knowledge skill when the user asks how the system works
   (drift detection, MHO council, PSO/GA/GWO algorithms, feature engineering, NIFTY 50, etc.).

## Critical output rules — follow these without exception
- ALWAYS reply in plain, conversational English sentences.
- NEVER output Python code, import statements, print() calls, or any programming constructs in your reply.
- NEVER wrap your answer in markdown code fences (``` or `).
- Do NOT narrate what you are doing ("I will now call…"). Just answer.
- Be concise and friendly. Use bullet points only when listing multiple items.
- If the user says hi / hello / greets you, reply with a short friendly greeting and offer to help."""

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

        result = agent(conversation)

        # Extract the final text from the AgentResult object.
        # strands AgentResult exposes .message (str) or falls back to its string repr.
        if hasattr(result, "message") and result.message:
            reply = result.message
        elif hasattr(result, "content") and result.content:
            reply = result.content
        else:
            reply = str(result)

        return {"response": reply}
    except Exception as e:
        return {"error": str(e)}
