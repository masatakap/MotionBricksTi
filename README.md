# MotionBricks Studio Ti

**Windows向けソース版 / Windows source release**

NVIDIAのMotionBricksをベースに、モーション編集をはじめとした便利な機能を追加した拡張ツールです。Kimodoで生成したモーションの取り込み、MikuMikuDance向けのモデル読込（PMX／PMD）・モーション出力（VMD）に対応しています。

An enhanced tool based on NVIDIA MotionBricks, with convenient features for motion editing and production. It supports importing motion generated with Kimodo, loading PMX/PMD target models, and exporting VMD motion for MikuMikuDance.

### 紹介映像 / Promotional video

https://github.com/user-attachments/assets/b97f51d8-d9ea-477f-b890-81d7a7587abb

[日本語](#日本語) · [English](#english)

---

## 日本語

### はじめての方へ

MotionBricks Studio Ti本体を先行公開しています。Unreal Engine連携プラグインの配布先は、Fabの審査完了後に掲載します。

**初回に開くファイルは「Setup Studio.cmd」、次回以降の起動は「Launch MotionBricks Studio Ti.cmd」です。** どちらも、取得したフォルダー内の同じ場所にあります。

### どんなアプリ？

モーション素材の読み込みと配置、ボーンによるポーズ編集、タイムラインでの再生・シーク、音との同期、モーションの書き出しを行います。

Studioの表示言語は日本語、英語、スペイン語、フランス語、中国語（簡体字）から選べます。

### 必要な環境

- Windows x64のPC
- 対応するNVIDIA GPUとドライバー。開発環境ではRTX 4070 Tiで起動・モーション生成を確認しています。
- インターネット接続と、アプリ・依存ライブラリ・モデル・生成データを保存する空き容量。初回の公式ONNXモデル取得は約1.14 GBで、その他の保存領域も必要です。
- Git for Windows、Git LFS、uv。Python 3.12はセットアップで使用し、必要に応じてuvが取得します。

導入ツールは各公式ページから入手してください。 [Git for Windows](https://gitforwindows.org/) · [Git LFS](https://git-lfs.com/) · [uvのインストール案内](https://docs.astral.sh/uv/getting-started/installation/)

### 初回導入

1. 上記のGit、Git LFS、uvを導入します。
2. エクスプローラーで、アプリを保存したい書き込み可能なローカルフォルダーを開きます。
3. エクスプローラー上部のアドレスバーに `powershell` と入力してEnterを押します。
4. 開いた画面へ、次の2行を1行ずつ貼り付け、それぞれEnterを押します。Gitはアプリ一式を取得するために使い、取得したものは `MotionBricksTi` フォルダーへ保存されます。

```powershell
git lfs install
git clone https://github.com/masatakap/MotionBricksTi.git
```

5. エクスプローラーで、取得したフォルダーを次の順に開きます。

```text
MotionBricksTi
  └ outputs
      └ motionbricks-studio
```

6. **「Setup Studio.cmd」をダブルクリック**します。環境の確認、必要なライブラリやモデルの取得が進みます。
7. **「Setup complete」**と表示されたらセットアップ完了です。「何かキーを押してください」の表示では、キーを押してセットアップ画面を閉じます。
8. 同じフォルダーの **「Launch MotionBricks Studio Ti.cmd」をダブルクリック**します。初回はGPU用エンジンを構築するため、進捗画面を開いたまま待ちます。

セットアップには、上記のGitによる取得手順を使ってください。GitHubの「Download ZIP」から取得したフォルダーは、現行セットアップの対象に含まれません。

### 2回目以降の起動

上記の `motionbricks-studio` フォルダーにある **「Launch MotionBricks Studio Ti.cmd」** をダブルクリックします。デスクトップへショートカットを作成すると、次回から探しやすくなります。

### 途中で止まったら

`Setup Studio.cmd` は5段階で確認します。停止した段階に表示される対処方法を確認してから、同じファイルを再実行してください。

| 表示 | 確認すること |
| --- | --- |
| `[1/5]` | Git・Git LFS・uv、Python、フォルダーの書き込み権限 |
| `[2/5]` | 依存ライブラリの導入、通信、空き容量 |
| `[3/5]` | NVIDIA GPUとドライバー、TensorRTの初期化 |
| `[4/5]` | Git LFS素材と公式モデルの取得・照合 |
| `[5/5]` | 配布するモーション素材の確認 |

起動時にエラーが出た場合は、ダイアログと、同じフォルダー内の `user_data/studio.log` を確認してください。

### Unreal Engine連携

UE連携には **MotionBricks Ti Bridge** プラグインを使用します。Windows x64・UE 5.8.4で検証しています。Fabの技術審査を通過し、法務審査中です。承認後にここへ配布ページのURLを掲載します。

導入後はStudioの「Unreal Engine → UEプロジェクトの接続設定」で対象の `.uproject` を選び、「UEに接続・同期を開始」を押します。UEでキャラクターを選び、「MotionBricks → MotionBricks Ti Bridge 連携パネル」から接続します。初回のモデル事前診断が開いたら、そこで同期を開始します。

### Kimodo連携（任意）

Kimodoでモーションを生成し、NPZとして保存した後、Studioの「モーション・ポーズ・ライブラリ」から取り込めます。Kimodoの導入とモデルの利用承認・認証は、別途行います。[Kimodo公式プロジェクト](https://research.nvidia.com/labs/sil/projects/kimodo/) · [Kimodo公式GitHub・導入案内](https://github.com/nv-tlabs/kimodo)

### MikuMikuDance（MMD）

VMD形式での書き出しに対応します。書き出し時は対象モデルのPMXまたはPMDを指定します。MMDの入手・導入は配布ページを確認してください。 [MikuMikuDance配布ページ（VPVP）](https://sites.google.com/view/vpvp/)

FBXの入出力には、Autodesk FBX SDKを使ってビルドした変換ヘルパーが必要です。ビルド手順は [FBXヘルパーのREADME](outputs/motionbricks-studio/app/native/README.md) を参照してください。

### 制作・出典

ベースとなるMotionBricksはNVIDIAが公開しています。カスタマイズはMASATAKAです。各構成要素のライセンスとクレジットは [ライセンス文書](outputs/motionbricks-studio/licenses/) に掲載しています。 [MotionBricks公式GitHub](https://github.com/NVlabs/motionbricks) · [MASATAKA / @masatakaP](https://x.com/masatakaP)

---

## English

### Getting started

MotionBricks Studio Ti is available as a standalone Windows source release. The Unreal Engine integration plugin will be listed here after Fab approves it.

**For first-time setup, double-click “Setup Studio.cmd”. To launch the application afterward, double-click “Launch MotionBricks Studio Ti.cmd”.** Both files will be in the same application folder.

### What does it do?

Studio imports and arranges motion assets, edits poses through bones, previews and seeks motion on a timeline, synchronizes playback with audio, and exports motion.

The Studio interface supports English, Japanese, Spanish, French, and Simplified Chinese.

### Requirements

- A Windows x64 PC.
- A compatible NVIDIA GPU and driver. Startup and motion generation have been tested on an RTX 4070 Ti.
- An internet connection and available storage for the application, dependencies, models, and generated files. The initial official ONNX model download is approximately 1.14 GB, with additional space required for other files.
- Git for Windows, Git LFS, and uv. Setup uses Python 3.12, which uv can obtain when needed.

Install the tools from their official sites. [Git for Windows](https://gitforwindows.org/) · [Git LFS](https://git-lfs.com/) · [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/)

### First installation

1. Install Git, Git LFS, and uv.
2. Open a writable local folder in Windows File Explorer where you want to store the application.
3. Type `powershell` into File Explorer’s address bar and press Enter.
4. Paste the following commands into the opened window, one line at a time, pressing Enter after each line. Git retrieves the application into a new `MotionBricksTi` folder.

```powershell
git lfs install
git clone https://github.com/masatakap/MotionBricksTi.git
```

5. In File Explorer, open these folders in order.

```text
MotionBricksTi
  └ outputs
      └ motionbricks-studio
```

6. **Double-click “Setup Studio.cmd”.** It checks your environment and downloads the required libraries and models.
7. When **“Setup complete”** appears, setup has finished. Press a key when prompted to close the setup window.
8. **Double-click “Launch MotionBricks Studio Ti.cmd”** in the same folder. The first launch builds an engine for your GPU. Keep the progress window open until it finishes.

The release instructions use the Git clone procedure above. Folders obtained with GitHub’s “Download ZIP” are outside the current setup workflow.

### Launching again

Double-click **“Launch MotionBricks Studio Ti.cmd”** inside the `motionbricks-studio` folder. You can create a desktop shortcut to this file for convenient access.

### If setup stops

Setup reports one of five stages. Follow the suggested action shown for that stage, then run `Setup Studio.cmd` again.

| Stage | What to check |
| --- | --- |
| `[1/5]` | Git, Git LFS, uv, Python, and folder write access |
| `[2/5]` | Dependency installation, network access, and free disk space |
| `[3/5]` | NVIDIA GPU, driver, and TensorRT initialization |
| `[4/5]` | Git LFS assets and official model downloads and verification |
| `[5/5]` | Distributed motion asset verification |

For startup errors, check the dialog and `user_data/studio.log` inside the application folder.

### Unreal Engine integration

UE integration uses the **MotionBricks Ti Bridge** plugin, tested on Windows x64 with UE 5.8.4. The plugin has passed Fab technical review and is undergoing legal review. The download link will appear here after approval.

After installation, choose “Unreal Engine → Set up UE project connection” in Studio and select your `.uproject`, then start UE synchronization. Select your character in UE and connect from “MotionBricks → MotionBricks Ti Bridge Panel”. If Model Preflight opens, select Start Sync there.

### Kimodo integration (optional)

Generate motion in Kimodo, save it as NPZ, and import it through Studio’s Motion & Pose Library. Kimodo installation, model access approval, and authentication are handled separately. [Official Kimodo project](https://research.nvidia.com/labs/sil/projects/kimodo/) · [Official Kimodo GitHub and setup guide](https://github.com/nv-tlabs/kimodo)

### MikuMikuDance (MMD)

Studio supports VMD export using a target PMX or PMD model. Visit the MMD distribution page for download and installation information. [MikuMikuDance distribution page in English (VPVP)](https://sites.google.com/view/evpvp/)

FBX import and export require the conversion helper built with the Autodesk FBX SDK. See the [FBX helper build instructions](outputs/motionbricks-studio/app/native/README.md).

### Credits

The original MotionBricks is published by NVIDIA. Customization is by MASATAKA. See the [component licenses and credits](outputs/motionbricks-studio/licenses/). [Official MotionBricks GitHub](https://github.com/NVlabs/motionbricks) · [MASATAKA / @masatakaP](https://x.com/masatakaP)
