import os
import time
import requests
import pandas as pd
import urllib.request
from PIL import Image

CSV_FILE = "data.csv"
OUTPUT_FOLDER = "assets/sprites" # 최종 도트 이미지가 들어갈 폴더

def process_bird(bird_id, bird_name):
    # 1. 위키백과에서 사진 찾기
    url = "https://ko.wikipedia.org/w/api.php"
    headers = {"User-Agent": "BirdApp/1.0"}
    params = {"action": "query", "format": "json", "prop": "pageimages", "titles": bird_name, "pithumbsize": 1000}

    try:
        res = requests.get(url, params=params, headers=headers, timeout=5).json()
        pages = res.get("query", {}).get("pages", {})
        img_url = next((info["thumbnail"]["source"] for pid, info in pages.items() if "thumbnail" in info), None)

        if not img_url: return False # 사진 없음 통과

        # 2. 임시 다운로드
        temp_img = f"temp_{bird_id}.jpg"
        req = urllib.request.Request(img_url, headers=headers)
        with urllib.request.urlopen(req) as r, open(temp_img, 'wb') as f:
            f.write(r.read())

        # 3. 도트 이미지(Pixel Art)로 변환하여 저장
        img = Image.open(temp_img).convert('RGBA')
        w, h = img.size
        # 48px 기준으로 비율 맞춰 축소 후 4배 확대
        target = 48
        small_w, small_h = target, int(target * (h / w))
        pixel_img = img.resize((small_w, small_h), Image.NEAREST).resize((small_w * 4, small_h * 4), Image.NEAREST)
        pixel_img.save(os.path.join(OUTPUT_FOLDER, f"{bird_id}.png"), "PNG")

        # 4. 임시 파일 삭제 (깔끔하게!)
        os.remove(temp_img)
        print(f"✅ [완료] No.{bird_id} {bird_name} 도트 이미지 생성")
        return True

    except Exception: return False

def main():
    if not os.path.exists(OUTPUT_FOLDER): os.makedirs(OUTPUT_FOLDER)
    df = pd.read_csv(CSV_FILE, skiprows=2, header=None, encoding='cp949')
    print("🚀 사진 다운로드 + 도트 변환을 동시에 시작합니다! (초고속)")
    success = 0
    for _, row in df.iloc[:, [0, 4]].dropna().iterrows():
        if process_bird(int(row[0]), str(row[4]).strip()): success += 1
        time.sleep(0.1) # 초고속 진행
    print(f"🎉 복구 완료! 총 {success}개의 도트 이미지가 assets/sprites 에 생성되었습니다.")

if __name__ == "__main__":
    main()