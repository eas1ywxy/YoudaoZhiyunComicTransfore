import uuid
import requests
import base64
import hashlib
import re
from flask import Flask, request, render_template, jsonify
from PIL import Image, ImageDraw, ImageFont
import io

app = Flask(__name__)

YOUDAO_URL = 'https://openapi.youdao.com/ocrtransapi'
APP_KEY = 'APP_KEY'       # 有道应用ID
APP_SECRET = 'APP_SECRET' # 有道应用密钥

def encrypt(signStr):
    m = hashlib.md5()
    m.update(signStr.encode('utf-8'))
    return m.hexdigest()

def call_youdao_api(image_base64):
    data = {
        'from': 'auto',
        'to': 'zh-CHS',
        'type': '1',
        'q': image_base64,
        'appKey': APP_KEY,
        'salt': str(uuid.uuid1())
    }
    signStr = APP_KEY + image_base64 + data['salt'] + APP_SECRET
    data['sign'] = encrypt(signStr)
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(YOUDAO_URL, data=data, headers=headers)
    return response.json()

def clean_text(text):
    return re.sub(r"[^\u4e00-\u9fff]", "", text)

def draw_translation(image_data, api_result):
    image = Image.open(io.BytesIO(image_data)).convert("RGB")
    draw = ImageDraw.Draw(image)

    try:
        base_font = ImageFont.truetype("static/simhei.ttf", 40)
    except:
        base_font = ImageFont.load_default()

    resRegions = api_result.get("resRegions", [])

    for region in resRegions:
        bbox = region.get("boundingBox", "")
        text = region.get("tranContent", "")
        translated_text = re.sub(r"[^\u4e00-\u9fff]", "", text)
        if not bbox or not translated_text:
            continue

        x, y, w, h = [int(v) for v in bbox.split(",")]
        draw.rectangle([(x, y), (x + w, y + h)], fill="white")

        # 横排文字自动换行
        is_vertical = h > w * 2
        if is_vertical:
            font_size = max(min(h // max(1, len(translated_text)), w - 2), 16)
            try:
                font = ImageFont.truetype("static/simhei.ttf", font_size)
            except:
                font = base_font

            offset_y = y
            draw_x = x + (w - font_size) // 2
            for ch in translated_text:
                draw.text((draw_x, offset_y), ch, fill="black", font=font)
                offset_y += font_size
        else:
            font_size = max(min(h, w // max(1, len(translated_text))), 16)
            try:
                font = ImageFont.truetype("static/simhei.ttf", font_size)
            except:
                font = base_font

            # 自动换行逻辑
            lines = []
            line = ""
            for ch in translated_text:
                # 使用 getbbox 计算文字宽度
                bbox_ch = font.getbbox(line + ch)
                line_width = bbox_ch[2] - bbox_ch[0]
                if line_width > w:
                    if line:
                        lines.append(line)
                    line = ch
                else:
                    line += ch
            if line:
                lines.append(line)

            # 垂直居中
            line_height = font.getbbox("口")[3]  # 字高
            total_text_height = line_height * len(lines)
            offset_y = y + (h - total_text_height) // 2
            for ln in lines:
                bbox_ln = font.getbbox(ln)
                text_w = bbox_ln[2] - bbox_ln[0]
                offset_x = x + (w - text_w) // 2
                draw.text((offset_x, offset_y), ln, fill="black", font=font)
                offset_y += line_height

    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file:
        return jsonify({"error": "没有文件"}), 400

    image_data = file.read()
    image_base64 = base64.b64encode(image_data).decode("utf-8")
    api_result = call_youdao_api(image_base64)
    translated_image_b64 = draw_translation(image_data, api_result)
    return jsonify({
        "file_name": file.filename,
        "translated_image": translated_image_b64
    })

if __name__ == '__main__':
    app.run(debug=True)
