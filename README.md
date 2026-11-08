# Squeezelite Android (Fork)

Lyrion Music Server (LMS) 用の Android プレイヤー。上流 [CDrummond/squeezelite](https://github.com/CDrummond/squeezelite) の **0.10.1** をベースにしたフォークです。

## 公開リポジトリ

- 公開source（履歴なしsnapshot）: https://github.com/hogehonya/squeezelite-android
  - 上流 [CDrummond/squeezelite](https://github.com/CDrummond/squeezelite) の fork。`main` はレビュー済みsourceの履歴なしsnapshotです。
- 開発履歴は Gitea `honya-dev-forks/squeezelite-android` で管理しています。公開snapshotには履歴を含めません。

## ベースとフォーク独自の変更

- ベース: 上流 `0.10.1`（2026-10-12、versionName 0.10.1 / versionCode 1001）
- Android Auto対応（上流0.11.0開発版）は採用していません。
- Android 8.1 (API 27) デバイスを対象にするため、フォーク側で次を維持しています。
  - `minSdkVersion 27`（上流は23）
  - ネイティブライブラリのビルドAPIレベル27（上流は28）
  - 設定画面のBluetoothAdapter nullチェック
  - 上流で未翻訳だったロシア語・ウクライナ語の文字列を追加（lint MissingTranslation対応）
- フォーク独自の追加物: 公開用source snapshotのexportツール（`tools/export_public_source.py` とテスト）、README/SITEMAP/CLAUDE.md、`.gitignore`

## 現在の試用ビルド

- versionName 0.10.1 / versionCode 1001、minSdk 27 / targetSdk 34 / compileSdk 35、armeabi-v7a / arm64-v8a
- 署名はAndroid Debug署名の試用版です。リリース署名・長期配布用の版は未整備です。
- 試用APK SHA256: `526b31b0f9df4896bcdcd4b4a74ed9c97c3b438f58607dae4a8f16e077fe5b58`（10,345,802 bytes）
- 配布時は、APKに対応するcommitの公開snapshot（`main`）と通知文を併せて配布します。

## ビルド

### 必要環境

- Java 17以上（JDK 21で確認）
- Android SDK (compileSdk 35 / build-tools 35.0.0)
- Android NDK (27.2.12479018)
- CMake (3.22.1)、meson、ninja
- Gradle 8.14.5 / Android Gradle Plugin 8.10.1（wrapper固定）

### ビルド手順

```bash
cd android
./gradlew assembleDebug
```

APK出力: `app/build/outputs/apk/debug/app-debug.apk`

## 公開用source snapshot

公開用のsource snapshotは、APKに対応するcommitを指定して作成します。

```bash
python3 tools/export_public_source.py \
  --ref <FULL_COMMIT_SHA> \
  --output /absolute/path/source.tar.gz
```

snapshotはGitの履歴を含めず、診断用bugreport、ローカル設定、鍵、生成物を除外します。収録commit、各ファイルのSHA256、除外一覧はアーカイブ内の `PUBLIC_SOURCE_MANIFEST.json` に記録されます。

既存のGit履歴は削除・書換されず、元のcloneやホストに残ります。このsnapshotには履歴を含めません。

APKを配布するときは、対応するsource snapshotと通知文を同時に配布します。現在のAPKはdebug試用版（versionCode 1001）です。同じ署名による更新は通常の上書き更新として扱えますが、新しい署名鍵で署名したAPKへは通常の上書き更新ができません。

## 動作確認デバイス

2026-11-08時点。

| 端末 | OS | ABI | 状態 |
|------|----|-----|------|
| Lenovo ThinkSmart View (CD-18781Y) `.60` / `.61` / `.62` | LineageOS 15.1（Android 8.1 / API 27） | armeabi-v7a | 0.10.1/1001（2026-11-08）上書き導入・起動確認 |
| Pixel 7 | Android 17 / API 37 | arm64-v8a | 0.10.1/1001（2026-11-08）上書き導入・起動確認（音声再生は未確認） |
| arrows F-52G | Android 16（API 36） | arm64-v8a | 0.6.1/601のまま（2026-11-08時点で未接続のため未更新） |
| arrows F-52E | Android 16（API 36） | arm64-v8a | 0.10.1/1001（2026-11-08）上書き導入・起動確認 |

### 既知の制約

- 16KB page sizeの端末での動作は未検証です。過去のビルドではPixel 7（4096byte page）で `libsqueezelite.so` の16KB非整合警告を確認しています。
- 試用APKはAndroid Debug署名です。署名の異なるAPKへの上書き更新はできません。
- Android Autoには対応していません（上流0.11.0で追加された機能のため）。

## ライセンス

GPL-3.0 (upstream準拠)

## upstream

- https://github.com/CDrummond/squeezelite
- https://f-droid.org/en/packages/org.lyrion.squeezelite/
