Mesh NG Checker (Refactored+)

Blenderで選択中のメッシュをまとめて解析し、トポロジのNG（N-gon / Non-manifold / Boundary / UV missing / Flip suspect）をレポート表示＆選択支援するツールです。

✅ 複数オブジェクト選択に対応（Object Modeで一括チェック）

✅ 結果をサイドバーに表示 + Text Editorに詳細レポート出力

✅ Edit Modeで NG箇所を選択（Non-manifold / Boundary / NG Faces）


Features
チェック項目

N-gon（5角以上の面）

Non-manifold edges（link_faces >= 3 のエッジ）

Boundary edges（link_faces == 1 のエッジ）

UV missing（UVレイヤーが無い）

Flip suspect（heuristic）
面法線と「メッシュ中心→面中心」の方向を用いた簡易判定（疑い）

UI / 出力

View3D > Sidebar > NG Checker にパネル表示

Last Result にオブジェクトごとの詳細を表示

Text Editorに NG_Check_Report を作成し、詳細ログを出力


選択支援（Edit Mode）

Select NG Faces：チェックON/OFF条件に一致する面を選択

Select Non-manifold：Non-manifoldエッジを選択

Select Boundary：Boundaryエッジを選択


Demo（任意：後で差し替え）

スクショ：images/panel.png

スクショ：images/report.png

GIF/動画：images/demo.gif


Requirements

Blender 4.5（4.2+でも動作する可能性あり）

OS：Windows / macOS / Linux


Installation（Legacy Add-on / ZIP）

このリポジトリをZIPでダウンロード、または mesh_ng_checker フォルダをZIP化

Blenderを開く

Edit > Preferences > Add-ons > Install...

ZIPを選択 → インストール

Add-ons一覧で Mesh NG Checker を有効化 ✅

※ZIPの中身は「mesh_ng_checker/ フォルダが入っていて、その中に __init__.py がある」構造が正解です。


Usage
1) Object Mode：一括チェック（複数選択OK）

Object Modeでメッシュを複数選択

Run NG Check を押す

Last Result と、画面下のINFOメッセージ、Text Editorのレポートを確認

2) Edit Mode：NG箇所を選択

修正したいオブジェクトをアクティブにする

Edit Modeへ

目的のボタンを押す

Select NG Faces

Select Non-manifold

Select Boundary


Notes / Known limitations

**Flip suspect は heuristic（簡易判定）**です。
特に Join後に離れた“島（connected components）”が複数ある場合、中心点（origin）基準の関係で誤判定が増える可能性があります。
→ 必要に応じて「島ごとに基準点を分ける」改善が可能です。


Roadmap（任意）

 Flip suspect の精度改善（島ごとに基準点を計算）

 CSV出力

 自動修正（安全な範囲：法線再計算、Merge by Distance等）

 UIの整理（折りたたみ、表示の見やすさ改善）


Development
Code structure（ざっくり）

analyze_bmesh(bm, obj)：解析の本体（Object/Edit共通で使える）

MESHNGCHECKER_OT_run：Object Modeで複数選択を回して解析

Select系 Operators：Edit Modeで選択支援（edge_flags / face_flags を利用）

Scene props：チェックON/OFF、閾値、Last Result文字列


License

MIT License（例）
※必要なら LICENSE ファイルを追加してください。


Author

YourName

(link) GitHub: https://github.com/xxxxx