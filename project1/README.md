# AI物体検出 Webアプリ

YOLOv8を使用したリアルタイム物体検出Webアプリケーションです。

## 特徴

- 🤖 最新のYOLOv8による高精度物体検出
- 🎨 モダンで直感的なUI/UX
- 📱 レスポンシブデザイン
- 🚀 ドラッグ&ドロップによるファイルアップロード
- 📊 信頼度スコア付きの検出結果表示

## セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. アプリケーションの起動

```bash
python app.py
```

### 3. ブラウザでアクセス

http://localhost:5000 にアクセスしてください。

## 使用方法

1. Webブラウザでアプリケーションにアクセス
2. 「画像を選択」ボタンをクリックするか、ドラッグ&ドロップで画像をアップロード
3. 「物体検出を実行」ボタンをクリック
4. AI が画像を分析し、検出された物体をハイライト表示

## サポートファイル形式

- PNG (.png)
- JPEG (.jpg, .jpeg)

## ディレクトリ構成

```
project1/
├── app.py              # メインアプリケーション
├── requirements.txt    # 依存関係
├── templates/
│   └── index.html     # フロントエンドテンプレート
├── static/            # 静的ファイル用（CSS/JS）
└── uploads/          # アップロード画像保存用
```

## 技術スタック

- **Backend**: Python 3.8+, Flaskv
- **AI Model**: YOLOv8 (Ultralytics)
- **Frontend**: HTML5, CSS3, JavaScript
- **Image Processing**: OpenCV, Pillow

## 注意事項

- 最大アップロードサイズ: 16MB