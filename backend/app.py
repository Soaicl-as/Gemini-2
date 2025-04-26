from fastapi import FastAPI, Request, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware # Required for local testing if frontend is on different port
import uvicorn
import time
import json
import os # Import os to access environment variables
import asyncio # Import asyncio for the log_generator sleep
from typing import List, Dict

# Corrected import: Use relative import for modules within the same package (backend)
from .instagram_client import login, complete_2fa, get_user_id, get_followers_or_following, send_mass_dm, is_logged_in
from .logger import get_logs, log_message # Use relative import for logger

app = FastAPI()

# CORS middleware for local development (allows frontend on different port)
# Remove or adjust in production if frontend is served from the same origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Be more specific in production, e.g., ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory for the frontend
# Ensure the path is correct relative to where the app is run
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serves the frontend index.html file."""
    # Ensure the path to index.html is correct
    try:
        with open("frontend/index.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Frontend index.html not found. Ensure the 'frontend' directory is in the correct location.")


@app.post("/login")
async def handle_login(username: str = Form(...), password: str = Form(...)):
    """Handles the login request."""
    result = login(username, password)
    return result

@app.post("/complete-2fa")
async def handle_complete_2fa(code: str = Form(...)):
    """Handles the 2FA completion request."""
    result = complete_2fa(code)
    return result

@app.get("/status")
async def get_status():
    """Returns the current login status."""
    return {"logged_in": is_logged_in()}

@app.post("/get-list")
async def handle_get_list(target_username: str = Form(...), list_type: str = Form(...)):
    """Handles requests to get followers or following list."""
    if not is_logged_in():
        raise HTTPException(status_code=401, detail="Not logged in.")

    user_id = get_user_id(target_username)
    if not user_id:
        raise HTTPException(status_code=404, detail=f"User '{target_username}' not found or not public.")

    result = get_followers_or_following(user_id, list_type)
    if result.get("status") == "error":
         raise HTTPException(status_code=500, detail=result.get("message"))
    if result.get("status") == "warning":
         # Return a 200 with a warning status
         return result

    return result

@app.post("/send-dm")
async def handle_send_dm(
    background_tasks: BackgroundTasks,
    recipient_pks: str = Form(...), # Comma-separated string of PKS
    message: str = Form(...),
    min_delay: int = Form(...),
    max_delay: int = Form(...),
    max_recipients: int = Form(...)
):
    """Handles the mass DM sending request."""
    if not is_logged_in():
        raise HTTPException(status_code=401, detail="Not logged in.")

    try:
        # Convert comma-separated string of PKS to a list of integers
        pks_list = [int(pk.strip()) for pk in recipient_pks.split(',') if pk.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid recipient PKS format. Must be comma-separated numbers.")

    if not pks_list:
         raise HTTPException(status_code=400, detail="No recipients provided.")

    if not message:
         raise HTTPException(status_code=400, detail="Message cannot be empty.")

    if min_delay < 0 or max_delay < 0 or min_delay > max_delay or min_delay > max_recipients: # Added check for min_delay vs max_recipients (might be a typo, assuming min_delay shouldn't exceed max_delay)
         raise HTTPException(status_code=400, detail="Invalid delay range or maximum recipients.")

    if max_recipients <= 0:
         raise HTTPException(status_code=400, detail="Maximum recipients must be a positive number.")

    # Run the potentially long-running send_mass_dm task in the background
    # so the API call returns immediately. Logs will be streamed via /logs.
    # Pass only the required number of recipients to the background task
    recipients_to_message = pks_list[:max_recipients]
    background_tasks.add_task(send_mass_dm, recipients_to_message, message, min_delay, max_delay, max_recipients)


    return {"status": "processing", "message": f"Mass DM task started in the background for up to {len(recipients_to_message)} recipients. Check logs for progress."}


@app.get("/logs")
async def stream_logs():
    """Streams logs to the frontend using Server-Sent Events."""
    async def log_generator():
        while True:
            logs = get_logs()
            if logs:
                for log in logs:
                    # SSE format: data: [log message]\n\n
                    yield f"data: {json.dumps({'log': log})}\n\n"
            await asyncio.sleep(0.5) # Check for new logs more frequently

    return StreamingResponse(log_generator(), media_type="text/event-stream")


# To run locally: uvicorn backend.app:app --reload --port 8000
# For Render: uvicorn backend.app:app --host 0.0.0.0 --port $PORT
# The __name__ == "__main__": block is for local development/testing.
# Render's entrypoint command handles running uvicorn directly.
# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

