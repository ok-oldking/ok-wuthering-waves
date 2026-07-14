<div align="center">
  <h1 align="center">
    <img src="icon.png" width="200" alt="ok-ww logo"/>
    <br/>
    ok-ww
  </h1> 
  
  <p>
    <a href="https://github.com/ok-oldking/ok-script">ok-script</a> で開発された、鳴潮（Wuthering Waves）向けの画像認識ベースの自動化ツールです。バックグラウンドモードに対応しています。
  </p>
  
  <p><i>Windows のユーザーインターフェースをシミュレートして動作し、メモリの読み取りやファイルの改変は一切行いません。</i></p>
</div>

<!-- Badges -->
<div align="center">
  
![Platform](https://img.shields.io/badge/platform-Windows-blue)
[![GitHub release](https://img.shields.io/github/v/release/ok-oldking/ok-wuthering-waves)](https://github.com/ok-oldking/ok-wuthering-waves/releases)
[![Total Downloads](https://img.shields.io/github/downloads/ok-oldking/ok-wuthering-waves/total)](https://github.com/ok-oldking/ok-wuthering-waves/releases)
[![Discord](https://img.shields.io/discord/296598043787132928?color=5865f2&label=%20Discord)](https://discord.gg/vVyCatEBgA)

</div>

**デモ＆チュートリアル:** [![YouTube](https://img.shields.io/badge/YouTube-%23FF0000.svg?style=for-the-badge&logo=YouTube&logoColor=white)](https://youtu.be/h6P1KWjdnB4)

---

## ⚠️ 免責事項

本ソフトウェアは、鳴潮のゲームプレイの一部を自動化するために設計された外部補助ツールです。関連する法令を遵守し、標準的なユーザーインターフェース操作のシミュレートのみによってゲームと連携します。本プロジェクトはユーザーの反復的な作業を簡略化することを目的としており、ゲームバランスを損なったり、不公平な優位性を提供したりするものではありません。ゲームのファイルやデータを改変することは決してありません。

本ソフトウェアはオープンソースかつ無料であり、個人の学習および交流のみを目的としています。商業目的や営利目的の活動には使用しないでください。開発チームは最終的な解釈権を留保します。本ソフトウェアの使用によって生じたいかなる問題についても、本プロジェクトおよびその開発者は責任を負いません。

なお、Kuro Games 公式による鳴潮のフェアプレイ宣言では、以下のように定められています:
> ゲーム体験を妨害するサードパーティ製ツールの使用は固く禁止されています。
> チート、スピードハック、チートソフトウェア、マクロスクリプトなどの不正なツールの使用に対しては、厳格な措置を講じます。これには、自動周回、スキル加速、無敵化、テレポート、ゲームデータの改変などが含まれますが、これらに限定されません。
> 違反が確認された場合、その重大性と頻度に応じて、不正に得た利益の没収、ゲームアカウントの一時停止または永久凍結などを含む（ただしこれらに限定されない）処罰を科します。

**本ソフトウェアを使用することにより、あなたは上記の声明を読み、理解し、同意したものとみなされ、起こりうるすべてのリスクを自らの意思で負うことになります。**

## 🚀 クイックスタート

1.  **インストーラーのダウンロード**: 下記の「ダウンロード」セクションから、最新の `ok-ww-win32-setup.exe` インストーラーファイルをダウンロードします。
2.  **プログラムのインストール**: `ok-ww-win32-setup.exe` ファイルをダブルクリックし、画面の指示に従ってインストールを完了します。
3.  **プログラムの実行**: インストール後、デスクトップのショートカットまたはスタートメニューから `ok-ww` を起動します。

## 📥 ダウンロード

*   **[GitHub](https://github.com/ok-oldking/ok-wuthering-waves/releases)**: 公式リリースページ。世界中から高速にアクセスできます。（**`Source Code` のアーカイブではなく、`setup.exe` インストーラーをダウンロードしてください**）。

## ✨ 主な機能
<img width="1778" height="1186" alt="QQ_1762961412161" src="https://github.com/user-attachments/assets/0109c68e-d714-4c34-b016-b4b45f9861fd" />

*   **高解像度対応**: 4K までのすべての 16:9 解像度（最低 1600x900）でスムーズに動作します。一部の機能は 21:9 などのウルトラワイド解像度にも対応しています。
*   **バックグラウンドモード**: ゲームウィンドウが最小化されていたり、他のウィンドウに隠れていたりしてもバックグラウンドで動作するため、PC を他の作業に使えます。
*   **インテリジェント認識**: すべてのキャラクターを自動的に認識するため、スキルシーケンスを手動で設定する必要がありません。ワンクリックで開始できます。
*   **自動ミュート**: バックグラウンドで動作している間、ゲームの音声を自動的にミュートできます。

## 🔧 トラブルシューティング

問題が発生した場合は、サポートを求める前に以下の手順を一つずつ確認してください:

1.  **インストールパス**: ソフトウェアが**英数字のみ**を含むパス（例: `D:\Games\ok-ww`）にインストールされていることを確認してください。`C:\Program Files` や、英語以外の文字を含むフォルダーにはインストールしないでください。
2.  **アンチウイルスソフト**: ファイルが誤って削除またはブロックされるのを防ぐため、ソフトウェアのインストールディレクトリをアンチウイルスソフト（Windows Defender を含む）の**例外またはホワイトリスト**に追加してください。
3.  **ディスプレイ設定**:
    *   グラフィックカードのフィルター（NVIDIA Game Filter など）やシャープニング機能をすべてオフにしてください。
    *   ゲームのデフォルトの明るさ設定を使用してください。
    *   ゲーム画面上に情報を表示するオーバーレイ（MSI Afterburner や Fraps などのフレームレート表示等）を無効にしてください。
4.  **カスタムキー設定**: ゲーム内のデフォルトのキー設定を変更している場合は、`ok-ww` の設定でも同様に更新する必要があります。設定に記載されているキー設定のみがサポートされています。
5.  **ソフトウェアのバージョン**: 最新バージョンの `ok-ww` を使用していることを確認してください。
6.  **ゲームのパフォーマンス**: ゲームが **60 FPS** で安定して動作することを確認してください。フレームレートが不安定な場合は、ゲームのグラフィック品質や解像度を下げてみてください。
7.  **ゲームの接続切断**: サーバーから頻繁に切断される場合は、ツールを起動する前に手動でゲームを起動し、5分ほどプレイしてみてください。切断された場合は、ゲームを閉じずにそのまま再ログインしてください。
8.  **サポートを受ける**: 上記の手順で問題が解決しない場合は、コミュニティチャンネルを通じて詳細なバグレポートを提出してください。

---

## 💻 開発者向け

### ソースコードからの実行（Python）

本プロジェクトは Python 3.12 のみをサポートしています。

```bash
# 依存関係のインストールまたは更新
pip install -r requirements.txt --upgrade

# リリース版の実行
python main.py

# デバッグ版の実行
python main_debug.py
```

### コマンドライン引数

コマンドライン引数を使用して自動起動できます。

```bash
# 例: 起動後に最初のタスクを自動実行し、完了したらプログラムを終了する
ok-ww.exe -t 1 -e
```

*   `-t` または `--task`: 起動後にリストの N 番目のタスクを自動的に実行します。`1` は最初のタスクを表します。
*   `-e` または `--exit`: タスクの完了後にプログラムを自動的に終了します。

## 💬 参加しよう

本プロジェクトは [ok-script](https://github.com/ok-oldking/ok-script) フレームワークをベースに開発されています。コアコードはわずか約 3000 行（Python）で、シンプルでメンテナンスしやすい構成です。独自の自動化プロジェクトを作成したい開発者の方は、ぜひ [ok-script](https://github.com/ok-oldking/ok-script) をご利用ください。

## 🔗 ok-script を使用しているプロジェクト:

*   鳴潮（Wuthering Waves）: [https://github.com/ok-oldking/ok-wuthering-waves](https://github.com/ok-oldking/ok-wuthering-waves)
*   原神（メンテナンス終了。ただしバックグラウンドでの会話自動スキップには引き続き使用可能）: [https://github.com/ok-oldking/ok-genshin-impact](https://github.com/ok-oldking/ok-genshin-impact)
*   ドールズフロントライン2: [https://github.com/ok-oldking/ok-gf2](https://github.com/ok-oldking/ok-gf2)
*   崩壊：スターレイル: [https://github.com/Shasnow/ok-starrailassistant](https://github.com/Shasnow/ok-starrailassistant)
*   スターレゾナンス: [https://github.com/Sanheiii/ok-star-resonance](https://github.com/Sanheiii/ok-star-resonance)
*   デュエットナイトアビス: [https://github.com/BnanZ0/ok-duet-night-abyss](https://github.com/BnanZ0/ok-duet-night-abyss)
*   アッシュエコーズ（更新停止）: [https://github.com/ok-oldking/ok-baijing](https://github.com/ok-oldking/ok-baijing)


## ❤️ スポンサーと謝辞

### スポンサー
*   **EXE 署名**: [SignPath.io](https://signpath.io/) による無料のコード署名、証明書は [SignPath Foundation](https://signpath.org/) より提供。

### 謝辞
*   [lazydog28/mc_auto_boss](https://github.com/lazydog28/mc_auto_boss)
*   [ok-oldking/OnnxOCR](https://github.com/ok-oldking/OnnxOCR)
*   [zhiyiYo/PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)
*   [Toufool/AutoSplit](https://github.com/Toufool/AutoSplit)
