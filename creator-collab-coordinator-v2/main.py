"""
Creator Collaboration Coordinator - API server.
"""

import os
import json
import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse

from models.schemas import CollaborationRequest, AgentSource
from agents.coordinator import CampaignCoordinator

load_dotenv()  # picks up a local .env (see .env.example) if present; no-op otherwise

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

API_KEY = os.environ.get("OPENAI_API_KEY", "")
DATA_DIR = Path(__file__).parent / "data"
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not API_KEY:
        print("\nWARNING: OPENAI_API_KEY not set.")
        print("Set it before running API requests.")
        print("   The app will still start but API calls will fail.\n")
    else:
        print("\nOPENAI_API_KEY detected. Agents are ready.\n")
    yield


app = FastAPI(
    title="Creator Collaboration Coordinator",
    description="Multi-agent brand-creator matching system with shared memory",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz():
    """Liveness/readiness probe — also surfaces whether the OpenAI key is configured."""
    return {
        "status": "ok",
        "openai_key_configured": bool(API_KEY),
        "data_dir_present": DATA_DIR.exists(),
    }


def load_sample_creator_profile(name: str) -> dict:
    path = DATA_DIR / f"creator_profile_{name}.json"
    if not path.exists():
        raise HTTPException(404, f"Sample creator profile '{name}' not found")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_collaboration_guidelines() -> str:
    path = DATA_DIR / "collaboration_guidelines.txt"
    if not path.exists():
        return "Collaboration guidelines not found."
    with open(path, encoding="utf-8") as f:
        return f.read()


@app.get("/api/campaigns")
async def list_scenarios():
    """List available creator-brand collaboration scenarios."""
    samples = []
    if not DATA_DIR.exists():
        return {"scenarios": [], "guidelines_available": False}

    for p in sorted(DATA_DIR.glob("creator_profile_*.json")):
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            samples.append({
                "id": p.stem.replace("creator_profile_", ""),
                "creator_name": data["creator_name"],
                "creator_specialty": data["creator_specialty"],
                "expertise_areas": data.get("expertise_areas", []),
            })
        except Exception as e:
            print(f"Error loading sample {p}: {e}")

    return {"scenarios": samples, "guidelines_available": (DATA_DIR / "collaboration_guidelines.txt").exists()}


@app.get("/api/scenario/{scenario_id}")
async def get_scenario(scenario_id: str):
    """Get a specific creator profile + full collaboration guidelines."""
    creator_profile = load_sample_creator_profile(scenario_id)
    guidelines = load_collaboration_guidelines()
    return {"creator_profile": creator_profile, "guidelines_text": guidelines, "guidelines_length": len(guidelines)}


@app.get("/api/guidelines")
async def get_guidelines():
    """Get the full collaboration guidelines text."""
    return {"text": load_collaboration_guidelines()}


@app.post("/api/match")
async def match_collaboration_stream(request: CollaborationRequest):
    """
    Match a creator with a brand and stream results via SSE.
    """
    if not API_KEY:
        raise HTTPException(500, "OPENAI_API_KEY not configured")

    coordinator = CampaignCoordinator(api_key=API_KEY)

    # Subscribe to ledger events BEFORE processing starts
    event_queue = coordinator.ledger.subscribe()

    async def event_stream():
        # Start processing in background. A Future (rather than a fixed sleep)
        # is what lets the consumer below wait deterministically for
        # run_matching() to actually finish writing its result, instead of
        # racing a guessed delay against the coordinator's final return.
        result_future: asyncio.Future = asyncio.get_running_loop().create_future()

        async def run_matching():
            try:
                result = await coordinator.process_collaboration(
                    creator_profile=request.creator_profile,
                    guidelines_text=request.brand_guidelines,
                    brand_name=request.brand_name,
                )
                if not result_future.done():
                    result_future.set_result(result)
            except Exception as e:
                logging.exception("Matching pipeline failed")
                if not result_future.done():
                    result_future.set_exception(e)
                # Write error to ledger so the stream gets it
                await coordinator.ledger.write(
                    source=AgentSource.SYSTEM,
                    event_type="ERROR",
                    message=f"Matching error: {str(e)}",
                    tags=["ERROR"],
                )

        asyncio.create_task(run_matching())

        # Stream events as they come in
        while True:
            try:
                entry = await asyncio.wait_for(event_queue.get(), timeout=120.0)
                event_data = {
                    "id": entry.id,
                    "timestamp": entry.timestamp.isoformat(),
                    "source": entry.source.value,
                    "event_type": entry.event_type,
                    "message": entry.message,
                    "data": entry.data,
                    "tags": entry.tags,
                    "severity": entry.severity.value,
                }
                yield f"data: {json.dumps(event_data)}\n\n"

                # Check if processing is complete
                if entry.event_type == "PROCESS_COMPLETE":
                    try:
                        result = await asyncio.wait_for(result_future, timeout=10.0)
                    except Exception:
                        result = None
                    if result:
                        # Serialize datetime objects
                        if "ledger" in result:
                            for le in result["ledger"]:
                                if hasattr(le.get("timestamp"), "isoformat"):
                                    le["timestamp"] = le["timestamp"].isoformat()
                        yield f"event: result\ndata: {json.dumps(result, default=str)}\n\n"
                    break

                if entry.event_type == "ERROR":
                    yield f"event: error\ndata: {json.dumps({'error': entry.message})}\n\n"
                    break

            except asyncio.TimeoutError:
                yield f"event: keepalive\ndata: {json.dumps({'status': 'processing'})}\n\n"

            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                break

        coordinator.ledger.unsubscribe(event_queue)
        yield f"event: done\ndata: {json.dumps({'status': 'complete'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/")
async def serve_frontend():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse("<h1>Frontend not found. Ensure static/index.html exists.</h1>")
    
    with open(index_path, encoding="utf-8") as f:
        return HTMLResponse(f.read())


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    print("Creator Collaboration Coordinator")
    print()
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")