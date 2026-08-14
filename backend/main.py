from security import hash_password
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
import os
import cloudinary
import cloudinary.uploader
import whisper
import yt_dlp
import uuid
import subprocess
import json
from rag import search_chunks
from vector_store import create_vector_store
from sqlalchemy.orm import Session
from models import CourseChatHistory
from fastapi.middleware.cors import CORSMiddleware
from schemas import (
    CourseChatRequest,
    CourseChatResponse
)
from fastapi.staticfiles import StaticFiles
from fastapi import UploadFile, File, Form,BackgroundTasks
from typing import List

from models import CourseMaterial
from schemas import CourseMaterialResponse
from video_transcription import transcribe_video
from models import User, Course, Enrollment, CourseVideo,CourseMaterial,CourseAudio,CourseImage,VideoTranscript,VideoTranscriptSegment
from schemas import VideoCreate, VideoResponse

from text_splitter import split_text

from schemas import (
    UserCreate,
    UserResponse,
    UserUpdate,
    PasswordChange,
    UserLogin,
    CourseCreate,
    CourseUpdate,
    CourseResponse,
    EnrollmentCreate,
    EnrollmentResponse,
    ProgressUpdate
)
from langchain_core.documents import Document
from security import (
    hash_password,
    verify_password,
    create_access_token
)

from pdf_utils import extract_pdf_text
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from security import verify_access_token
from models import Course
from database import engine, Base, get_db

Base.metadata.create_all(bind=engine)

security = HTTPBearer()

# -----------------------------
# Load Environment Variables
# -----------------------------
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# -----------------------------
# Gemini Client
# -----------------------------
api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)


# -----------------------------
# Cloudinary Configuration
# -----------------------------

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

# -----------------------------
# FastAPI App
# -----------------------------
app = FastAPI()
UPLOAD_DIR = os.path.join(
    os.path.dirname(__file__),
    "uploads"
)

os.makedirs(
UPLOAD_DIR,
exist_ok=True
)

app.mount(
    "/uploads",
    StaticFiles(
        directory=UPLOAD_DIR
    ),
    name="uploads"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "https://coursera-multimodal-intelligence-platform-6wvy.onrender.com",
        "https://coursera-multimodal-intelligence.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Request Model
# -----------------------------
class ChatRequest(BaseModel):
    message: str


# -----------------------------
# Home Route
# -----------------------------
@app.get("/")
def home():
    return {
        "message": "Welcome to Multimodal Intelligence Platform"
    }


# -----------------------------
# About Route
# -----------------------------
@app.get("/about")
def about():
    return {
        "project": "Multimodal Intelligence Platform",
        "developer": "Sumit Mishra"
    }


# -----------------------------
# Chat Route
# -----------------------------
@app.post("/chat")
def chat(request: ChatRequest):

    try:

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=request.message
        )

        return {
            "reply": response.text
        }

    except Exception as e:

        # amazonq-ignore-next-line
        return {
            "error": str(e)
        }

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):

    token = credentials.credentials

    email = verify_access_token(token)

    user = db.query(User).filter(
        User.email == email
    ).first()

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return user


def admin_required(
    current_user: User = Depends(get_current_user)
):

    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only admin can access this resource"
        )

    return current_user


@app.get("/users", response_model=list[UserResponse])
def get_users(
    current_user: User = Depends(admin_required),
    db: Session = Depends(get_db)
):
    users = db.query(User).all()
    return users


@app.post("/users", response_model=UserResponse)
def create_user(
    user: UserCreate,
    current_user: User = Depends(admin_required),
    db: Session = Depends(get_db)
):

    hashed_password = hash_password(user.password)

    new_user = User(
        full_name=user.full_name,
        email=user.email,
        password=hashed_password,
        role=user.role
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.user_id == user_id
    ).first()

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return user


@app.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    updated_user: UserUpdate,
    current_user: User = Depends(admin_required),
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.user_id == user_id
    ).first()

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    user.full_name = updated_user.full_name
    user.email = updated_user.email

    if updated_user.password:
        user.password = hash_password(updated_user.password)

    db.commit()
    db.refresh(user)

    return user

@app.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    current_user: User = Depends(admin_required),
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.user_id == user_id
    ).first()

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    db.delete(user)
    db.commit()

    return {
        "message": "User deleted successfully"
    }


@app.post("/login")
def login(
    login: UserLogin,
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.email == login.email
    ).first()

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not verify_password(
        login.password,
        user.password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    token = create_access_token(
        data={
            "sub": user.email
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }

@app.put("/change-password")
def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(
        password_data.current_password,
        current_user.password
    ):
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect"
        )

    if len(password_data.new_password) < 6:
        raise HTTPException(
            status_code=400,
            detail="New password must be at least 6 characters"
        )

    if verify_password(
        password_data.new_password,
        current_user.password
    ):
        raise HTTPException(
            status_code=400,
            detail="New password must be different from current password"
        )

    current_user.password = hash_password(
        password_data.new_password
    )

    db.commit()

    return {
        "message": "Password changed successfully"
    }


@app.get("/profile")
def profile(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials

    email = verify_access_token(token)

    return {
        "message": "Access Granted",
        "email": email
    }


@app.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user)
):

    return current_user


@app.get("/admin")
def admin_dashboard(
    current_user: User = Depends(get_current_user)
):

    return {
        "message": "Welcome Admin",
        "user": current_user.full_name
    }


@app.post("/courses", response_model=CourseResponse)
def create_course(
    course: CourseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    new_course = Course(
        title=course.title,
        description=course.description,
        price=course.price,
        category=course.category,
        difficulty=course.difficulty,
        thumbnail=course.thumbnail,
        instructor_id=current_user.user_id
    )

    db.add(new_course)
    db.commit()
    db.refresh(new_course)

    return new_course


@app.get("/courses", response_model=list[CourseResponse])
def get_courses(
    db: Session = Depends(get_db)
):

    return db.query(Course).all()


@app.get("/courses/{course_id}", response_model=CourseResponse)
def get_course(
    course_id: int,
    db: Session = Depends(get_db)
):

    course = db.query(Course).filter(
        Course.course_id == course_id
    ).first()

    if not course:
        raise HTTPException(
            status_code=404,
            detail="Course not found"
        )

    return course

@app.put("/courses/{course_id}", response_model=CourseResponse)
def update_course(
    course_id: int,
    updated_course: CourseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    course = db.query(Course).filter(
        Course.course_id == course_id
    ).first()

    if not course:
        raise HTTPException(
            status_code=404,
            detail="Course not found"
        )

    course.title = updated_course.title
    course.description = updated_course.description
    course.price = updated_course.price
    course.category = updated_course.category
    course.difficulty = updated_course.difficulty
    course.thumbnail = updated_course.thumbnail

    db.commit()
    db.refresh(course)

    return course


@app.delete("/courses/{course_id}")
def delete_course(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    course = db.query(Course).filter(
        Course.course_id == course_id
    ).first()

    if not course:
        raise HTTPException(
            status_code=404,
            detail="Course not found"
        )

    db.delete(course)
    db.commit()

    return {
        "message": "Course deleted successfully"
    }


@app.post("/enroll", response_model=EnrollmentResponse)
def enroll_course(
    enrollment: EnrollmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    course = db.query(Course).filter(
        Course.course_id == enrollment.course_id
    ).first()

    if not course:
        raise HTTPException(
            status_code=404,
            detail="Course not found"
        )

    existing = db.query(Enrollment).filter(
        Enrollment.student_id == current_user.user_id,
        Enrollment.course_id == enrollment.course_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Already enrolled"
        )

    new_enrollment = Enrollment(
        student_id=current_user.user_id,
        course_id=enrollment.course_id
    )

    db.add(new_enrollment)
    db.commit()
    db.refresh(new_enrollment)

    return new_enrollment


@app.get("/my-courses", response_model=list[EnrollmentResponse])
def my_courses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    return db.query(Enrollment).filter(
        Enrollment.student_id == current_user.user_id
    ).all()


@app.put("/progress/{course_id}", response_model=EnrollmentResponse)
def update_progress(
    course_id: int,
    progress: ProgressUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    enrollment = db.query(Enrollment).filter(
        Enrollment.student_id == current_user.user_id,
        Enrollment.course_id == course_id
    ).first()

    if not enrollment:
        raise HTTPException(
            status_code=404,
            detail="Enrollment not found"
        )

    enrollment.progress = progress.progress

    if progress.progress >= 100:
        enrollment.completed = True

    db.commit()
    db.refresh(enrollment)

    return enrollment

@app.post("/videos", response_model=VideoResponse)
def create_video(
    video: VideoCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    course = db.query(Course).filter(
        Course.course_id == video.course_id
    ).first()

    if not course:
        raise HTTPException(
            status_code=404,
            detail="Course not found"
        )

    new_video = CourseVideo(
        course_id=video.course_id,
        title=video.title,
        description=video.description,
        video_url=video.video_url,
        duration=video.duration,
        order_no=video.order_no
    )

    db.add(new_video)
    db.commit()
    db.refresh(new_video)

    return new_video


@app.get("/audios/{course_id}")
def get_audios(
    course_id: int,
    db: Session = Depends(get_db)
):
    audios = db.query(CourseAudio).filter(
        CourseAudio.course_id == course_id
    ).order_by(
        CourseAudio.order_no
    ).all()

    return audios

@app.get("/images/{course_id}")
def get_images(
    course_id: int,
    db: Session = Depends(get_db)
):
    images = db.query(CourseImage).filter(
        CourseImage.course_id == course_id
    ).order_by(
        CourseImage.order_no
    ).all()

    return images


@app.delete("/course-image/{image_id}")
def delete_course_image(
    image_id: int,
    db: Session = Depends(get_db)
):
    image = db.query(CourseImage).filter(
        CourseImage.image_id == image_id
    ).first()

    if not image:
        raise HTTPException(
            status_code=404,
            detail="Image not found."
        )

    db.delete(image)
    db.commit()

    return {
        "message": "Course image deleted successfully."
    }

@app.get("/videos/{course_id}", response_model=list[VideoResponse])
def get_videos(
    course_id: int,
    db: Session = Depends(get_db)
):

    videos = db.query(CourseVideo).filter(
        CourseVideo.course_id == course_id
    ).order_by(
        CourseVideo.order_no
    ).all()

    return videos


@app.put("/videos/{video_id}", response_model=VideoResponse)
def update_video(
    video_id: int,
    video: VideoCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    existing_video = db.query(
        CourseVideo
    ).filter(
        CourseVideo.video_id == video_id
    ).first()

    if not existing_video:
        raise HTTPException(
            status_code=404,
            detail="Video not found"
        )

    existing_video.title = video.title
    existing_video.description = video.description
    existing_video.video_url = video.video_url
    existing_video.duration = video.duration
    existing_video.order_no = video.order_no

    db.commit()
    db.refresh(existing_video)

    return existing_video


@app.delete("/videos/{video_id}")
def delete_video(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # ---------------------------------
    # Find Video
    # ---------------------------------

    video = db.query(
        CourseVideo
    ).filter(
        CourseVideo.video_id == video_id
    ).first()

    if not video:
        raise HTTPException(
            status_code=404,
            detail="Video not found"
        )

    # ---------------------------------
    # Delete Transcript Segments
    # ---------------------------------

    db.query(
        VideoTranscriptSegment
    ).filter(
        VideoTranscriptSegment.video_id == video_id
    ).delete(
        synchronize_session=False
    )

    # ---------------------------------
    # Delete Full Transcript
    # ---------------------------------

    db.query(
        VideoTranscript
    ).filter(
        VideoTranscript.video_id == video_id
    ).delete(
        synchronize_session=False
    )

    # ---------------------------------
    # Delete Video File
    # ---------------------------------

    if video.video_url:

        filename = video.video_url.replace(
            "/uploads/videos/",
            ""
        )

        file_path = os.path.join(
            os.path.dirname(__file__),
            "uploads",
            "videos",
            filename
        )

        if os.path.exists(file_path):
            os.remove(file_path)

    # ---------------------------------
    # Delete Video
    # ---------------------------------

    db.delete(video)
    db.commit()

    return {
        "message": "Video deleted successfully",
        "video_id": video_id
    }
@app.post("/course-chat", response_model=CourseChatResponse)
def course_chat(
    request: CourseChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    course = db.query(Course).filter(
        Course.course_id == request.course_id
    ).first()

    if not course:
        raise HTTPException(
            status_code=404,
            detail="Course not found"
        )

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=request.question
    )

    answer = response.text

    chat = CourseChatHistory(
        user_id=current_user.user_id,
        course_id=request.course_id,
        question=request.question,
        answer=answer
    )

    db.add(chat)
    db.commit()
    db.refresh(chat)

    return chat


@app.post("/upload-course-material")
async def upload_course_material(
    course_id: int = Form(...),
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # ---------------------------------
    # Check Course
    # ---------------------------------

    course = db.query(Course).filter(
        Course.course_id == course_id
    ).first()

    if not course:
        raise HTTPException(
            status_code=404,
            detail="Course not found"
        )

    # ---------------------------------
    # Create Upload Directory
    # ---------------------------------

    os.makedirs(
        UPLOAD_DIR,
        exist_ok=True
    )

    print("=== MULTI PDF UPLOAD DEBUG ===")
    print(f"UPLOAD_DIR: {UPLOAD_DIR}")
    print(
        f"Number of files received: "
        f"{len(files)}"
    )

    uploaded_files = []

    # ---------------------------------
    # Upload Each PDF
    # ---------------------------------

    for file in files:

        if not file.filename:
            continue

        # ---------------------------------
        # Validate PDF
        # ---------------------------------

        extension = os.path.splitext(
            file.filename
        )[1].lower()

        if extension != ".pdf":
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{file.filename} is not a PDF. "
                    "Only PDF files are allowed."
                )
            )

        # ---------------------------------
        # Read File
        # ---------------------------------

        content = await file.read()

        print(
            f"Filename: {file.filename}"
        )

        print(
            f"Content length: "
            f"{len(content)}"
        )

        if len(content) == 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{file.filename} is empty."
                )
            )

        # ---------------------------------
        # Create File Path
        # ---------------------------------

        file_path = os.path.join(
            UPLOAD_DIR,
            file.filename
        )

        print(
            f"File path: {file_path}"
        )

        # ---------------------------------
        # Save File
        # ---------------------------------

        with open(
            file_path,
            "wb"
        ) as buffer:

            buffer.write(content)


        print(
            f"File exists: "
            f"{os.path.exists(file_path)}"
        )

        print(
            f"File size: "
            f"{os.path.getsize(file_path)}"
        )

        # ---------------------------------
        # Save Database Record
        # Store only the filename so the record is not
        # tied to an absolute path on this machine.
        # ---------------------------------

        material = CourseMaterial(
            course_id=course_id,
            file_name=file.filename,
            file_path=file.filename
        )

        db.add(material)

        uploaded_files.append(
            file.filename
        )

    # ---------------------------------
    # Commit All Materials
    # ---------------------------------

    db.commit()

    print(
        f"Uploaded files: "
        f"{uploaded_files}"
    )

    print(
        "=== END MULTI PDF UPLOAD ==="
    )

    return {
        "message": (
            "Files uploaded successfully"
        ),
        "files": uploaded_files
    }
def get_video_duration(file_path):
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                file_path
            ],
            capture_output=True,
            text=True,
            check=True
        )

        data = json.loads(result.stdout)

        duration = float(
            data["format"]["duration"]
        )

        return int(round(duration))

    except Exception as e:
        print("=== FFPROBE DURATION ERROR ===")
        print(str(e))
        print("=== END FFPROBE ERROR ===")

        return None
def process_video_transcription(
    video_id,
    file_path
):
    print("========================================")
    print("=== BACKGROUND TRANSCRIPTION STARTED ===")
    print(f"Video ID: {video_id}")
    print(f"File: {file_path}")
    print("========================================")

    # Create an independent session owned entirely by this
    # background task. The request-scoped session is closed
    # by FastAPI before this task runs, so we must not reuse it.
    from database import SessionLocal
    db = SessionLocal()

    try:
        transcription = transcribe_video(
            file_path
        )

        print("=== TRANSCRIPTION COMPLETED ===")
        print(
            f"Transcript length: "
            f"{len(transcription['text'])}"
        )

        # ---------------------------------
        # Save Full Transcript
        # ---------------------------------

        transcript = VideoTranscript(
            video_id=video_id,
            full_text=transcription["text"]
        )

        db.add(transcript)

        # ---------------------------------
        # Save Timestamped Segments
        # ---------------------------------

        segments = transcription["segments"]

        for segment in segments:

            transcript_segment = VideoTranscriptSegment(
                video_id=video_id,
                start_time=segment["start"],
                end_time=segment["end"],
                text=segment["text"]
            )

            db.add(transcript_segment)

        db.commit()

        print(
            f"Transcript segments saved: "
            f"{len(segments)}"
        )

        print("=== BACKGROUND TRANSCRIPTION COMPLETED ===")

    except Exception as e:

        print("=== BACKGROUND TRANSCRIPTION FAILED ===")
        print(str(e))

        db.rollback()

    finally:
        db.close()
@app.post("/upload-course-video")
async def upload_course_video(
    background_tasks: BackgroundTasks,
    course_id: int = Form(...),
    title: str = Form(...),
    description: str | None = Form(None),
    order_no: int = Form(0),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # ---------------------------------
    # Check Course
    # ---------------------------------

    course = db.query(Course).filter(
        Course.course_id == course_id
    ).first()

    if not course:
        raise HTTPException(
            status_code=404,
            detail="Course not found"
        )

    # ---------------------------------
    # Validate File
    # ---------------------------------

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Video file is required"
        )

    allowed_extensions = (
        ".mp4",
        ".webm",
        ".ogg",
        ".mov"
    )

    extension = os.path.splitext(
        file.filename
    )[1].lower()

    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid video format. "
                "Allowed formats: MP4, WEBM, OGG, MOV"
            )
        )

    # ---------------------------------
    # Create Video Upload Directory
    # ---------------------------------

    video_upload_dir = os.path.join(
        os.path.dirname(__file__),
        "uploads",
        "videos"
    )

    os.makedirs(
        video_upload_dir,
        exist_ok=True
    )

    # ---------------------------------
    # Create Unique File Name
    # ---------------------------------

    unique_name = (
        f"{uuid.uuid4().hex}"
        f"{extension}"
    )

    file_path = os.path.join(
        video_upload_dir,
        unique_name
    )

    # ---------------------------------
    # Save Video File
    # ---------------------------------

    content = await file.read()

    print("=== VIDEO UPLOAD DEBUG ===")
    print(f"Course ID: {course_id}")
    print(f"Original filename: {file.filename}")
    print(f"Saved filename: {unique_name}")
    print(f"Content length: {len(content)}")
    print(f"File path: {file_path}")

    with open(file_path, "wb") as buffer:
        buffer.write(content)

    # ---------------------------------
    # Upload Video to Cloudinary
    # ---------------------------------

    print("=== CLOUDINARY VIDEO UPLOAD ===")

    cloudinary_result = cloudinary.uploader.upload(
        file_path,
        resource_type="video",
        folder="coursera/course_videos"
    )

    video_url = cloudinary_result["secure_url"]

    print(f"Cloudinary URL: {video_url}")
    print("=== END CLOUDINARY VIDEO UPLOAD ===")

    print(
        f"File exists: "
        f"{os.path.exists(file_path)}"
    )

    print("=== END VIDEO UPLOAD DEBUG ===")

    # ---------------------------------
    # Extract Video Duration
    # ---------------------------------

    print("=== VIDEO DURATION DETECTION ===")

    duration = get_video_duration(
        file_path
    )

    if duration is None:
        raise HTTPException(
            status_code=400,
            detail="Unable to determine video duration."
        )

    print(
        f"Detected duration: {duration} seconds"
    )

    print("=== END VIDEO DURATION DETECTION ===")

    

    # ---------------------------------
    # Save Video Database Record
    # ---------------------------------

    new_video = CourseVideo(
        course_id=course_id,
        title=title,
        description=description,
        video_url=video_url,
        duration=duration,
        order_no=order_no
    )

    db.add(new_video)
    db.commit()
    db.refresh(new_video)

    print("=== VIDEO DATABASE RECORD CREATED ===")
    print(f"Video ID: {new_video.video_id}")

    # ---------------------------------
    # Generate Transcript
    # ---------------------------------

        # ---------------------------------
    # Start Background Transcription
    # ---------------------------------

    background_tasks.add_task(
        process_video_transcription,
        new_video.video_id,
        file_path
    )

    print(
        "=== BACKGROUND TRANSCRIPTION QUEUED ==="
    )

    return {
        "message": "Video uploaded successfully",
        "video": new_video,
        "transcription": {
            "status": "processing"
        }
    }

    return {
        "message": "Video uploaded successfully",
        "video": new_video,
        "transcription": {
            "status": "completed"
        }
    }

@app.get("/course-materials/{course_id}", response_model=list[CourseMaterialResponse])
def get_course_materials(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    return db.query(CourseMaterial).filter(
        CourseMaterial.course_id == course_id
    ).all()
@app.delete("/course-material/{material_id}")
def delete_course_material(
    material_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    material = db.query(CourseMaterial).filter(
        CourseMaterial.material_id == material_id
    ).first()

    if not material:
        raise HTTPException(
            status_code=404,
            detail="Course material not found"
        )

    # Delete physical PDF
    file_path = os.path.join(
        UPLOAD_DIR,
        material.file_path
    )

    if os.path.exists(file_path):
        os.remove(file_path)

    # Delete database record
    db.delete(material)
    db.commit()

    return {
        "message": "Course material deleted successfully"
    }



    

@app.post("/generate-vector-db/{course_id}")
def generate_vector_db(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # ---------------------------------
    # Get Course PDFs
    # ---------------------------------

    materials = db.query(CourseMaterial).filter(
        CourseMaterial.course_id == course_id
    ).all()

    # ---------------------------------
    # Get Course Videos
    # ---------------------------------

    videos = db.query(CourseVideo).filter(
        CourseVideo.course_id == course_id
    ).all()

    if not materials and not videos:
        raise HTTPException(
            status_code=404,
            detail="No course materials or videos found"
        )

    all_documents = []

    print("=== GENERATE VECTOR DB DEBUG ===")

    # =================================
    # PROCESS PDF MATERIALS
    # =================================

    print(
        f"Total PDFs in DB for course {course_id}: "
        f"{len(materials)}"
    )

    for material in materials:

        file_path = material.file_path

        # Backward-compatible path resolution:
        # - Old records: file_path is an absolute path → use as-is.
        # - New records: file_path is a filename only → join with UPLOAD_DIR.
        if not os.path.isabs(file_path):

            file_path = os.path.join(
                UPLOAD_DIR,
                file_path
            )

        print(
            f"Processing PDF: {file_path}"
        )

        print(
            f"File exists: "
            f"{os.path.exists(file_path)}"
        )

        pages = extract_pdf_text(
            file_path
        )

        print(
            f"Pages extracted: "
            f"{len(pages)}"
        )

        source_name = os.path.basename(
            file_path
        )

        documents = split_text(
            pages,
            source_name
        )

        print(
            f"PDF documents created: "
            f"{len(documents)}"
        )

        all_documents.extend(
            documents
        )

    # =================================
    # PROCESS VIDEO TRANSCRIPTS
    # =================================

    print(
        f"Total videos in DB for course {course_id}: "
        f"{len(videos)}"
    )

    for video in videos:

        transcript_segments = db.query(
            VideoTranscriptSegment
        ).filter(
            VideoTranscriptSegment.video_id
            == video.video_id
        ).order_by(
            VideoTranscriptSegment.start_time
        ).all()

        print(
            f"\nProcessing video: "
            f"{video.title}"
        )

        print(
            f"Video ID: "
            f"{video.video_id}"
        )

        print(
            f"Transcript segments: "
            f"{len(transcript_segments)}"
        )

        for segment in transcript_segments:

            if not segment.text.strip():
                continue

            document = Document(
                page_content=segment.text,
                metadata={
                    "source": "video",
                    "video_id": video.video_id,
                    "video_title": video.title,
                    "start_time": segment.start_time,
                    "end_time": segment.end_time,
                    "course_id": course_id
                }
            )

            all_documents.append(
                document
            )

    # =================================
    # FINAL DOCUMENT COUNT
    # =================================

    print(
        f"\nTotal documents across PDFs + videos: "
        f"{len(all_documents)}"
    )

    if not all_documents:

        raise HTTPException(
            status_code=400,
            detail="No searchable content found"
        )

    # =================================
    # CREATE FAISS VECTOR STORE
    # =================================

    folder = create_vector_store(
        all_documents,
        course_id
    )

    print(
        f"FAISS index saved to: {folder}"
    )

    print(
        "=== END GENERATE VECTOR DB DEBUG ==="
    )

    return {
        "message": (
            "Vector database created successfully"
        ),
        "total_files": len(materials),
        "total_videos": len(videos),
        "chunks": len(all_documents),
        "location": folder
    }

@app.post("/course-rag-chat")
def course_rag_chat(
    request: CourseChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # ---------------------------------
    # Retrieve Previous Chat History
    # ---------------------------------
    previous_chats = db.query(
        CourseChatHistory
    ).filter(
        CourseChatHistory.user_id == current_user.user_id,
        CourseChatHistory.course_id == request.course_id
    ).order_by(
        CourseChatHistory.created_at.desc()
    ).limit(5).all()

    previous_chats.reverse()

    print("=== CHAT MEMORY DEBUG ===")
    print(
        f"Previous chats found: {len(previous_chats)}"
    )

    for chat in previous_chats:
        print(f"Q: {chat.question}")
        print(f"A: {chat.answer[:300]}")

    print("=== END CHAT MEMORY DEBUG ===")

    # ---------------------------------
    # Build Chat Memory Context
    # ---------------------------------
    memory_parts = []

    for chat in previous_chats:
        memory_parts.append(
            f"""
Previous User Question:
{chat.question}

Previous AI Answer:
{chat.answer}
"""
        )

    chat_memory = "\n\n".join(
        memory_parts
    )

    # ---------------------------------
    # Build Retrieval Query
    # ---------------------------------
    # Use only the current question for FAISS retrieval.
    # Concatenating previous questions pollutes the embedding
    # query and causes irrelevant chunks to rank higher.
    # Chat memory is still passed to Gemini in the prompt
    # so follow-up references ("it", "that", etc.) still work.
    retrieval_query = request.question

    print("=== RETRIEVAL QUERY DEBUG ===")
    print(retrieval_query)
    print("=== END RETRIEVAL QUERY DEBUG ===")

    # ---------------------------------
    # Retrieve RAG Chunks
    # ---------------------------------
    docs = search_chunks(
        request.course_id,
        retrieval_query
    )

    # ---------------------------------
    # Cheap keyword-overlap reranker
    # ---------------------------------
    # No extra API call. Tokenise the question and each chunk,
    # count shared content words, keep the top-N most relevant.
    # Video chunks are only kept when the question is clearly
    # video-related; otherwise they are deprioritised so
    # Gemini does not receive noisy transcript snippets for
    # PDF/concept questions.
    _STOP = {
        "a", "an", "the", "is", "are", "was", "were", "be",
        "been", "being", "have", "has", "had", "do", "does",
        "did", "will", "would", "could", "should", "may",
        "might", "shall", "can", "to", "of", "in", "on",
        "at", "by", "for", "with", "about", "as", "into",
        "through", "and", "or", "but", "if", "so", "yet",
        "what", "how", "why", "when", "where", "which",
        "who", "whom", "this", "that", "these", "those",
        "it", "its", "i", "you", "he", "she", "we", "they",
        "me", "him", "her", "us", "them", "my", "your",
        "his", "our", "their", "not", "no", "from", "up",
        "out", "than", "then", "just", "also", "more",
    }

    _VIDEO_KEYWORDS = {
        "video", "watch", "lecture", "clip", "recording",
        "timestamp", "minute", "second", "spoken", "said",
        "mentioned", "talk", "talks",
        "discussed", "shown", "demonstrate", "demonstrates",
    }

    def _tokens(text):
        return {
            w for w in text.lower().split()
            if w.isalpha() and w not in _STOP
        }

    question_tokens = _tokens(request.question)
    is_video_question = bool(
        question_tokens & _VIDEO_KEYWORDS
    )

    def _score(doc):
        chunk_tokens = _tokens(doc.page_content)
        overlap = len(question_tokens & chunk_tokens)
        is_video_chunk = (
            doc.metadata.get("source") == "video"
        )
        # Penalise video chunks when the question is not
        # video-related so they rank below PDF chunks.
        if is_video_chunk and not is_video_question:
            overlap = overlap * 0.3
        return overlap

    scored = sorted(
        docs,
        key=_score,
        reverse=True
    )

    # Keep at most 5 chunks; always keep at least 1 so
    # Gemini has something to work with even on sparse matches.
    docs = scored[:5] if len(scored) >= 5 else scored

    print("=== RERANKER DEBUG ===")
    for i, doc in enumerate(docs):
        print(
            f"Rank {i+1} | "
            f"source={doc.metadata.get('source')} | "
            f"score={_score(doc):.2f} | "
            f"{doc.page_content[:80]}"
        )
    print("=== END RERANKER DEBUG ===")

    print("=" * 60)
    print("Retrieved Chunks:", len(docs))

    for i, doc in enumerate(docs):
        print(f"\nChunk {i + 1}:")
        print(doc.page_content[:1000])
        print("Metadata:", doc.metadata)

    print("=" * 60)

    # ---------------------------------
    # Get Course Videos
    # ---------------------------------
    videos = db.query(
        CourseVideo
    ).filter(
        CourseVideo.course_id == request.course_id
    ).order_by(
        CourseVideo.order_no
    ).all()

    # ---------------------------------
    # Build Video Metadata Context
    # ---------------------------------
    video_metadata = []

    for video in videos:
        duration_seconds = video.duration or 0
        minutes = duration_seconds // 60
        seconds = duration_seconds % 60

        duration_formatted = (
            f"{minutes}:{seconds:02d}"
        )

        video_metadata.append(
            f"""
Video ID: {video.video_id}
Title: {video.title}
Description: {video.description or "No description"}
Runtime: {duration_formatted}
Runtime in seconds: {duration_seconds}
"""
        )

    video_context = "\n".join(
        video_metadata
    )

    # ---------------------------------
    # Build Retrieved Context
    # ---------------------------------
    context_parts = []

    for doc in docs:
        metadata = doc.metadata

        if metadata.get("source") == "video":
            start_time = metadata.get(
                "start_time",
                0
            )

            end_time = metadata.get(
                "end_time",
                0
            )

            video_title = metadata.get(
                "video_title",
                "Unknown video"
            )

            video_id = metadata.get(
                "video_id",
                "Unknown"
            )

            context_parts.append(
                f"""
[VIDEO TRANSCRIPT]
Video ID: {video_id}
Video Title: {video_title}
Timestamp: {start_time:.2f}s - {end_time:.2f}s

Transcript:
{doc.page_content}
"""
            )

        else:
            context_parts.append(
                f"""
[COURSE MATERIAL]
Source: {metadata.get("source", "Unknown")}
Page: {metadata.get("page", "Unknown")}
Chunk: {metadata.get("chunk", "Unknown")}

Content:
{doc.page_content}
"""
            )

    context = "\n\n".join(
        context_parts
    )

    # ---------------------------------
    # Debug
    # ---------------------------------
    print("=== VIDEO METADATA DEBUG ===")
    print(f"Videos found: {len(videos)}")
    print(video_context)
    print("=== END VIDEO METADATA DEBUG ===")

    print("=== CHAT MEMORY CONTEXT ===")
    print(chat_memory[:2000])
    print("=== END CHAT MEMORY CONTEXT ===")

    print("=== PROMPT DEBUG ===")
    print(
        f"Context length sent to Gemini: {len(context)} chars"
    )
    print(
        f"Context preview: {repr(context[:500])}"
    )
    print("=== END PROMPT DEBUG ===")

    # ---------------------------------
    # Prompt
    # ---------------------------------
    prompt = f"""
You are an AI Tutor for an online course.

You must answer ONLY using the provided course
materials, video transcripts, and video metadata.

There are TWO types of information available:

1. COURSE MATERIAL
   - PDF/document content
   - Page and chunk information

2. VIDEO INFORMATION
   - Video title
   - Description
   - Runtime
   - Timestamped transcript segments

IMPORTANT RULES:

- Use the PREVIOUS CONVERSATION only to understand
  references and follow-up questions such as
  "it", "this", "that", or "the above".

- Factual claims must be supported by the current
  retrieved course material, video transcripts,
  or video metadata.

- Do not treat a previous AI answer as independent
  factual evidence.

- If the question asks about video runtime, title,
  description, or other video metadata, use the
  VIDEO METADATA section.

- If the question asks about the content spoken
  in a video, use the VIDEO TRANSCRIPT sections.

- If the question asks about PDF/course material,
  use the COURSE MATERIAL sections.

- Do not invent information.

- If the answer cannot be found in the provided
  information, reply exactly:

I don't know from the course material.

PREVIOUS CONVERSATION:

{chat_memory}

VIDEO METADATA:

{video_context}

RETRIEVED COURSE CONTENT:

{context}

CURRENT QUESTION:

{request.question}
"""

    # ---------------------------------
    # Generate AI Response
    # ---------------------------------

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt
        )

    except Exception as e:

        error_message = str(e)

        print("=== GEMINI ERROR ===")
        print(error_message)
        print("=== END GEMINI ERROR ===")

        if (
            "429" in error_message
            or "RESOURCE_EXHAUSTED" in error_message
            or "quota" in error_message.lower()
        ):
            raise HTTPException(
                status_code=429,
                detail=(
                    "Gemini API quota exceeded. "
                    "Please try again after the quota resets."
                )
            )

        raise HTTPException(
            status_code=503,
            detail=(
                "AI service is temporarily "
                "unavailable. Please try again."
            )
        )

    # ---------------------------------
    # Save Chat History
    # ---------------------------------
    chat = CourseChatHistory(
        user_id=current_user.user_id,
        course_id=request.course_id,
        question=request.question,
        answer=response.text
    )

    db.add(chat)
    db.commit()
    db.refresh(chat)

    # ---------------------------------
    # Prepare Evidence
    # ---------------------------------
    evidence = []

    for i, doc in enumerate(docs):
        metadata = doc.metadata

        if metadata.get("source") == "video":
            evidence.append({
                "id": i + 1,
                "source": "video",
                "video_id": metadata.get("video_id"),
                "video_title": metadata.get("video_title"),
                "start_time": metadata.get("start_time"),
                "end_time": metadata.get("end_time"),
                "text": doc.page_content[:600]
            })

        else:
            evidence.append({
                "id": i + 1,
                "source": metadata.get(
                    "source",
                    "Unknown source"
                ),
                "page": metadata.get(
                    "page",
                    "Unknown"
                ),
                "chunk": metadata.get(
                    "chunk",
                    "Unknown"
                ),
                "text": doc.page_content[:600]
            })

    # ---------------------------------
    # Final Response
    # ---------------------------------
    return {
        "answer": response.text,
        "chunks_used": len(docs),
        "evidence": evidence
    }


@app.post("/upload-course-audio")
async def upload_course_audio(
    course_id: int = Form(...),
    title: str = Form(...),
    description: str | None = Form(None),
    order_no: int = Form(0),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(
        Course.course_id == course_id
    ).first()

    if not course:
        raise HTTPException(
            status_code=404,
            detail="Course not found"
        )

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Audio file is required"
        )

    allowed_extensions = (
        ".mp3",
        ".wav",
        ".ogg",
        ".m4a",
        ".aac"
    )

    extension = os.path.splitext(
        file.filename
    )[1].lower()

    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid audio format. "
                "Allowed formats: MP3, WAV, OGG, M4A, AAC"
            )
        )

    audio_upload_dir = os.path.join(
        os.path.dirname(__file__),
        "uploads",
        "audio"
    )

    os.makedirs(
        audio_upload_dir,
        exist_ok=True
    )

    unique_name = (
        f"{uuid.uuid4().hex}"
        f"{extension}"
    )

    file_path = os.path.join(
        audio_upload_dir,
        unique_name
    )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Audio file is empty."
        )

    with open(file_path, "wb") as buffer:
        buffer.write(content)

    print("=== CLOUDINARY AUDIO UPLOAD ===")

    cloudinary_result = cloudinary.uploader.upload(
        file_path,
        resource_type="video",
        folder="coursera/course_audios"
    )

    audio_url = cloudinary_result["secure_url"]

    print(f"Cloudinary Audio URL: {audio_url}")
    print("=== END CLOUDINARY AUDIO UPLOAD ===")

    duration = get_video_duration(file_path)

    new_audio = CourseAudio(
        course_id=course_id,
        title=title,
        description=description,
        audio_url=audio_url,
        duration=duration,
        order_no=order_no
    )

    db.add(new_audio)
    db.commit()
    db.refresh(new_audio)

    return {
        "message": "Audio uploaded successfully",
        "audio": new_audio
    }

@app.post("/upload-course-image")
async def upload_course_image(
    course_id: int = Form(...),
    title: str = Form(...),
    description: str | None = Form(None),
    order_no: int = Form(0),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(
        Course.course_id == course_id
    ).first()

    if not course:
        raise HTTPException(
            status_code=404,
            detail="Course not found"
        )

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Image file is required"
        )

    allowed_extensions = (
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif"
    )

    extension = os.path.splitext(
        file.filename
    )[1].lower()

    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid image format. "
                "Allowed formats: JPG, JPEG, PNG, WEBP, GIF"
            )
        )

    image_upload_dir = os.path.join(
        os.path.dirname(__file__),
        "uploads",
        "images"
    )

    os.makedirs(
        image_upload_dir,
        exist_ok=True
    )

    unique_name = (
        f"{uuid.uuid4().hex}"
        f"{extension}"
    )

    file_path = os.path.join(
        image_upload_dir,
        unique_name
    )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Image file is empty."
        )

    with open(file_path, "wb") as buffer:
        buffer.write(content)

    print("=== CLOUDINARY IMAGE UPLOAD ===")

    cloudinary_result = cloudinary.uploader.upload(
        file_path,
        resource_type="image",
        folder="coursera/course_images"
    )

    image_url = cloudinary_result["secure_url"]

    print(f"Cloudinary Image URL: {image_url}")
    print("=== END CLOUDINARY IMAGE UPLOAD ===")

    new_image = CourseImage(
        course_id=course_id,
        title=title,
        description=description,
        image_url=image_url,
        order_no=order_no
    )

    db.add(new_image)
    db.commit()
    db.refresh(new_image)

    return {
        "message": "Image uploaded successfully",
        "image": new_image
    }

@app.post("/transcribe-youtube-video/{video_id}")
def transcribe_youtube_video(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    video = db.query(CourseVideo).filter(
        CourseVideo.video_id == video_id
    ).first()

    if not video:
        raise HTTPException(
            status_code=404,
            detail="Video not found"
        )

    if not video.video_url.startswith(
        ("http://", "https://")
    ):
        raise HTTPException(
            status_code=400,
            detail="This video does not have a YouTube URL"
        )

    temp_dir = os.path.join(
        os.path.dirname(__file__),
        "temp_video"
    )

    os.makedirs(
        temp_dir,
        exist_ok=True
    )

    audio_path = os.path.join(
        temp_dir,
        f"{uuid.uuid4().hex}"
    )

    try:

        print("=" * 60)
        print("=== YOUTUBE TRANSCRIPTION STARTED ===")
        print(f"Video ID: {video_id}")
        print(f"Title: {video.title}")
        print(f"URL: {video.video_url}")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": audio_path + ".%(ext)s",
            "noplaylist": True,
        }

        with yt_dlp.YoutubeDL(
            ydl_opts
        ) as ydl:

            ydl.download(
                [video.video_url]
            )

        downloaded_file = None

        for filename in os.listdir(temp_dir):

            if filename.startswith(
                os.path.basename(audio_path)
            ):
                downloaded_file = os.path.join(
                    temp_dir,
                    filename
                )
                break

        if not downloaded_file:
            raise Exception(
                "Downloaded audio file not found"
            )

        print(
            f"Audio downloaded: {downloaded_file}"
        )

        print("Loading Whisper model...")

        model = whisper.load_model("base")

        print("Transcribing YouTube video...")

        result = model.transcribe(
            downloaded_file,
            fp16=False
        )

        full_text = result.get(
            "text",
            ""
        ).strip()

        segments = result.get(
            "segments",
            []
        )

        print(
            f"Transcript length: {len(full_text)}"
        )

        print(
            f"Segments found: {len(segments)}"
        )

        # Remove old transcript
        db.query(
            VideoTranscriptSegment
        ).filter(
            VideoTranscriptSegment.video_id
            == video_id
        ).delete(
            synchronize_session=False
        )

        db.query(
            VideoTranscript
        ).filter(
            VideoTranscript.video_id
            == video_id
        ).delete(
            synchronize_session=False
        )

        db.commit()

        # Save full transcript
        transcript = VideoTranscript(
            video_id=video_id,
            full_text=full_text
        )

        db.add(transcript)

        # Save timestamp segments
        for segment in segments:

            segment_text = segment.get(
                "text",
                ""
            ).strip()

            if not segment_text:
                continue

            transcript_segment = (
                VideoTranscriptSegment(
                    video_id=video_id,
                    start_time=float(
                        segment["start"]
                    ),
                    end_time=float(
                        segment["end"]
                    ),
                    text=segment_text
                )
            )

            db.add(transcript_segment)

        db.commit()

        print(
            "=== YOUTUBE TRANSCRIPTION COMPLETED ==="
        )

        print(
            f"Video ID: {video_id}"
        )

        print(
            f"Transcript segments saved: "
            f"{len(segments)}"
        )

        print("=" * 60)

        return {
            "message": (
                "YouTube video transcribed successfully"
            ),
            "video_id": video_id,
            "title": video.title,
            "transcript_length": len(full_text),
            "segments": len(segments)
        }

    except Exception as e:

        db.rollback()

        print(
            "=== YOUTUBE TRANSCRIPTION ERROR ==="
        )

        print(str(e))

        raise HTTPException(
            status_code=500,
            detail=(
                f"YouTube transcription failed: {str(e)}"
            )
        )

    finally:

        if os.path.exists(temp_dir):

            for filename in os.listdir(temp_dir):

                file_path = os.path.join(
                    temp_dir,
                    filename
                )

                try:
                    os.remove(file_path)
                except Exception:
                    pass