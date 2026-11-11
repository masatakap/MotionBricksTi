# MotionBricks Studio Ti

**Windows x64 ZIP版 / Windows x64 ZIP release**

[Windows版ZIPをダウンロード / Download for Windows](https://github.com/masatakap/MotionBricksTi/releases/latest/download/MotionBricksStudioTi-Windows-x64.zip)

NVIDIAのMotionBricksをベースに、モーション編集をはじめとした便利な機能を追加した拡張ツールです。Kimodoで生成したモーションの取り込み、MikuMikuDance向けのモデル読込（PMX／PMD）・モーション出力（VMD）に対応しています。

An enhanced tool based on NVIDIA MotionBricks, with convenient features for motion editing and production. It supports importing motion generated with Kimodo, loading PMX/PMD target models, and exporting VMD motion for MikuMikuDance.

### 紹介映像 / Promotional video

https://github.com/user-attachments/assets/b97f51d8-d9ea-477f-b890-81d7a7587abb

[日本語](#日本語) · [English](#english)

---

## 日本語

### はじめての方へ

MotionBricks Studio Ti本体を先行公開しています。Unreal Engine連携プラグインの配布先は、Fabの審査完了後に掲載します。

展開したフォルダー内の **「Launch MotionBricks Studio Ti.cmd」** をダブルクリックします。初回は必要な環境を自動で準備します。

### どんなアプリ？

モーション素材の読み込みと配置、ボーンによるポーズ編集、タイムラインでの再生・シーク、音との同期、モーションの書き出しを行います。

Studioの表示言語は日本語、英語、スペイン語、フランス語、中国語（簡体字）から選べます。

### 必要な環境

- Windows x64のPC
- 対応するNVIDIA GPUとドライバー。開発環境ではRTX 4070 Tiで起動・モーション生成を確認しています。
- インターネット接続と、アプリ・依存ライブラリ・モデル・生成データを保存する空き容量。初回の公式ONNXモデル取得は約1.14 GBで、その他の保存領域も必要です。

### 初回起動

1. [GitHub Releases](https://github.com/masatakap/MotionBricksTi/releases/latest)の「Assets」から **`MotionBricksStudioTi-Windows-x64.zip`** をダウンロードします。
2. ZIPを右クリックして「すべて展開」を選びます。
3. 展開した `MotionBricksStudioTi` フォルダーを開き、**`Launch MotionBricks Studio Ti.cmd`** をダブルクリックします。

初回はPythonと依存ライブラリを準備し、NVIDIA公式モデル約1.14 GBを取得します。初回起動時はTensorRTエンジンも構築するため、Studioの画面が出るまでお待ちください。2回目以降も同じファイルをダブルクリックします。

途中で止まった場合は表示されたメッセージを確認し、同じ起動ファイルを再度開きます。Studio起動後のログは `outputs/motionbricks-studio/user_data/studio.log` にあります。

### Unreal Engine連携

UE連携には **MotionBricks Ti Bridge** プラグインを使用します。Windows x64・UE 5.8.4で検証しています。Fabの技術審査を通過し、法務審査中です。承認後にここへ配布ページのURLを掲載します。

導入後はStudioの「Unreal Engine → UEプロジェクトの接続設定」で対象の `.uproject` を選び、「UEに接続・同期を開始」を押します。UEでキャラクターを選び、「MotionBricks → MotionBricks Ti Bridge 連携パネル」から接続します。初回のモデル事前診断が開いたら、そこで同期を開始します。

### Kimodo連携（任意）

Kimodoでモーションを生成し、NPZとして保存した後、Studioの「モーション・ポーズ・ライブラリ」から取り込めます。Kimodoの導入とモデルの利用承認・認証は、別途行います。[Kimodo公式プロジェクト](https://research.nvidia.com/labs/sil/projects/kimodo/) · [Kimodo公式GitHub・導入案内](https://github.com/nv-tlabs/kimodo)

### MikuMikuDance（MMD）

VMD形式での書き出しに対応します。書き出し時は対象モデルのPMXまたはPMDを指定します。MMDの入手・導入は配布ページを確認してください。 [MikuMikuDance配布ページ（VPVP）](https://sites.google.com/view/vpvp/)

FBXの入出力には、Autodesk FBX SDKを使ってビルドした変換ヘルパーが必要です。ビルド手順はZIP内の `outputs/motionbricks-studio/app/native/README.md` にあります。

### 制作・出典

ベースとなるMotionBricksはNVIDIAが公開しています。カスタマイズはMASATAKAです。ライセンスとクレジットはZIP内の `outputs/motionbricks-studio/licenses/` にあります。 [MotionBricks公式GitHub](https://github.com/NVlabs/motionbricks) · [MASATAKA / @masatakaP](https://x.com/masatakaP)

---

## English

### Getting started

MotionBricks Studio Ti is available as a standalone Windows ZIP release. The Unreal Engine integration plugin will be listed here after Fab approves it.

Double-click **“Launch MotionBricks Studio Ti.cmd”** in the extracted folder. It prepares the required environment on the first run.

### What does it do?

Studio imports and arranges motion assets, edits poses through bones, previews and seeks motion on a timeline, synchronizes playback with audio, and exports motion.

The Studio interface supports English, Japanese, Spanish, French, and Simplified Chinese.

### Requirements

- A Windows x64 PC.
- A compatible NVIDIA GPU and driver. Startup and motion generation have been tested on an RTX 4070 Ti.
- An internet connection and available storage for the application, dependencies, models, and generated files. The initial official ONNX model download is approximately 1.14 GB, with additional space required for other files.

### First launch

1. Download **`MotionBricksStudioTi-Windows-x64.zip`** from the Assets section of [GitHub Releases](https://github.com/masatakap/MotionBricksTi/releases/latest).
2. Right-click the ZIP and choose **Extract All**.
3. Open the extracted `MotionBricksStudioTi` folder and double-click **`Launch MotionBricks Studio Ti.cmd`**.

The first launch prepares Python and its dependencies and downloads approximately 1.14 GB of official NVIDIA models. Studio also builds a TensorRT engine on its first launch. Wait for the Studio window to open, then use the same launcher for subsequent runs.

If setup stops, review the on-screen message and run the launcher again. Studio writes its startup log to `outputs/motionbricks-studio/user_data/studio.log`.

### Unreal Engine integration

UE integration uses the **MotionBricks Ti Bridge** plugin, tested on Windows x64 with UE 5.8.4. The plugin has passed Fab technical review and is undergoing legal review. The download link will appear here after approval.

After installation, choose “Unreal Engine → Set up UE project connection” in Studio and select your `.uproject`, then start UE synchronization. Select your character in UE and connect from “MotionBricks → MotionBricks Ti Bridge Panel”. If Model Preflight opens, select Start Sync there.

### Kimodo integration (optional)

Generate motion in Kimodo, save it as NPZ, and import it through Studio’s Motion & Pose Library. Kimodo installation, model access approval, and authentication are handled separately. [Official Kimodo project](https://research.nvidia.com/labs/sil/projects/kimodo/) · [Official Kimodo GitHub and setup guide](https://github.com/nv-tlabs/kimodo)

### MikuMikuDance (MMD)

Studio supports VMD export using a target PMX or PMD model. Visit the MMD distribution page for download and installation information. [MikuMikuDance distribution page in English (VPVP)](https://sites.google.com/view/evpvp/)

FBX import and export require the conversion helper built with the Autodesk FBX SDK. The ZIP includes build instructions in `outputs/motionbricks-studio/app/native/README.md`.

### Credits

The original MotionBricks is published by NVIDIA. Customization is by MASATAKA. The ZIP includes component licenses and credits in `outputs/motionbricks-studio/licenses/`. [Official MotionBricks GitHub](https://github.com/NVlabs/motionbricks) · [MASATAKA / @masatakaP](https://x.com/masatakaP)
