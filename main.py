import aiofiles
from enum import Enum
from fastapi import BackgroundTasks, FastAPI, UploadFile, HTTPException
from pathlib import Path
from pydantic import BaseModel
import uuid
import whisper

UPLOAD_DIR = Path("temp")
UPLOAD_DIR.mkdir(exist_ok=True)
ALLOWED_CONTENT_TYPES = {"video/mp4", "audio/mp3", "audio/aac", "audio/mp4", "audio/mpeg", "audio/ogg", "audio/vnd.wav"}
MAX_MB = 200
MAX_BYTES = MAX_MB * 1024 * 1024

app = FastAPI()
model = whisper.load_model("base") # 1Gb of VRAM
tasks = {}

class TaskStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class TaskOut(BaseModel):
    id: str
    status: str
    result: TaskStatus
    error: str | None

def transcribe(filename: str, task_id: str) -> None:
    tasks[task_id]["status"] = TaskStatus.RUNNING

    try:
        result = model.transcribe(f"{UPLOAD_DIR}/{filename}")
        tasks[task_id]["status"] = TaskStatus.COMPLETED
        tasks[task_id]["result"] = result["text"]
    except Exception as e:
        tasks[task_id]["status"] = TaskStatus.FAILED
        tasks[task_id]["error"] = str(e)

@app.post("/transcribe")
async def upload_file(file: UploadFile, background_task: BackgroundTasks):
    length = file.size

    if not length or int(length) > MAX_BYTES:
        raise HTTPException(413, f"Max size is {MAX_MB} MB")

    new_filename = f"{str(uuid.uuid4())}.{Path(file.filename).suffix}"
    target = UPLOAD_DIR / new_filename

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(415, "Unsupported file type")

    async with aiofiles.open(target, "wb") as out:
        total = 0
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_BYTES:
                raise HTTPException(413, f"Max size is {MAX_MB} MB")
            await out.write(chunk)

    task_id = uuid.uuid4()

    new_task = TaskOut(
        id=str(task_id),
        status=TaskStatus.PENDING,
        result=None,
        error=None
    )

    tasks[str(task_id)] = new_task
    
    background_task.add_task(transcribe, new_filename, new_task.id)
    
    return {"task_id": task_id}

@app.get("/transcribe/{task_id}", response_model=TaskOut)
async def lookup_task(task_id: str):
    task = tasks[task_id]

    if task is None:
        raise HTTPException(500, f"task '{task_id}' not found")
    else:
        return tasks[task_id]

@app.get("/transcribe/{task_id}/result")
async def transcription_result(task_id: str):
    task: TaskOut = tasks[task_id]

    return {
        "task_id": task.id,
        "content": task.result,
        "error": task.error
    }