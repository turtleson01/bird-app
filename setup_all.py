import os
import time
import requests
import pandas as pd
import urllib.request
from PIL import Image
from rembg import remove  # ⭐️ 배경 제거 마법

CSV_FILE = "data.csv"
OUTPUT_FOLDER = "assets/sprites"

def process_bird(bird_id, bird_name):
    # 1. 위키백과에서 사진 찾기
    url = "https://ko.wikipedia.org/w/api.php"
    headers = {"User-Agent": "BirdApp/2.0"}
    params = {"action": "query", "format": "json", "prop": "pageimages", "titles": bird_name, "pithumbsize": 1000}

    try:
        res = requests.get(url, params=params, headers=headers, timeout=5).json()
        pages = res.get("query", {}).get("pages", {})
        img_url = next((info["thumbnail"]["source"] for pid, info in pages.items() if "thumbnail" in info), None)

        if not img_url: return False

        # 2. 임시 다운로드
        temp_img = f"temp_{bird_id}.jpg"
        req = urllib.request.Request(img_url, headers=headers)
        with urllib.request.urlopen(req) as r, open(temp_img, 'wb') as f:
            f.write(r.read())

        # 3. ⭐️ 배경 제거 AI 적용
        with open(temp_img, 'rb') as i:
            input_data = i.read()
            output_data = remove(input_data) # 배경이 날아가고 새만 남음!

        import io
        img = Image.open(io.BytesIO(output_data)).convert("RGBA")

        # 4. ⭐️ 크기 축소 & 색감 단순화 (16색 레트로 감성)
        w, h = img.size
        target = 48
        small_w, small_h = target, int(target * (h / w))
        
        # 작게 줄이기
        pixel_img = img.resize((small_w, small_h), Image.NEAREST)
        
        # 색을 16개로 제한하여 고전 게임 느낌 내기
        pixel_img = pixel_img.quantize(colors=16, method=2)
        pixel_img = pixel_img.convert("RGBA") # 투명도 유지

        # 5. 보기 좋게 4배 확대 후 저장
        final_img = pixel_img.resize((small_w * 4, small_h * 4), Image.NEAREST)
        final_img.save(os.path.join(OUTPUT_FOLDER, f"{bird_id}.png"), "PNG")

        os.remove(temp_img)
        print(f"✨ [고품질] No.{bird_id} {bird_name} 레트로 도트 생성!")
        return True

    except Exception: return False

def main():
    if not os.path.exists(OUTPUT_FOLDER): os.makedirs(OUTPUT_FOLDER)
    df = pd.read_csv(CSV_FILE, skiprows=2, header=None, encoding='cp949')
    print("🚀 [배경투명+16색] 고품질 도트 재생성을 시작합니다...")
    success = 0
    for _, row in df.iloc[:, [0, 4]].dropna().iterrows():
        if process_bird(int(row[0]), str(row[4]).strip()): success += 1
        time.sleep(0.1)
    print(f"🎉 완벽합니다! 총 {success}개의 고품질 도트 이미지가 완성되었습니다.")

if __name__ == "__main__":
    main()