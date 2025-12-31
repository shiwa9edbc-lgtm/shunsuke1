import os
import cv2
import numpy as np
from flask import Flask, request, render_template, send_from_directory, jsonify
from werkzeug.utils import secure_filename
from ultralytics import YOLO
import uuid
from PIL import Image

app = Flask(__name__)

# 設定
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 最大ファイルサイズ16MB

# アップロードディレクトリが存在しない場合は作成
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# YOLOモデルをロード（初回実行時は自動的にダウンロード）
model = YOLO('yolov8n.pt')  # 速度重視でnanoバージョンを使用

# 物体クラスの日本語翻訳辞書
class_translation = {
    'person': '人',
    'bicycle': '自転車',
    'car': '車',
    'motorcycle': 'バイク',
    'airplane': '飛行機',
    'bus': 'バス',
    'train': '電車',
    'truck': 'トラック',
    'boat': 'ボート',
    'traffic light': '信号機',
    'fire hydrant': '消火栓',
    'stop sign': '停止標識',
    'parking meter': 'パーキングメーター',
    'bench': 'ベンチ',
    'bird': '鳥',
    'cat': '猫',
    'dog': '犬',
    'horse': '馬',
    'sheep': '羊',
    'cow': '牛',
    'elephant': '象',
    'bear': '熊',
    'zebra': 'シマウマ',
    'giraffe': 'キリン',
    'backpack': 'リュックサック',
    'umbrella': '傘',
    'handbag': 'ハンドバッグ',
    'tie': 'ネクタイ',
    'suitcase': 'スーツケース',
    'frisbee': 'フリスビー',
    'skis': 'スキー',
    'snowboard': 'スノーボード',
    'sports ball': 'スポーツボール',
    'kite': '凧',
    'baseball bat': '野球バット',
    'baseball glove': '野球グローブ',
    'skateboard': 'スケートボード',
    'surfboard': 'サーフボード',
    'tennis racket': 'テニスラケット',
    'bottle': 'ボトル',
    'wine glass': 'ワイングラス',
    'cup': 'カップ',
    'fork': 'フォーク',
    'knife': 'ナイフ',
    'spoon': 'スプーン',
    'bowl': 'ボウル',
    'banana': 'バナナ',
    'apple': 'りんご',
    'sandwich': 'サンドイッチ',
    'orange': 'オレンジ',
    'broccoli': 'ブロッコリー',
    'carrot': 'にんじん',
    'hot dog': 'ホットドッグ',
    'pizza': 'ピザ',
    'donut': 'ドーナツ',
    'cake': 'ケーキ',
    'chair': '椅子',
    'couch': 'ソファ',
    'potted plant': '鉢植え',
    'bed': 'ベッド',
    'dining table': 'ダイニングテーブル',
    'toilet': 'トイレ',
    'tv': 'テレビ',
    'laptop': 'ノートパソコン',
    'mouse': 'マウス',
    'remote': 'リモコン',
    'keyboard': 'キーボード',
    'cell phone': '携帯電話',
    'microwave': '電子レンジ',
    'oven': 'オーブン',
    'toaster': 'トースター',
    'sink': 'シンク',
    'refrigerator': '冷蔵庫',
    'book': '本',
    'clock': '時計',
    'vase': '花瓶',
    'scissors': 'はさみ',
    'teddy bear': 'テディベア',
    'hair drier': 'ヘアドライヤー',
    'toothbrush': '歯ブラシ'
}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def detect_objects(image_path, output_path):
    """
    Perform object detection on an image and save the result
    """
    try:
        # 推論を実行
        results = model(image_path)
        
        # 最初の結果を取得（1枚の画像を処理しているため）
        result = results[0]
        
        # バウンディングボックスとラベルを画像に描画
        annotated_image = result.plot()
        
        # 注釈付き画像を保存
        cv2.imwrite(output_path, annotated_image)
        
        # 検出情報を抽出
        detections = []
        if result.boxes is not None:
            for box in result.boxes:
                # バウンディングボックスの座標を取得
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                # 信頼度スコアを取得
                confidence = box.conf[0].cpu().numpy()
                # クラスIDと名前を取得
                class_id = int(box.cls[0].cpu().numpy())
                class_name = model.names[class_id]
                # 利用可能な場合は日本語に翻訳
                japanese_name = class_translation.get(class_name, class_name)
                
                detections.append({
                    'class': japanese_name,
                    'confidence': float(confidence),
                    'bbox': [float(x1), float(y1), float(x2), float(y2)]
                })
        
        return detections, True
    except Exception as e:
        print(f"Error in object detection: {str(e)}")
        return [], False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        # 一意なファイル名を生成
        filename = secure_filename(file.filename)
        unique_id = str(uuid.uuid4())
        file_extension = filename.rsplit('.', 1)[1].lower()
        input_filename = f"{unique_id}_input.{file_extension}"
        output_filename = f"{unique_id}_output.{file_extension}"
        
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        
        # アップロードされたファイルを保存
        file.save(input_path)
        
        # 物体検出を実行
        detections, success = detect_objects(input_path, output_path)
        
        if success:
            return jsonify({
                'success': True,
                'output_image': output_filename,
                'detections': detections,
                'detection_count': len(detections)
            })
        else:
            return jsonify({'error': 'Object detection failed'}), 500
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    print("Starting Flask app...")
    print("YOLO model loading...")
    app.run(debug=False, host='0.0.0.0', port=5000)