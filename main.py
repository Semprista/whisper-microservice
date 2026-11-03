from fastapi import BackgroundTasks, FastAPI, UploadFile, HTTPException, Response
import whisper
from pathlib import Path
import aiofiles

UPLOAD_DIR = Path("temp")
UPLOAD_DIR.mkdir(exist_ok=True)
ALLOWED_CONTENT_TYPES = {"video/mp4", "audio/mp3", "audio/aac", "audio/mp4", "audio/mpeg", "audio/ogg", "audio/vnd.wav"}

app = FastAPI()
model = whisper.load_model("base") # 1Gb of VRAM
tasks = []

def transcribe(filename: str, task_id: int) -> None:
    tasks[task_id]["status"] = "Transcribing"

    try:
        result = model.transcribe("/temp" + filename) # test for now
        tasks[task_id]["status"] = "OK"
        tasks[task_id]["result"] = result["text"]
    except Exception as e:
        tasks[task_id]["status"] = "ERROR"
        tasks[task_id]["error"] = str(e)

@app.post("/transcribe")
async def upload_file(file: UploadFile, background_task: BackgroundTasks):
    target = UPLOAD_DIR / file.filename

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(415, "Unsupported file type")

    async with aiofiles.open(target, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            await out.write(chunk)

    task_id = "0001"
    tasks.append({
        task_id: {
            "filename": file.filename,
            "status": "Loading file",
            "result": None,
            "error": None
        }
    })
    background_task.add_task(transcribe, "audio.mp3", 0001)
    
    return {"task_id": task_id}

@app.get("/transcribe/{id}")
async def lookup_task(task_id: int):
    return tasks[task_id]

@app.get("/transcribe/{id}/result")
async def transcription_result(task_id: int):
    return {
        "task_id": task_id,
        "content": tasks[task_id]["result"]
    }