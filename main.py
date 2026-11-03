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
TRANSCRIPTION_LANGUAGES = {"en", "fr"}
MAX_MB = 200
MAX_BYTES = MAX_MB * 1024 * 1024

app = FastAPI()
model = whisper.load_model("base", device="cuda") # 1Gb of VRAM
tasks = {}

class TaskStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class TaskOut(BaseModel):
    id: str
    status: TaskStatus
    result: str | None
    error: str | None

def transcribe(filename: str, language: str, task_id: str) -> None:
    task: TaskOut = tasks.get(task_id)

    if task is None:
        return
    
    try:
        task.status = TaskStatus.RUNNING
        result = model.transcribe(f"{UPLOAD_DIR}/{filename}", language=language)
        task.status = TaskStatus.COMPLETED
        task.result = result["text"]
    except Exception as e:
        if task is not None:
            task.status = TaskStatus.FAILED
            task.error = str(e)

        print(str(e))

@app.post("/transcribe")
async def upload_file(file: UploadFile, language: str, background_task: BackgroundTasks):
    length = file.size

    if not length or int(length) > MAX_BYTES:
        raise HTTPException(400, f"Max size is {MAX_MB} MB")
    
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(415, "Unsupported file type")

    if language not in TRANSCRIPTION_LANGUAGES:
        raise HTTPException(400, f"Unknown language ('{language}')")

    new_filename = str(uuid.uuid4()) + Path(file.filename).suffix
    target = UPLOAD_DIR / new_filename

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
    
    background_task.add_task(transcribe, new_filename, language, new_task.id)
    
    return {"task_id": task_id}

@app.get("/transcribe/{task_id}", response_model=TaskOut)
async def lookup_task(task_id: str):
    task = tasks.get(task_id)

    if task is None:
        raise HTTPException(404, f"task '{task_id}' not found")
    
    return task

@app.get("/transcribe/{task_id}/result")
async def transcription_result(task_id: str):
    task: TaskOut = tasks.get(task_id)

    if task is not None:
        return {
            "task_id": task.id,
            "content": task.result,
            "error": task.error
        }
    else:
        raise HTTPException(404, f"Task '{task_id}' not found.")