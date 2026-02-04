from fastapi import FastAPI, Request, HTTPException, Depends, Response, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pathlib import Path
from dotenv import load_dotenv
import os
import jwt
from ftplib import FTP
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import Optional, Dict, List
import io
import subprocess
import tempfile
import shutil
import mysql.connector
import threading
import uuid

# 환경변수 로드
load_dotenv()

# ==================== 백그라운드 작업 관리 ====================
class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, dict] = {}
        self.lock = threading.Lock()

    def create_task(self, task_type: str, description: str) -> str:
        task_id = str(uuid.uuid4())[:8]
        with self.lock:
            self.tasks[task_id] = {
                "id": task_id,
                "type": task_type,
                "description": description,
                "status": "running",
                "progress": 0,
                "total": 0,
                "current_item": "",
                "started_at": datetime.now().isoformat(),
                "finished_at": None,
                "logs": []
            }
        return task_id

    def update_task(self, task_id: str, **kwargs):
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id].update(kwargs)

    def add_log(self, task_id: str, message: str):
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id]["logs"].append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "message": message
                })
                # 최대 100개 로그만 유지
                if len(self.tasks[task_id]["logs"]) > 100:
                    self.tasks[task_id]["logs"] = self.tasks[task_id]["logs"][-100:]

    def finish_task(self, task_id: str, status: str = "completed"):
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id]["status"] = status
                self.tasks[task_id]["finished_at"] = datetime.now().isoformat()

    def get_task(self, task_id: str) -> Optional[dict]:
        with self.lock:
            return self.tasks.get(task_id)

    def get_all_tasks(self) -> List[dict]:
        with self.lock:
            # 최근 작업 20개만 반환 (최신순)
            tasks = list(self.tasks.values())
            tasks.sort(key=lambda x: x["started_at"], reverse=True)
            return tasks[:20]

    def get_running_tasks(self) -> List[dict]:
        with self.lock:
            return [t for t in self.tasks.values() if t["status"] == "running"]

    def cleanup_old_tasks(self):
        """오래된 완료 작업 정리 (1시간 이상)"""
        with self.lock:
            now = datetime.now()
            to_delete = []
            for task_id, task in self.tasks.items():
                if task["status"] != "running" and task["finished_at"]:
                    finished = datetime.fromisoformat(task["finished_at"])
                    if (now - finished).total_seconds() > 3600:
                        to_delete.append(task_id)
            for task_id in to_delete:
                del self.tasks[task_id]

task_manager = TaskManager()

app = FastAPI(
    title="SSIRN - 지기술(G-TECH)",
    description="지기술 공식 웹사이트 API",
    version="2.0.0"
)

# 설정
BASE_DIR = Path(__file__).resolve().parent
SECRET_KEY = os.getenv("ROOT_PASSWORD", "secret")
FTP_HOST = os.getenv("FTP_HOST")
FTP_PORT = int(os.getenv("FTP_PORT", 21))
FTP_USER = os.getenv("FTP_USER")
FTP_PASSWORD = os.getenv("FTP_PASSWORD")
ROOT_USER = os.getenv("ROOT_USER")
ROOT_PASSWORD = os.getenv("ROOT_PASSWORD")

# DB 설정
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "ssirn")

# 정적 파일 마운트
app.mount("/css", StaticFiles(directory=BASE_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=BASE_DIR / "js"), name="js")
app.mount("/images", StaticFiles(directory=BASE_DIR / "images"), name="images")
app.mount("/video", StaticFiles(directory=BASE_DIR / "video"), name="video")


# ==================== 모델 ====================
class LoginRequest(BaseModel):
    username: str
    password: str


class GalleryItem(BaseModel):
    url: str
    description: Optional[str] = ""
    type: str = "image"


# ==================== 인증 ====================
def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def verify_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except:
        return None


async def get_current_user(request: Request) -> str:
    token = request.cookies.get("auth_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    username = verify_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")

    return username


# ==================== 페이지 라우트 ====================
@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
async def home():
    return FileResponse(BASE_DIR / "index.html")


@app.get("/vision", response_class=HTMLResponse)
@app.get("/vision.html", response_class=HTMLResponse)
async def vision():
    return FileResponse(BASE_DIR / "vision.html")


@app.get("/technology", response_class=HTMLResponse)
@app.get("/technology.html", response_class=HTMLResponse)
async def technology():
    return FileResponse(BASE_DIR / "technology.html")


@app.get("/products", response_class=HTMLResponse)
@app.get("/products.html", response_class=HTMLResponse)
async def products():
    return FileResponse(BASE_DIR / "products.html")


@app.get("/gallery", response_class=HTMLResponse)
@app.get("/gallery.html", response_class=HTMLResponse)
async def gallery():
    return FileResponse(BASE_DIR / "gallery.html")


@app.get("/contact", response_class=HTMLResponse)
@app.get("/contact.html", response_class=HTMLResponse)
async def contact():
    return FileResponse(BASE_DIR / "contact.html")


@app.get("/timelapse", response_class=HTMLResponse)
@app.get("/timelapse.html", response_class=HTMLResponse)
async def timelapse():
    return FileResponse(BASE_DIR / "timelapse.html")


@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin.html", response_class=HTMLResponse)
async def admin():
    return FileResponse(BASE_DIR / "admin.html")


@app.get("/dashboard", response_class=HTMLResponse)
@app.get("/dashboard.html", response_class=HTMLResponse)
async def dashboard():
    return FileResponse(BASE_DIR / "dashboard.html")


# ==================== 인증 API ====================
@app.post("/api/login")
async def login(request: LoginRequest, response: Response):
    if request.username == ROOT_USER and request.password == ROOT_PASSWORD:
        token = create_token(request.username)
        response.set_cookie(
            key="auth_token",
            value=token,
            httponly=True,
            max_age=86400,
            samesite="lax"
        )
        return {"success": True, "token": token}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.post("/api/logout")
async def logout(response: Response):
    response.delete_cookie("auth_token")
    return {"success": True}


@app.get("/api/auth/check")
async def check_auth(request: Request):
    token = request.cookies.get("auth_token")
    if token and verify_token(token):
        return {"authenticated": True}
    return {"authenticated": False}


# ==================== FTP API ====================
# 카메라별 FTP 경로
CAMERAS = {
    "feed": {"path": "/homes/ha/camFTP/feed", "name": "메인 카메라"},
    "west": {"path": "/homes/ha/camFTP/west", "name": "서쪽 카메라"},
    "roof": {"path": "/homes/ha/camFTP/roof", "name": "지붕 카메라"},
    "conner": {"path": "/homes/ha/camFTP/conner", "name": "코너 카메라"},
}
FTP_BASE_PATH = "/homes/ha/camFTP/feed"  # 기본값 (하위호환)


def get_ftp_connection():
    """FTP 연결 생성"""
    ftp = FTP()
    ftp.connect(FTP_HOST, FTP_PORT)
    ftp.login(FTP_USER, FTP_PASSWORD)
    return ftp


@app.get("/api/cameras")
async def get_cameras():
    """사용 가능한 카메라 목록"""
    return {
        "success": True,
        "cameras": [{"id": k, "name": v["name"]} for k, v in CAMERAS.items()]
    }


@app.get("/api/feed/dates")
async def get_feed_dates(camera: str = "feed"):
    """사용 가능한 날짜 폴더 목록"""
    try:
        cam_path = CAMERAS.get(camera, CAMERAS["feed"])["path"]
        ftp = get_ftp_connection()
        ftp.cwd(cam_path)
        folders = sorted([f for f in ftp.nlst() if f.isdigit() and len(f) == 8], reverse=True)
        ftp.quit()
        return {"success": True, "dates": folders, "camera": camera}
    except Exception as e:
        return {"success": False, "error": str(e), "dates": []}


@app.get("/api/feed/list")
async def get_feed_list(date: str = None, camera: str = "feed"):
    """FTP feed 폴더의 이미지 목록 가져오기"""
    try:
        cam_path = CAMERAS.get(camera, CAMERAS["feed"])["path"]
        ftp = get_ftp_connection()
        ftp.cwd(cam_path)

        # 날짜가 없으면 가장 최근 폴더 사용
        if not date:
            folders = sorted([f for f in ftp.nlst() if f.isdigit() and len(f) == 8], reverse=True)
            if not folders:
                ftp.quit()
                return {"success": False, "error": "No date folders found", "files": [], "count": 0}
            date = folders[0]

        # images 폴더로 이동
        ftp.cwd(f"{cam_path}/{date}/images")

        # 이미지 파일 목록
        all_files = ftp.nlst()
        files = []
        for name in all_files:
            if name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                files.append({
                    "name": name,
                    "date": date,
                    "camera": camera,
                    "path": f"{date}/images/{name}"
                })

        # 파일명 기준 정렬 (시간순)
        files.sort(key=lambda x: x["name"])
        ftp.quit()

        return {"success": True, "files": files, "count": len(files), "date": date, "camera": camera}
    except Exception as e:
        return {"success": False, "error": str(e), "files": [], "count": 0}


@app.get("/api/feed/image/{camera}/{date}/{filename}")
async def get_feed_image_with_camera(camera: str, date: str, filename: str):
    """FTP에서 이미지 프록시 (카메라 지정)"""
    try:
        cam_path = CAMERAS.get(camera, CAMERAS["feed"])["path"]
        ftp = get_ftp_connection()

        # 이미지 다운로드
        data = io.BytesIO()
        ftp.retrbinary(f"RETR {cam_path}/{date}/images/{filename}", data.write)
        ftp.quit()

        data.seek(0)

        # Content-Type 결정
        ext = filename.lower().split('.')[-1]
        content_types = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'webp': 'image/webp'
        }
        content_type = content_types.get(ext, 'image/jpeg')

        return StreamingResponse(
            data,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=3600"}
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Image not found: {str(e)}")


@app.get("/api/feed/image/{date}/{filename}")
async def get_feed_image(date: str, filename: str):
    """FTP에서 이미지 프록시 (하위호환 - feed 카메라)"""
    return await get_feed_image_with_camera("feed", date, filename)


# ==================== 동영상 API ====================
TEMP_DIR = Path("/tmp/ssirn_timelapse")


def get_video_path(camera: str = "feed") -> str:
    """카메라별 비디오 경로"""
    cam_path = CAMERAS.get(camera, CAMERAS["feed"])["path"]
    return f"{cam_path}/videos"


def ensure_video_folder(camera: str = "feed"):
    """FTP에 videos 폴더가 있는지 확인하고 없으면 생성"""
    try:
        video_path = get_video_path(camera)
        ftp = get_ftp_connection()
        try:
            ftp.cwd(video_path)
        except:
            ftp.mkd(video_path)
        ftp.quit()
    except:
        pass


@app.get("/api/feed/videos")
async def get_video_list(camera: str = "feed"):
    """변환된 동영상 목록 (파일 크기 포함)"""
    try:
        video_path = get_video_path(camera)
        ftp = get_ftp_connection()
        try:
            ftp.cwd(video_path)
            # 파일 목록과 크기 가져오기
            video_info = []
            files = []
            ftp.retrlines('LIST', files.append)

            for line in files:
                parts = line.split()
                if len(parts) >= 9:
                    size = int(parts[4])  # 파일 크기 (bytes)
                    name = parts[8]  # 파일명
                    if name.endswith('.mp4'):
                        date = name.replace('.mp4', '')
                        # 720p 동영상은 보통 5MB 이하 (분당 약 1MB)
                        # 원본 1080p 이상은 보통 10MB 이상
                        is_720p = size < 8 * 1024 * 1024  # 8MB 기준
                        video_info.append({
                            "date": date,
                            "size": size,
                            "size_mb": round(size / (1024 * 1024), 2),
                            "is_720p": is_720p
                        })

            ftp.quit()
            video_info.sort(key=lambda x: x["date"], reverse=True)

            # 모든 동영상이 720p인지 체크
            all_720p = all(v["is_720p"] for v in video_info) if video_info else True

            return {
                "success": True,
                "videos": [v["date"] for v in video_info],  # 기존 호환
                "video_info": video_info,  # 상세 정보
                "all_720p": all_720p,
                "camera": camera
            }
        except:
            ftp.quit()
            return {"success": True, "videos": [], "video_info": [], "all_720p": True, "camera": camera}
    except Exception as e:
        return {"success": False, "error": str(e), "videos": [], "video_info": [], "all_720p": True}


@app.get("/api/feed/video/{camera}/{date}")
async def get_video_with_camera(camera: str, date: str):
    """FTP에서 동영상 스트리밍 (카메라 지정)"""
    try:
        video_path = get_video_path(camera)
        ftp = get_ftp_connection()
        data = io.BytesIO()
        ftp.retrbinary(f"RETR {video_path}/{date}.mp4", data.write)
        ftp.quit()

        data.seek(0)
        file_size = len(data.getvalue())

        return StreamingResponse(
            data,
            media_type="video/mp4",
            headers={
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
                "Cache-Control": "public, max-age=86400"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Video not found: {str(e)}")


@app.get("/api/feed/video/{date}")
async def get_video(date: str):
    """FTP에서 동영상 스트리밍 (하위호환 - feed 카메라)"""
    return await get_video_with_camera("feed", date)


def convert_images_to_video(date: str, camera: str = "feed", delete_originals: bool = True):
    """이미지를 동영상으로 변환 (백그라운드 작업) - 720p로 리사이즈"""
    work_dir = None
    try:
        cam_path = CAMERAS.get(camera, CAMERAS["feed"])["path"]
        video_path = get_video_path(camera)

        # 임시 디렉토리 생성
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        work_dir = TEMP_DIR / f"{camera}_{date}"
        work_dir.mkdir(exist_ok=True)

        # FTP에서 이미지 다운로드
        ftp = get_ftp_connection()
        ftp.cwd(f"{cam_path}/{date}/images")
        files = sorted([f for f in ftp.nlst() if f.lower().endswith(('.jpg', '.jpeg', '.png'))])

        if not files:
            ftp.quit()
            return

        # 이미지 다운로드
        for i, filename in enumerate(files):
            local_path = work_dir / f"img_{i:05d}.jpg"
            with open(local_path, 'wb') as f:
                ftp.retrbinary(f"RETR {filename}", f.write)

        ftp.quit()

        # ffmpeg로 동영상 생성 (10fps, 720p 리사이즈)
        output_path = work_dir / f"{date}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-framerate", "10",
            "-i", str(work_dir / "img_%05d.jpg"),
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            "-crf", "26",
            str(output_path)
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        # FTP에 업로드
        ensure_video_folder(camera)
        ftp = get_ftp_connection()
        ftp.cwd(video_path)
        with open(output_path, 'rb') as f:
            ftp.storbinary(f"STOR {date}.mp4", f)
        ftp.quit()

        # 원본 이미지 삭제
        if delete_originals:
            delete_original_images(camera, date)

        # 임시 파일 정리
        shutil.rmtree(work_dir, ignore_errors=True)
        print(f"Converted {camera}/{date} to 720p video")

    except Exception as e:
        print(f"Video conversion error for {camera}/{date}: {e}")
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)


def resize_existing_video(camera: str, date: str):
    """기존 동영상을 720p로 리사이즈"""
    work_dir = None
    try:
        video_path = get_video_path(camera)

        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        work_dir = TEMP_DIR / f"resize_{camera}_{date}"
        work_dir.mkdir(exist_ok=True)

        # FTP에서 동영상 다운로드
        ftp = get_ftp_connection()
        ftp.cwd(video_path)

        input_path = work_dir / f"original_{date}.mp4"
        output_path = work_dir / f"{date}.mp4"

        with open(input_path, 'wb') as f:
            ftp.retrbinary(f"RETR {date}.mp4", f.write)
        ftp.quit()

        # 현재 파일 크기 확인
        original_size = input_path.stat().st_size

        # ffmpeg로 720p 리사이즈
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            "-crf", "26",
            str(output_path)
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        new_size = output_path.stat().st_size

        # 새 파일이 더 작으면 업로드
        if new_size < original_size:
            ftp = get_ftp_connection()
            ftp.cwd(video_path)
            with open(output_path, 'rb') as f:
                ftp.storbinary(f"STOR {date}.mp4", f)
            ftp.quit()
            print(f"Resized {camera}/{date}: {original_size//1024}KB -> {new_size//1024}KB")
        else:
            print(f"Skipped {camera}/{date}: already optimized")

        shutil.rmtree(work_dir, ignore_errors=True)

    except Exception as e:
        print(f"Resize error for {camera}/{date}: {e}")
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)


def resize_all_videos_task(camera: str, task_id: str = None):
    """카메라의 모든 동영상 리사이즈 태스크"""
    try:
        video_path = get_video_path(camera)
        ftp = get_ftp_connection()
        ftp.cwd(video_path)
        files = [f.replace('.mp4', '') for f in ftp.nlst() if f.endswith('.mp4')]
        ftp.quit()

        total = len(files)
        if task_id:
            task_manager.update_task(task_id, total=total)
            task_manager.add_log(task_id, f"총 {total}개 동영상 리사이즈 시작")

        for i, date in enumerate(files):
            if task_id:
                task_manager.update_task(task_id, progress=i+1, current_item=f"{date}.mp4")
                task_manager.add_log(task_id, f"리사이즈 중: {date}")
            resize_existing_video(camera, date)

        if task_id:
            task_manager.add_log(task_id, f"완료: {total}개 동영상 리사이즈")
            task_manager.finish_task(task_id, "completed")
        print(f"Completed resizing all videos for {camera}")
    except Exception as e:
        if task_id:
            task_manager.add_log(task_id, f"오류: {e}")
            task_manager.finish_task(task_id, "failed")
        print(f"Error resizing videos for {camera}: {e}")


@app.post("/api/feed/convert/{camera}/{date}")
async def convert_to_video_with_camera(camera: str, date: str, background_tasks: BackgroundTasks, request: Request):
    """이미지를 동영상으로 변환 (관리자 전용, 카메라 지정)"""
    # 인증 확인
    token = request.cookies.get("auth_token")
    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")

    if camera not in CAMERAS:
        raise HTTPException(status_code=400, detail=f"Invalid camera: {camera}")

    # 백그라운드에서 변환 작업 실행 (변환 후 원본 삭제)
    background_tasks.add_task(convert_images_to_video, date, camera, True)
    return {"success": True, "message": f"Converting {camera}/{date} to 720p video (originals will be deleted)"}


@app.post("/api/feed/resize-all/{camera}")
async def resize_all_videos(camera: str, background_tasks: BackgroundTasks, request: Request):
    """기존 동영상 일괄 720p 리사이즈 (관리자 전용)"""
    token = request.cookies.get("auth_token")
    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")

    if camera not in CAMERAS:
        raise HTTPException(status_code=400, detail=f"Invalid camera: {camera}")

    # 작업 생성
    task_id = task_manager.create_task("resize", f"{camera} 동영상 일괄 리사이즈")

    background_tasks.add_task(resize_all_videos_task, camera, task_id)
    return {"success": True, "message": f"Resizing all videos for {camera} in background", "task_id": task_id}


@app.post("/api/feed/convert/{date}")
async def convert_to_video(date: str, background_tasks: BackgroundTasks, request: Request):
    """이미지를 동영상으로 변환 (하위호환 - feed 카메라)"""
    return await convert_to_video_with_camera("feed", date, background_tasks, request)


@app.get("/api/feed/status/{camera}/{date}")
async def get_conversion_status_with_camera(camera: str, date: str):
    """동영상 변환 상태 확인 (카메라 지정)"""
    try:
        video_path = get_video_path(camera)
        ftp = get_ftp_connection()
        ftp.cwd(video_path)
        files = ftp.nlst()
        ftp.quit()

        exists = f"{date}.mp4" in files
        return {"success": True, "date": date, "camera": camera, "hasVideo": exists}
    except:
        return {"success": True, "date": date, "camera": camera, "hasVideo": False}


@app.get("/api/feed/status/{date}")
async def get_conversion_status(date: str):
    """동영상 변환 상태 확인 (하위호환 - feed 카메라)"""
    return await get_conversion_status_with_camera("feed", date)


# ==================== 대시보드 API ====================
def get_db_connection():
    """DB 연결"""
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )


@app.get("/api/dashboard/stats")
async def get_dashboard_stats(from_date: str = None, to_date: str = None):
    """대시보드 통계"""
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # 날짜 조건
        date_condition = ""
        det_date_condition = ""
        params = []
        if from_date and to_date:
            date_condition = "WHERE stat_date BETWEEN %s AND %s"
            det_date_condition = "WHERE image_date BETWEEN %s AND %s"
            params = [from_date, to_date]
        elif from_date:
            date_condition = "WHERE stat_date >= %s"
            det_date_condition = "WHERE image_date >= %s"
            params = [from_date]

        # 총계
        cursor.execute(f"""
            SELECT
                COALESCE(SUM(total_detections), 0) as total,
                COALESCE(SUM(cat_count), 0) as cats,
                COALESCE(SUM(dog_count), 0) as dogs,
                COALESCE(SUM(person_count), 0) as persons,
                COALESCE(SUM(car_count), 0) as cars,
                COALESCE(SUM(other_count), 0) as others
            FROM daily_stats {date_condition}
        """, params)
        totals = cursor.fetchone()

        # 시간대별 합계
        hourly = []
        for h in range(24):
            cursor.execute(f"""
                SELECT COALESCE(SUM(hour_{h}), 0) as cnt
                FROM daily_stats {date_condition}
            """, params)
            result = cursor.fetchone()
            hourly.append(result['cnt'] if result else 0)

        # 고유 고양이 수
        cursor.execute(f"""
            SELECT COUNT(DISTINCT cat_id) as cnt
            FROM detections
            WHERE cat_id IS NOT NULL
            {('AND image_date BETWEEN %s AND %s' if from_date and to_date else '')}
        """, params if from_date and to_date else [])
        unique_cats = cursor.fetchone()

        cursor.close()
        db.close()

        return {
            "success": True,
            "total": totals['total'] if totals else 0,
            "cats": totals['cats'] if totals else 0,
            "dogs": totals['dogs'] if totals else 0,
            "persons": totals['persons'] if totals else 0,
            "cars": totals['cars'] if totals else 0,
            "others": totals['others'] if totals else 0,
            "uniqueCats": unique_cats['cnt'] if unique_cats else 0,
            "hourly": hourly
        }
    except Exception as e:
        return {"success": False, "error": str(e), "total": 0, "cats": 0, "dogs": 0, "persons": 0, "cars": 0, "others": 0, "hourly": [0]*24}


@app.get("/api/dashboard/detections")
async def get_detections(from_date: str = None, to_date: str = None, limit: int = 50):
    """탐지 기록 조회"""
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        params = []
        where_clause = "WHERE 1=1"
        if from_date and to_date:
            where_clause += " AND image_date BETWEEN %s AND %s"
            params.extend([from_date, to_date])

        cursor.execute(f"""
            SELECT
                image_name as image,
                DATE_FORMAT(image_date, '%%Y%%m%%d') as date,
                TIME_FORMAT(image_time, '%%H:%%i:%%s') as time,
                object_class as class,
                confidence,
                is_cat,
                cat_id
            FROM detections
            {where_clause}
            ORDER BY image_date DESC, image_time DESC
            LIMIT %s
        """, params + [limit])

        detections = cursor.fetchall()

        cursor.close()
        db.close()

        return {"success": True, "detections": detections}
    except Exception as e:
        return {"success": False, "error": str(e), "detections": []}


@app.get("/api/dashboard/cats")
async def get_cat_profiles(from_date: str = None, to_date: str = None):
    """고양이 개체별 프로필"""
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        params = []
        where_clause = "WHERE is_cat = TRUE AND cat_id IS NOT NULL"
        if from_date and to_date:
            where_clause += " AND image_date BETWEEN %s AND %s"
            params.extend([from_date, to_date])

        cursor.execute(f"""
            SELECT
                cat_id as id,
                cat_id as name,
                COUNT(*) as count,
                MIN(image_name) as first_image,
                DATE_FORMAT(MIN(image_date), '%%Y%%m%%d') as first_date
            FROM detections
            {where_clause}
            GROUP BY cat_id
            ORDER BY count DESC
        """, params)

        cats = cursor.fetchall()

        # 썸네일 URL 추가
        for cat in cats:
            if cat['first_image'] and cat['first_date']:
                cat['thumbnail'] = f"/api/feed/image/{cat['first_date']}/{cat['first_image']}"

        cursor.close()
        db.close()

        return {"success": True, "cats": cats}
    except Exception as e:
        return {"success": False, "error": str(e), "cats": []}


@app.post("/api/analyze/{date}")
async def analyze_date(date: str, background_tasks: BackgroundTasks, request: Request):
    """특정 날짜 이미지 분석 (관리자 전용)"""
    # 인증 확인
    token = request.cookies.get("auth_token")
    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")

    # 백그라운드에서 분석 실행
    import subprocess
    background_tasks.add_task(
        subprocess.run,
        ["python3", str(BASE_DIR / "analyzer.py"), date],
        capture_output=True
    )

    return {"success": True, "message": f"Analyzing {date} in background"}


# ==================== 타임랩스 설정 API ====================
# 설정 파일 경로
SETTINGS_FILE = BASE_DIR / "settings.json"


def load_settings():
    """설정 파일 로드"""
    try:
        if SETTINGS_FILE.exists():
            import json
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {"public_cameras": ["feed", "west", "roof"], "gallery_items": []}


def save_settings(settings):
    """설정 파일 저장"""
    import json
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)


@app.get("/api/settings")
async def get_settings():
    """설정 조회"""
    settings = load_settings()
    return {"success": True, "settings": settings}


@app.post("/api/settings")
async def update_settings(request: Request):
    """설정 업데이트 (관리자 전용)"""
    token = request.cookies.get("auth_token")
    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")

    data = await request.json()
    settings = load_settings()
    settings.update(data)
    save_settings(settings)
    return {"success": True}


@app.get("/api/timelapse/cameras")
async def get_timelapse_cameras():
    """공개 타임랩스 카메라 목록"""
    settings = load_settings()
    public_cameras = settings.get("public_cameras", ["feed", "west", "roof"])[:3]
    result = []
    for cam_id in public_cameras:
        if cam_id in CAMERAS:
            result.append({"id": cam_id, "name": CAMERAS[cam_id]["name"]})
    return {"success": True, "cameras": result}


# ==================== 갤러리 API ====================
@app.get("/api/gallery")
async def get_gallery():
    """갤러리 목록 조회"""
    settings = load_settings()
    items = settings.get("gallery_items", [])
    return {"success": True, "items": items}


@app.post("/api/gallery")
async def add_gallery_item(request: Request):
    """갤러리 항목 추가 (관리자)"""
    token = request.cookies.get("auth_token")
    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")

    data = await request.json()
    settings = load_settings()
    items = settings.get("gallery_items", [])

    import time
    new_item = {
        "id": int(time.time() * 1000),
        "url": data.get("url", ""),
        "description": data.get("description", ""),
        "type": "video" if "youtube.com" in data.get("url", "") or "youtu.be" in data.get("url", "") else "image",
        "createdAt": datetime.now().isoformat()
    }
    items.insert(0, new_item)
    settings["gallery_items"] = items
    save_settings(settings)
    return {"success": True, "item": new_item}


@app.put("/api/gallery/{item_id}")
async def update_gallery_item(item_id: int, request: Request):
    """갤러리 항목 수정 (관리자)"""
    token = request.cookies.get("auth_token")
    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")

    data = await request.json()
    settings = load_settings()
    items = settings.get("gallery_items", [])

    for item in items:
        if item.get("id") == item_id:
            item["url"] = data.get("url", item["url"])
            item["description"] = data.get("description", item["description"])
            item["type"] = "video" if "youtube.com" in item["url"] or "youtu.be" in item["url"] else "image"
            break

    settings["gallery_items"] = items
    save_settings(settings)
    return {"success": True}


@app.delete("/api/gallery/{item_id}")
async def delete_gallery_item(item_id: int, request: Request):
    """갤러리 항목 삭제 (관리자)"""
    token = request.cookies.get("auth_token")
    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")

    settings = load_settings()
    items = settings.get("gallery_items", [])
    items = [i for i in items if i.get("id") != item_id]
    settings["gallery_items"] = items
    save_settings(settings)
    return {"success": True}


@app.get("/api/feed/pending-dates/{camera}")
async def get_pending_dates(camera: str):
    """동영상 변환이 필요한 날짜 목록 (이미지 있고 동영상 없는 날짜)"""
    try:
        if camera not in CAMERAS:
            return {"success": False, "error": "Invalid camera", "pending": [], "completed": []}

        cam_path = CAMERAS[camera]["path"]
        video_path = get_video_path(camera)

        ftp = get_ftp_connection()

        # 1. 모든 날짜 폴더 (이미지 있는 날짜)
        ftp.cwd(cam_path)
        all_dates = sorted([f for f in ftp.nlst() if f.isdigit() and len(f) == 8], reverse=True)

        # 2. 동영상 있는 날짜
        video_dates = []
        try:
            ftp.cwd(video_path)
            files = ftp.nlst()
            video_dates = [f.replace('.mp4', '') for f in files if f.endswith('.mp4')]
        except:
            pass

        ftp.quit()

        # 3. 분류
        pending = [d for d in all_dates if d not in video_dates]
        completed = [d for d in all_dates if d in video_dates]

        return {
            "success": True,
            "pending": pending,
            "completed": completed,
            "camera": camera
        }
    except Exception as e:
        return {"success": False, "error": str(e), "pending": [], "completed": []}


@app.post("/api/feed/convert-range/{camera}")
async def convert_date_range(camera: str, request: Request, background_tasks: BackgroundTasks):
    """날짜 범위 동영상 변환 및 원본 삭제 (관리자 전용)"""
    token = request.cookies.get("auth_token")
    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")

    if camera not in CAMERAS:
        raise HTTPException(status_code=400, detail=f"Invalid camera: {camera}")

    data = await request.json()
    from_date = data.get("from_date")
    to_date = data.get("to_date")
    delete_images = data.get("delete_images", False)

    if not from_date or not to_date:
        raise HTTPException(status_code=400, detail="from_date and to_date required")

    # 작업 생성
    task_id = task_manager.create_task("convert", f"{camera} 동영상 변환 ({from_date}~{to_date})")

    # 백그라운드에서 변환 작업 실행
    background_tasks.add_task(convert_date_range_task, camera, from_date, to_date, delete_images, task_id)
    return {"success": True, "message": f"Converting {camera} from {from_date} to {to_date}", "task_id": task_id}


def convert_date_range_task(camera: str, from_date: str, to_date: str, delete_images: bool, task_id: str = None):
    """날짜 범위 변환 태스크"""
    from datetime import datetime as dt, timedelta

    start = dt.strptime(from_date, "%Y%m%d")
    end = dt.strptime(to_date, "%Y%m%d")

    # 총 날짜 수 계산
    total_days = (end - start).days + 1
    if task_id:
        task_manager.update_task(task_id, total=total_days)
        task_manager.add_log(task_id, f"총 {total_days}일 변환 시작")

    current = start
    progress = 0
    while current <= end:
        date_str = current.strftime("%Y%m%d")
        progress += 1
        try:
            if task_id:
                task_manager.update_task(task_id, progress=progress, current_item=date_str)
                task_manager.add_log(task_id, f"변환 중: {date_str}")

            convert_images_to_video(date_str, camera)
            if delete_images:
                delete_original_images(camera, date_str)

            if task_id:
                task_manager.add_log(task_id, f"완료: {date_str}")
        except Exception as e:
            if task_id:
                task_manager.add_log(task_id, f"오류 ({date_str}): {e}")
            print(f"Error converting {camera}/{date_str}: {e}")
        current += timedelta(days=1)

    if task_id:
        task_manager.add_log(task_id, f"모든 변환 완료")
        task_manager.finish_task(task_id, "completed")


def delete_original_images(camera: str, date: str):
    """원본 이미지 삭제"""
    try:
        cam_path = CAMERAS.get(camera, CAMERAS["feed"])["path"]
        video_path = get_video_path(camera)

        # 동영상이 존재하는지 확인
        ftp = get_ftp_connection()
        try:
            ftp.cwd(video_path)
            files = ftp.nlst()
            if f"{date}.mp4" not in files:
                ftp.quit()
                return  # 동영상 없으면 삭제 안함
        except:
            ftp.quit()
            return

        # 이미지 삭제
        ftp.cwd(f"{cam_path}/{date}/images")
        images = [f for f in ftp.nlst() if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        for img in images:
            try:
                ftp.delete(img)
            except:
                pass
        ftp.quit()
        print(f"Deleted {len(images)} images from {camera}/{date}")
    except Exception as e:
        print(f"Error deleting images from {camera}/{date}: {e}")


# ==================== 작업 상태 API ====================
@app.get("/api/tasks")
async def get_tasks():
    """실행 중인 작업 목록"""
    task_manager.cleanup_old_tasks()
    return {
        "success": True,
        "running": task_manager.get_running_tasks(),
        "recent": task_manager.get_all_tasks()
    }


@app.get("/api/tasks/{task_id}")
async def get_task_detail(task_id: str):
    """특정 작업 상세 정보"""
    task = task_manager.get_task(task_id)
    if task:
        return {"success": True, "task": task}
    return {"success": False, "error": "Task not found"}


@app.get("/api/system/status")
async def get_system_status():
    """시스템 상태 (CPU, RAM, 디스크, 서비스)"""
    try:
        # CPU 사용량
        cpu_result = subprocess.run(
            ["top", "-bn1"],
            capture_output=True, text=True, timeout=5
        )
        cpu_line = [l for l in cpu_result.stdout.split('\n') if 'Cpu' in l or '%Cpu' in l]
        cpu_usage = 0
        if cpu_line:
            # "%Cpu(s):  1.2 us,  0.3 sy, ..." 형태 파싱
            parts = cpu_line[0].split(',')
            for p in parts:
                if 'id' in p:  # idle
                    idle = float(p.split()[0])
                    cpu_usage = round(100 - idle, 1)
                    break

        # 메모리 사용량
        mem_result = subprocess.run(
            ["free", "-m"],
            capture_output=True, text=True, timeout=5
        )
        mem_lines = mem_result.stdout.strip().split('\n')
        mem_total, mem_used, mem_free = 0, 0, 0
        for line in mem_lines:
            if line.startswith('Mem:'):
                parts = line.split()
                mem_total = int(parts[1])
                mem_used = int(parts[2])
                mem_free = int(parts[3])
                break
        mem_percent = round((mem_used / mem_total) * 100, 1) if mem_total > 0 else 0

        # 디스크 사용량
        disk_result = subprocess.run(
            ["df", "-h", "/"],
            capture_output=True, text=True, timeout=5
        )
        disk_lines = disk_result.stdout.strip().split('\n')
        disk_total, disk_used, disk_free, disk_percent = "0", "0", "0", 0
        if len(disk_lines) > 1:
            parts = disk_lines[1].split()
            disk_total = parts[1]
            disk_used = parts[2]
            disk_free = parts[3]
            disk_percent = int(parts[4].replace('%', ''))

        # 실행 중인 서비스 (웹앱/서버)
        services = []
        ps_result = subprocess.run(
            ["ps", "aux"],
            capture_output=True, text=True, timeout=5
        )
        for line in ps_result.stdout.split('\n'):
            line_lower = line.lower()
            # uvicorn, gunicorn, nginx, node, python 웹서버 등
            if any(s in line_lower for s in ['uvicorn', 'gunicorn', 'nginx', 'node ', 'flask', 'django', 'fastapi']):
                parts = line.split()
                if len(parts) >= 11:
                    services.append({
                        "pid": parts[1],
                        "cpu": parts[2],
                        "mem": parts[3],
                        "cmd": ' '.join(parts[10:])[:60]
                    })

        return {
            "success": True,
            "cpu": {"usage": cpu_usage},
            "memory": {
                "total_mb": mem_total,
                "used_mb": mem_used,
                "free_mb": mem_free,
                "percent": mem_percent
            },
            "disk": {
                "total": disk_total,
                "used": disk_used,
                "free": disk_free,
                "percent": disk_percent
            },
            "services": services[:10]  # 최대 10개
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==================== 기본 API ====================
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "ssirn"}


@app.get("/api/info")
async def get_info():
    return {
        "name": "지기술(G-TECH)",
        "version": "1.10.0",
        "website": "https://ssirn.co.kr"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
