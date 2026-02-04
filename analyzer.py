#!/usr/bin/env python3
"""
SSIRN 이미지 분석기 - YOLO 객체 탐지 + 고양이 개체 구별
"""
import os
import sys
import io
import re
import mysql.connector
from ftplib import FTP
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv('/usr/ssirn/.env')

# FTP 설정
FTP_HOST = os.getenv('FTP_HOST')
FTP_PORT = int(os.getenv('FTP_PORT', 21))
FTP_USER = os.getenv('FTP_USER')
FTP_PASSWORD = os.getenv('FTP_PASSWORD')
FTP_BASE_PATH = "/homes/ha/camFTP/feed"

# DB 설정
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME', 'ssirn')
}

# YOLO 모델 (나중에 로드)
model = None
cat_embeddings = {}  # 고양이 개체별 특징 벡터 저장


def get_ftp():
    """FTP 연결"""
    ftp = FTP()
    ftp.connect(FTP_HOST, FTP_PORT)
    ftp.login(FTP_USER, FTP_PASSWORD)
    return ftp


def get_db():
    """DB 연결"""
    return mysql.connector.connect(**DB_CONFIG)


def load_model():
    """YOLO 모델 로드"""
    global model
    if model is None:
        from ultralytics import YOLO
        model = YOLO('yolov8n.pt')  # nano 모델 (빠름)
    return model


def parse_filename(filename):
    """파일명에서 날짜/시간 추출
    예: A26020400333410.jpg -> 2026-02-04 00:33:34
    """
    match = re.match(r'[A-Z](\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})', filename)
    if match:
        y, m, d, h, mi, s = match.groups()
        year = 2000 + int(y)
        return {
            'date': f"{year}-{m}-{d}",
            'time': f"{h}:{mi}:{s}",
            'hour': int(h)
        }
    return None


def analyze_image(image_data, filename, max_size=416):
    """이미지 분석 - 객체 탐지"""
    import numpy as np
    from PIL import Image

    # 이미지 로드
    img = Image.open(io.BytesIO(image_data))

    # 이미지 리사이즈 (메모리 절약)
    if max(img.size) > max_size:
        ratio = max_size / max(img.size)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    # YOLO 탐지 (신뢰도 임계값 낮춤 - 작은 객체도 감지)
    model = load_model()
    results = model(img, verbose=False, conf=0.15)

    detections = []
    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            cls_name = model.names[cls_id]
            conf = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            # 관심 객체: 고양이, 개, 사람, 자동차 (COCO: cat=15, dog=16, person=0, car=2)
            is_cat = cls_name == 'cat'
            is_dog = cls_name == 'dog'
            is_person = cls_name == 'person'
            is_car = cls_name == 'car'

            # 관심 객체만 저장
            if is_cat or is_dog or is_person or is_car:
                detections.append({
                    'class': cls_name,
                    'confidence': conf,
                    'bbox': (x1, y1, x2-x1, y2-y1),
                    'is_cat': is_cat,
                    'is_dog': is_dog,
                    'is_person': is_person,
                    'is_car': is_car,
                    'cat_id': None  # 나중에 개체 구별로 채움
                })

    return detections


def identify_cat(image_data, bbox, existing_cats):
    """고양이 개체 구별 (간단한 특징 비교)
    나중에 더 정교한 re-id 모델로 대체 가능
    """
    # TODO: 고양이 개체 구별 로직
    # 현재는 새로운 고양이로 처리
    cat_id = f"CAT_{len(existing_cats) + 1:03d}"
    return cat_id


def save_detection(db, image_name, date_info, detection):
    """탐지 결과 DB 저장"""
    cursor = db.cursor()

    sql = """
    INSERT INTO detections
    (image_name, image_date, image_time, object_class, confidence,
     bbox_x, bbox_y, bbox_w, bbox_h, is_cat, cat_id)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    bbox = detection['bbox']
    cursor.execute(sql, (
        image_name,
        date_info['date'],
        date_info['time'],
        detection['class'],
        detection['confidence'],
        bbox[0], bbox[1], bbox[2], bbox[3],
        detection['is_cat'],
        detection['cat_id']
    ))

    db.commit()
    cursor.close()


def update_daily_stats(db, date_str, hour, detection):
    """일일 통계 업데이트"""
    cursor = db.cursor()

    # UPSERT 방식
    hour_col = f"hour_{hour}"

    is_cat = detection.get('is_cat', False)
    is_dog = detection.get('is_dog', False)
    is_person = detection.get('is_person', False)
    is_car = detection.get('is_car', False)

    cat_inc = 1 if is_cat else 0
    dog_inc = 1 if is_dog else 0
    person_inc = 1 if is_person else 0
    car_inc = 1 if is_car else 0
    other_inc = 1 if not (is_cat or is_dog or is_person or is_car) else 0

    sql = f"""
    INSERT INTO daily_stats (stat_date, total_detections, cat_count, dog_count, person_count, car_count, other_count, {hour_col})
    VALUES (%s, 1, %s, %s, %s, %s, %s, 1)
    ON DUPLICATE KEY UPDATE
        total_detections = total_detections + 1,
        cat_count = cat_count + %s,
        dog_count = dog_count + %s,
        person_count = person_count + %s,
        car_count = car_count + %s,
        other_count = other_count + %s,
        {hour_col} = {hour_col} + 1
    """

    cursor.execute(sql, (date_str, cat_inc, dog_inc, person_inc, car_inc, other_inc, cat_inc, dog_inc, person_inc, car_inc, other_inc))
    db.commit()
    cursor.close()


def analyze_date(date_str, limit=None):
    """특정 날짜의 이미지 분석"""
    print(f"\n=== Analyzing {date_str} ===")

    db = get_db()

    # FTP에서 파일 목록 가져오기
    ftp = get_ftp()
    ftp.cwd(f"{FTP_BASE_PATH}/{date_str}/images")
    files = sorted([f for f in ftp.nlst() if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
    ftp.quit()

    if limit:
        files = files[:limit]

    print(f"Found {len(files)} images")

    analyzed = 0
    total_cats = 0
    total_others = 0

    for i, filename in enumerate(files):
        # 각 이미지마다 새로운 FTP 연결 (안정성 향상)
        try:
            ftp = get_ftp()
            ftp.cwd(f"{FTP_BASE_PATH}/{date_str}/images")
            data = io.BytesIO()
            ftp.retrbinary(f"RETR {filename}", data.write)
            ftp.quit()
            data.seek(0)
        except Exception as e:
            print(f"  FTP error for {filename}: {e}")
            continue

        # 파일명에서 날짜/시간 파싱
        date_info = parse_filename(filename)
        if not date_info:
            continue

        # 분석
        try:
            detections = analyze_image(data.getvalue(), filename)

            for det in detections:
                # DB 저장
                save_detection(db, filename, date_info, det)

                # 통계 업데이트
                update_daily_stats(db, date_info['date'], date_info['hour'], det)

                if det['is_cat']:
                    total_cats += 1
                elif det.get('is_dog'):
                    total_others += 1  # 개 카운트 (간단히)
                elif det.get('is_person'):
                    total_others += 1  # 사람 카운트 (간단히)
                else:
                    total_others += 1

            analyzed += 1

            if (i + 1) % 10 == 0:
                print(f"  Processed {i + 1}/{len(files)} images...")

        except Exception as e:
            print(f"  Error analyzing {filename}: {e}")

    db.close()

    print(f"\nCompleted: {analyzed} images analyzed")
    print(f"  Cats: {total_cats}, Others: {total_others}")

    return {'analyzed': analyzed, 'cats': total_cats, 'others': total_others}


def main():
    """메인 함수"""
    if len(sys.argv) < 2:
        print("Usage: python analyzer.py <date> [limit]")
        print("  date: YYYYMMDD format (e.g., 20260204)")
        print("  limit: optional, max images to analyze")
        sys.exit(1)

    date_str = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None

    analyze_date(date_str, limit)


if __name__ == "__main__":
    main()
