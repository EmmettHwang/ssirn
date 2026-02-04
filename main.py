from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pathlib import Path

app = FastAPI(
    title="SSIRN - 지기술(G-TECH)",
    description="지기술 공식 웹사이트 API",
    version="1.8.0"
)

# 정적 파일 경로
BASE_DIR = Path(__file__).resolve().parent

# 정적 파일 마운트 (CSS, JS, 이미지, 비디오)
app.mount("/css", StaticFiles(directory=BASE_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=BASE_DIR / "js"), name="js")
app.mount("/images", StaticFiles(directory=BASE_DIR / "images"), name="images")
app.mount("/video", StaticFiles(directory=BASE_DIR / "video"), name="video")


@app.get("/", response_class=HTMLResponse)
async def home():
    """홈페이지"""
    return FileResponse(BASE_DIR / "index.html")


@app.get("/vision", response_class=HTMLResponse)
@app.get("/vision.html", response_class=HTMLResponse)
async def vision():
    """비전 페이지"""
    return FileResponse(BASE_DIR / "vision.html")


@app.get("/technology", response_class=HTMLResponse)
@app.get("/technology.html", response_class=HTMLResponse)
async def technology():
    """SSIRN 기술 페이지"""
    return FileResponse(BASE_DIR / "technology.html")


@app.get("/products", response_class=HTMLResponse)
@app.get("/products.html", response_class=HTMLResponse)
async def products():
    """제품 페이지"""
    return FileResponse(BASE_DIR / "products.html")


@app.get("/gallery", response_class=HTMLResponse)
@app.get("/gallery.html", response_class=HTMLResponse)
async def gallery():
    """연구 갤러리 페이지"""
    return FileResponse(BASE_DIR / "gallery.html")


@app.get("/contact", response_class=HTMLResponse)
@app.get("/contact.html", response_class=HTMLResponse)
async def contact():
    """문의 페이지"""
    return FileResponse(BASE_DIR / "contact.html")


# API 엔드포인트 (확장용)
@app.get("/api/health")
async def health_check():
    """헬스 체크"""
    return {"status": "healthy", "service": "ssirn"}


@app.get("/api/info")
async def get_info():
    """서비스 정보"""
    return {
        "name": "지기술(G-TECH)",
        "version": "1.0.0",
        "website": "https://ssirn.co.kr"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
