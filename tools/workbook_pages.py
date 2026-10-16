# -*- coding: utf-8 -*-
"""Sheet layouts for the safe log-append workbook."""

from __future__ import annotations

from build_workbook import apply_cell, chunks, finish_sheet, font, row_height, write_title

INK = "FF1A1A1A"
HEADER_BG = "FF2B2B2B"
HEADER_FG = "FFF7F7F7"
PAPER = "FFFFFFFF"
PAPER_ALT = "FFF4F4F4"
PAPER_COMMAND = "FFEDEDED"
SECTION_BG = "FFE6E6E6"
TITLE_BG = "FF3A3A3A"


INTRO = [
    ("このブックの目的",
     "CloudWatch Alarm が、決まった言葉を見つけたときに鳴るかを、すでに動いているログを消さずに確かめるためのコマンド集です。"
     "やることは、ノートの最後に試験の1行を足すことだけです。ノートを白紙に戻す操作、ノートを捨てる操作、ロググループを削除する操作は、コピーできるセルに入れていません。"),
    ("ノートのたとえ",
     "ログファイルは、すでに字が書いてあるノートです。inode は背表紙の整理番号です。サイズはページの厚みです。"
     "1つの > は、ノートを一度白紙にしてから書き直す消しゴムです。>> は、最後のページの続きに字を足す鉛筆です。"
     "CloudWatch エージェントは、新しい行だけを運ぶ集配人で、どこまで読んだかをしおり（オフセット）で覚えています。"
     "ファイルが薄くなると、集配人は「途中で破られた」と判断し、先頭から読み直すことがあります。試験行だけでなく、昔の行がもう一度送られ、ベルが重なって鳴ることがあります。"
     "だから試験では、厚みを減らさず、同じ背表紙のまま、最後にだけ足します。"),
    ("ベルが鳴るまで",
     "ファイルへ足した行は、エージェントが改行を見つけると1件のログになります。既定では、ログをメモリにためる時間（logs の force_flush_interval）は5秒です。1MBたまると、その前でも送ります。"
     "クラウドへ届いた新しい行だけを、メトリクスフィルタが数えます。フィルタは、作るより前の行は数えません。"
     "その数が、アラームの Period、EvaluationPeriods、DatapointsToAlarm で決めた窓を超えると ALARM になります。"
     "1分以上の周期のアラームは、およそ1分ごとに窓を見ます。足した瞬間に鳴らないことがあります。"
     "PutLogEvents は、ノートを通さず集配センターへ手紙を出す方法です。フィルタとベルは試せますが、集配人のしおりは動きません。"),
    ("コピーのしかた",
     "コマンド一覧で、手順1のセルだけを選んでコピーし、先に実行します。表示を読んでから、別の操作で手順2のセルだけをコピーします。"
     "行全体をコピーすると、説明の文章まで端末へ貼られます。"
     "セルの表示が途中で切れていても、セルを1つ選べば全文がコピーされます。全文を読むときは「くわしい説明」です。"
     "手順の途中でキー入力を待たないのは、貼り付けの続きが入力に吸い込まれ、意図しない行が動く事故を避けるためです。"
     "バックスラッシュで折り返した命令は、Windows のコピーで行末に CR が付くと壊れます。長文の標準は、引用符付きのヒアドキュメントか、/tmp の下書きです。"),
    ("書き換える例文",
     "コマンドの中の「ここを」は、現場の値へ書き換えるまで残しています。残ったままでは、安全ツールも手作業の検査も拒否します。"
     "パスは絶対パスにします。* や ? は使いません。相対パスは、今いるフォルダを間違えると別のファイルに当たります。"
     "ALARM_MARKER は、メトリクスフィルタが表示した探す言葉そのものにします。"),
    ("先にやること",
     "1. P-05 で、ベルがだれを呼ぶかを見る。本番の当番につながるなら、試験であることを先に伝える。"
     "2. P-04 で、探す言葉と、平文か JSON かを見る。"
     "3. P-01 と P-02 で、背表紙、厚み、最後が改行かを見る。"
     "4. R-02 または R-01 の --self-test を、本番ログを指定せずに実行する。"
     "5. P-03 の手順1（ドライラン）を見てから、手順2で短い1行を足す。手作業なら L-02。"
     "6. A-04 でクラウドに届いたかを見る。もう一度 P-05 でベルを見る。"
     "長文は、そのあとで G-01、G-04、G-05 を使います。ファイルを開きたくない試験は A-01 と A-02 です。"),
    ("このブックがしないこと",
     "ロググループやログストリームの削除、保持期間を短くすること、フィルタの削除、アラームの無効化、削除保護を外すことは、コマンド欄に置いていません。"
     "ファイルを空にする命令、同じファイルへ自分を cat して膨らませる命令、エディタで保存し直す手順も置いていません。"
     "検証に失敗したとき、ツールは元へ戻そうとしません。戻すための切り詰めが、二度目の消去になるからです。"),
    ("確認した範囲",
     "safe_append.py、safe_append.sh、Invoke-SafeLogAppend.ps1 は、一時ファイルに対して、既存の行が残ること、無いファイルを作らないこと、自分自身への追記を拒否することを実行して確認しています。"
     "このブックの AWS コマンドは、実在のアカウントへは送っていません。リージョンと名前の例文を残しているので、書き換えない限り API は成功しません。"),
]


ACCIDENTS = [
    ("上書きのリダイレクト",
     "ファイルへ流す記号を1つだけ使うと、開いた瞬間に長さが0になります。1970年代の初期 UNIX からある動きで、続きに足す記号を1つ書き忘れるだけで起きます。",
     "記号は2つにします。L-02 または P-03 を使います。このブックの追記セルは、検査のあとに記号2つだけを使います。"),
    ("長さを0にする書き方",
     "コロンに続けてファイルへ流す形、truncate、/dev/null をコピーする形は、中身を空にします。エージェントはサイズが減ったことを検知し、先頭から読み直すことがあります。",
     "試験では厚みを減らす命令を使いません。空にしたあとの復旧も、このブックではやりません。"),
    ("tee から -a を外す",
     "tee は1971年から、画面とファイルへ同時に流すT字の管です。-a が無いと、POSIX の定めではファイルを書き直します。",
     "使うなら L-03 の tee -a だけにします。実行前に -a があることを目で見ます。"),
    ("PowerShell の入れ替え命令",
     "Set-Content と Clear-Content は中身を入れ替えるか空にします。Out-File も、Append を付けないと入れ替えです。",
     "W-01 と W-02 は FileMode.Append と、BOM を付けない UTF-8 だけを使います。"),
    ("sed のその場書き換えと、同じファイルへの流し込み",
     "GNU sed のその場書き換えは、一時ファイルへ書いてから置き換える実装があり、失敗すると空になる事故が知られています。2001年頃に広まった機能です。同じファイルへコマンドの結果を流す書き方も、先に長さを0にします。",
     "ログファイルには sed を使いません。試験スクリプトの改行を直すときも、別のファイルへ書き出します。"),
    ("自分自身へ cat して足す",
     "読みながら自分の末尾へ足すと、終わりなく膨らみ、ディスクを埋めます。下書きとログを同じパスにすると起きます。",
     "G-04 は /tmp の固定名だけを下書きにし、-ef で同一ファイルを拒否します。安全ツールも同じ inode を拒否します。"),
    ("ワイルドカードと相対パス",
     "* は複数のファイルに一度に当たります。相対パスは、今いるフォルダが違うと別のノートを開きます。",
     "絶対パスだけを使い、* や ? や [ がパスに入っていたら拒否します。"),
    ("シンボリックリンク",
     "リンクの名前に書くと、別の場所の本物へ届きます。見た名前と、実際に厚くなるファイルが違います。",
     "リンクは拒否し、本物のパスを指定し直します。"),
    ("末尾に改行が無い",
     "エージェントは改行までを1件として読みます。2026年5月の AWS の説明では、改行で終わらないファイルからはイベントが送られず、エラーも出ません。",
     "P-02 で最後のバイトが 0a であることを見てから足します。足す側も改行で終えます。"),
    ("ロググループの削除",
     "グループを削除すると、試験どころか過去のログが消えます。2025年11月26日からの削除保護は、有効なグループへの削除を ValidationException で拒否します。",
     "削除命令はこのブックにありません。P-06 は保護を付けるだけで、外すフラグは置いていません。"),
    ("古い sequence token 手順",
     "2014年から2023年1月3日までは、前の応答のトークンを次の送信に付けないと拒否されることがありました。2023年1月4日以降、トークンは無視され、待たなくても受け付けられます。",
     "トークンが取れないことを理由に、ストリームを作り直したり削除したりしません。A-02 はトークンを付けません。"),
    ("エディタで開いて保存",
     "メモ帳などで開いて保存すると、文字コードが UTF-16 になったり、全体が書き直されたり、最後の改行が落ちたりします。",
     "試験行は、このブックの追記コマンドで足します。ログ本体をエディタで保存しません。"),
    ("ローテーションの強制",
     "logrotate の強制実行や、copytruncate は、アプリの都合でファイルを薄くしたり名前を変えたりします。試験の操作としては大きすぎます。",
     "アラーム試験のあいだに、ローテーションを手動で回しません。"),
    ("noclobber だけで安心する",
     "noclobber は1979年の csh で、1つの > から既存ファイルを守るために入りました。>>、 -a の無い tee、エディタ、削除は止めません。",
     "補助として入れています。本体の約束は、>> しか使わないことと、書いたあとに厚みが減っていないことを見ることです。"),
]


GLOSSARY = [
    ("ログファイル", "アプリが今も書いているテキストのノート。試験は、このノートの最後にだけ字を足します。"),
    ("inode", "ファイルの背表紙の整理番号。追記の前後で同じなら、別のファイルにすり替わっていません。"),
    ("サイズ", "ファイルの厚み。バイト数です。試験のあとで減っていたら、誰かが途中を破っています。"),
    (">>", "終わりへ足す開き方。O_APPEND です。書く直前に位置を終わりへ動かし、そのあいだにほかの変更を挟みません。"),
    ("> を1つ", "開いたときに長さを0にしてから書く開き方。このブックのログへは使いません。"),
    ("noclobber", "既存ファイルへの、記号1つの上書きを拒否するシェルの設定。追記は止めません。"),
    ("printf", "渡した字をそのまま出す POSIX の道具。%s と \\n で、解釈せずに1行にします。"),
    ("ヒアドキュメント", "次の終端行までを文字として読む書き方。終端を引用すると、$ は動きません。"),
    ("O_APPEND", "終わりへ足す、という OS の旗。1回の write について、終わりへの移動と書き込みが分かれません。"),
    ("FILE_APPEND_DATA", "Windows で、終わりへ足す権利だけを付ける開き方。途中へ書き戻す権利を持たせません。"),
    ("メトリクスフィルタ", "届いた新しいログから、決まった言葉を数えて、CloudWatch の数値にする仕組み。過去の行は数えません。"),
    ("アラーム", "その数値が、決めた窓の中で約束を超えたら状態を変えるベル。2009年からある CloudWatch の機能です。"),
    ("Period", "数値を1点にまとめる時間の長さ。秒で指定します。"),
    ("EvaluationPeriods", "状態を決めるときに見る、最近の点の個数。"),
    ("DatapointsToAlarm", "その個数のうち、何点超えれば ALARM にするか。連続でなくても、窓の中なら数えます。"),
    ("force_flush_interval", "エージェントがログをメモリにためる最大秒数。logs の既定は5秒です。metrics の既定の60秒とは別です。"),
    ("オフセット", "エージェントが、ファイルのどこまで送ったかを覚えるしおり。追記ならしおりの後ろだけを読みます。"),
    ("PutLogEvents", "ログを API で1件ずつ送る命令。ローカルファイルは開きません。sequence token は2023年1月4日から無視されます。"),
    ("sequence token", "昔、次の送信に必要だった合言葉。今は互換のため返りますが、無くても拒否されません。"),
    ("削除保護", "2025年11月26日から付けられる、ロググループを削除させない設定。既定ではオフです。"),
    ("Live Tail", "届いた直後のログを流して見る機能。時間で課金され、最長3時間です。確認の標準は検索です。"),
    ("CWALARM-TEST", "試験行だとあとから分かる印。本番のエラー行と区別するために先頭へ付けます。"),
]


TIMELINE = [
    ("1971", "UNIX 第1版のマニュアルに tee と ls がある。ファイルへ流す仕組みは、このころからノートを空にできた。"),
    ("1979", "Bourne シェルが UNIX 第7版で広まり、ヒアドキュメントが使えるようになった。同じ年、csh が noclobber を入れ、記号1つの上書きから既存ファイルを守った。"),
    ("1983", "4.2BSD が flock を広めた。複数の書き手が、長い追記の順番を取るためです。"),
    ("1986", "4.3BSD に logger が入り、syslog へ1行渡せるようになった。"),
    ("1992", "POSIX.2 が printf を標準にし、echo の System V と BSD の差を避けられるようにした。"),
    ("2001", "GNU sed のその場書き換えが広まり、失敗すると空になる事故も知られるようになった。syslog の古い形は RFC 3164 になった。"),
    ("2009", "CloudWatch が数値のアラームとして始まった。ログそのもののサービスは、まだありません。"),
    ("2010", "systemd が始まり、のちに journal が syslog の入口を引き受けるサーバーが増えた。"),
    ("2014-07-10", "CloudWatch Logs が始まった。メトリクスフィルタで、ログの言葉を数値にし、2009年からのベルへつなげられるようになった。PutLogEvents には sequence token が必要だった。"),
    ("2017", "今の統合 CloudWatch エージェントが広まり、メトリクスとログをまとめて送れるようになった。ファイルの末尾を読むのが、ログ収集の基本になった。"),
    ("2022", "Live Tail が発表され、届いた直後のログを流して見られるようになった。閲覧時間の料金がある。"),
    ("2023-01-04", "PutLogEvents の sequence token が不要になり、ストリームごとの毎秒5回という制限も外れた。トークンは互換のため残るが、無視される。"),
    ("2025-04-02", "1件のログの上限が256KBから1MBになった。要求全体は、本文に1件26バイトを足した値で1,048,576バイトまで。"),
    ("2025-07頃", "エージェントの実装に、1MBの行を扱う変更が入った。設定例の max_event_size は256KBだった時期が長いので、動いている設定を見ない限り試験行は短くする。"),
    ("2025-09-12", "エージェントの状態ファイルで、切り詰めの検知を直す変更が入っている。サイズが減ったファイルは先頭から読み直す動きがある。"),
    ("2025-11-26", "ロググループの削除保護が、全商用リージョンで使えるようになった。既定では無効。"),
    ("2026-05-04", "AWS の説明が、改行で終わらないファイルはエージェントが送らないこと、サイズが減ると先頭から読み直すことを整理している。"),
    ("2026-10", "logs の force_flush_interval の既定は5秒、metrics の既定は60秒、アラームは1分以上の周期ならおよそ1分ごとに評価する、という公式説明が確認できる。"),
]


CHECKLIST = [
    ("1", "通知", "P-05", "AlarmActions と State が読める", "本番の当番につながるなら、試験であることを先に伝える"),
    ("2", "探す言葉", "P-04", "filterPattern とメトリクス名が読める", "ALARM_MARKER をその言葉に合わせる。JSON なら形も合わせる"),
    ("3", "ファイル", "P-01", "inode と size をメモできる", "リンク、ディレクトリ、相対パスなら中止する"),
    ("4", "改行", "P-02", "最後のバイトが 0a", "0a でなければ追記しない"),
    ("5", "道具", "R-01 または R-02", "RESULT=SELF_TEST_OK", "本番パスを渡さずに、一時ファイルだけで成功する"),
    ("6", "予告", "P-03 手順1 または L-02 手順1", "RESULT=DRY_RUN と、足す行が見える", "例文の「ここを」が残っていたら中止する"),
    ("7", "追記", "P-03 手順2 または L-02 手順2", "inode が同じで、size が減っていない", "減っていたら戻す操作をせず、人が見る"),
    ("8", "到着", "A-04", "CWALARM-TEST と試験の id が見える", "見えないときは、経路（ファイルか API か）と改行と待ち時間を見る"),
    ("9", "ベル", "もう一度 P-05", "State と Reason を読む", "窓が1分以上なら、直後に ALARM にならなくてもおかしくない"),
]


def _set_height(ws, row_index: int, texts: list[str], widths: list[float], size=11):
    needed = 18
    for text, width in zip(texts, widths):
        needed = max(needed, row_height(text, width, size))
    ws.row_dimensions[row_index].height = needed


def build_intro(wb):
    ws = wb.active
    ws.title = "はじめに"
    widths = {1: 28, 2: 120}
    write_title(ws, 2, "CloudWatch Alarm を安全に鳴らすための、ログ追記コマンド集",
                "既存のログを消さず、最後に試験の文字列だけを足します。手順1を先にコピーし、表示を読んでから手順2を別途コピーします。")
    row = 4
    apply_cell(ws.cell(row, 1), "項目", size=11, bold=True, color=HEADER_FG, bg=HEADER_BG)
    apply_cell(ws.cell(row, 2), "説明", size=11, bold=True, color=HEADER_FG, bg=HEADER_BG)
    ws.row_dimensions[row].height = 22
    for title, body in INTRO:
        parts = chunks(body, widths[2], 300)
        for index, part in enumerate(parts):
            row += 1
            label = title if index == 0 else f"{title}（続き）"
            bg = PAPER if row % 2 == 0 else PAPER_ALT
            apply_cell(ws.cell(row, 1), label, bold=True, bg=SECTION_BG)
            apply_cell(ws.cell(row, 2), part, bg=bg)
            _set_height(ws, row, [label, part], [widths[1], widths[2]])
    finish_sheet(ws, 4, row, 2, widths)
    ws.auto_filter.ref = None
    ws.freeze_panes = "A5"
    return ws


def build_list(wb, items):
    ws = wb.create_sheet("コマンド一覧")
    headers = ["ID", "分類", "順番", "名前", "ログを変更するか", "手順1_先にコピー", "手順2_確認後にコピー",
               "たとえ", "歴史の要点", "安全の要点", "実行前", "実行後", "制限"]
    widths = {1: 12, 2: 16, 3: 10, 4: 36, 5: 24, 6: 78, 7: 78, 8: 42, 9: 42, 10: 42, 11: 36, 12: 36, 13: 36}
    write_title(ws, len(headers), "コピーするコマンド",
                "手順1のセルだけをコピーして実行します。ログを変える手順2は、別のセルです。表示が切れても、セルを1つ選べば全文がコピーされます。読むときは「くわしい説明」です。")
    header_row = 4
    for col, header in enumerate(headers, 1):
        apply_cell(ws.cell(header_row, col), header, bold=True, color=HEADER_FG, bg=HEADER_BG)
    ws.row_dimensions[header_row].height = 30
    for offset, item in enumerate(items):
        row = header_row + 1 + offset
        values = [item["id"], item["group"], item["order"], item["name"], item["touches"],
                  item["step1"], item["step2"], item["kid"], item["history"], item["safety"],
                  item["before"], item["after"], item["limits"]]
        bg = PAPER if offset % 2 == 0 else PAPER_ALT
        for col, value in enumerate(values, 1):
            cell_bg = PAPER_COMMAND if col in (6, 7) else bg
            apply_cell(ws.cell(row, col), value, size=10 if col in (6, 7) else 11, bg=cell_bg,
                       border_color="FF6E6E6E" if col in (6, 7) else "FFC8C8C8")
        _set_height(ws, row, values, [widths[i] for i in range(1, 14)], 10)
    finish_sheet(ws, header_row, header_row + len(items), len(headers), widths)
    return ws


def build_detail(wb, items):
    ws = wb.create_sheet("くわしい説明")
    widths = {1: 18, 2: 28, 3: 118}
    write_title(ws, 3, "各コマンドのくわしい説明",
                "コピーは「コマンド一覧」のセルを1つだけ使います。このシートは、途中で切れないように分割して読むためのものです。")
    row = 4
    apply_cell(ws.cell(row, 1), "ID", bold=True, color=HEADER_FG, bg=HEADER_BG)
    apply_cell(ws.cell(row, 2), "項目", bold=True, color=HEADER_FG, bg=HEADER_BG)
    apply_cell(ws.cell(row, 3), "内容", bold=True, color=HEADER_FG, bg=HEADER_BG)
    ws.row_dimensions[row].height = 22
    labels = [
        ("たとえ", "kid"),
        ("歴史と背景", "history"),
        ("必要になった経緯", "why"),
        ("安全である理由", "safety"),
        ("行の意味", "meaning"),
        ("実行前", "before"),
        ("実行後", "after"),
        ("制限", "limits"),
    ]
    for item in items:
        row += 1
        banner = f"{item['id']}  {item['name']}    順番: {item['order']}    ログを変更するか: {item['touches']}"
        apply_cell(ws.cell(row, 1), item["id"], bold=True, color=HEADER_FG, bg=TITLE_BG)
        apply_cell(ws.cell(row, 2), "コマンド", bold=True, color=HEADER_FG, bg=TITLE_BG)
        apply_cell(ws.cell(row, 3), banner, bold=True, color=HEADER_FG, bg=TITLE_BG)
        ws.row_dimensions[row].height = 24
        for label, key in labels:
            parts = chunks(item[key], widths[3], 300)
            for index, part in enumerate(parts):
                row += 1
                apply_cell(ws.cell(row, 1), item["id"], bg=SECTION_BG)
                apply_cell(ws.cell(row, 2), label if index == 0 else f"{label}（続き）", bold=True, bg=SECTION_BG)
                apply_cell(ws.cell(row, 3), part, bg=PAPER)
                _set_height(ws, row, [item["id"], label, part], [widths[1], widths[2], widths[3]])
        for step_name, step_key in (("手順1を読む", "step1"), ("手順2を読む", "step2")):
            lines = item[step_key].split("\n")
            group_size = 16
            for start in range(0, len(lines), group_size):
                row += 1
                part = "\n".join(lines[start:start + group_size])
                suffix = "" if start == 0 else "（続き。コピーは一覧のセル）"
                apply_cell(ws.cell(row, 1), item["id"], bg=PAPER_COMMAND)
                apply_cell(ws.cell(row, 2), step_name + suffix, bold=True, bg=PAPER_COMMAND)
                apply_cell(ws.cell(row, 3), part, size=10, bg=PAPER_COMMAND, border_color="FF6E6E6E")
                _set_height(ws, row, [item["id"], step_name, part], [widths[1], widths[2], widths[3]], 10)
    finish_sheet(ws, 4, row, 3, widths)
    ws.auto_filter.ref = None
    ws.freeze_panes = "A5"
    return ws


def build_check(wb):
    ws = wb.create_sheet("実行チェック")
    headers = ["順番", "見ること", "使うID", "期待する結果", "ダメなとき"]
    widths = {1: 12, 2: 18, 3: 28, 4: 55, 5: 70}
    write_title(ws, 5, "実行の順番", "上から順に進めます。各コマンドの中身は「コマンド一覧」にあります。")
    row = 4
    for col, header in enumerate(headers, 1):
        apply_cell(ws.cell(row, col), header, bold=True, color=HEADER_FG, bg=HEADER_BG)
    for item in CHECKLIST:
        row += 1
        bg = PAPER if row % 2 == 0 else PAPER_ALT
        for col, value in enumerate(item, 1):
            apply_cell(ws.cell(row, col), value, bg=bg)
        _set_height(ws, row, list(item), [widths[i] for i in range(1, 6)])
    finish_sheet(ws, 4, row, 5, widths)
    return ws


def build_accidents(wb):
    ws = wb.create_sheet("事故を防ぐ")
    headers = ["やりがちなこと", "何が起きるか", "代わりにすること"]
    widths = {1: 32, 2: 78, 3: 70}
    write_title(ws, 3, "実行しない操作",
                "このシートに、ログを消す完成コマンドは置いていません。形を文章で説明し、代わりの安全なIDを示します。")
    row = 4
    for col, header in enumerate(headers, 1):
        apply_cell(ws.cell(row, col), header, bold=True, color=HEADER_FG, bg=HEADER_BG)
    for name, happens, instead in ACCIDENTS:
        row += 1
        values = [name, happens, instead]
        bg = PAPER if row % 2 == 0 else PAPER_ALT
        for col, value in enumerate(values, 1):
            apply_cell(ws.cell(row, col), value, bg=bg)
        _set_height(ws, row, values, [widths[1], widths[2], widths[3]])
    finish_sheet(ws, 4, row, 3, widths)
    return ws


def build_words(wb):
    ws = wb.create_sheet("言葉と年表")
    widths = {1: 28, 2: 110, 3: 22, 4: 90}
    write_title(ws, 4, "言葉と、必要になった順番",
                "左が言葉の意味、右が年表です。年は、その仕組みが公になった時期です。")
    apply_cell(ws.cell(4, 1), "言葉", bold=True, color=HEADER_FG, bg=HEADER_BG)
    apply_cell(ws.cell(4, 2), "意味", bold=True, color=HEADER_FG, bg=HEADER_BG)
    apply_cell(ws.cell(4, 3), "年", bold=True, color=HEADER_FG, bg=HEADER_BG)
    apply_cell(ws.cell(4, 4), "何が必要になったか", bold=True, color=HEADER_FG, bg=HEADER_BG)
    ws.row_dimensions[4].height = 22
    row = 4
    total = max(len(GLOSSARY), len(TIMELINE))
    for index in range(total):
        row += 1
        bg = PAPER if index % 2 == 0 else PAPER_ALT
        if index < len(GLOSSARY):
            word, meaning = GLOSSARY[index]
        else:
            word, meaning = "", ""
        if index < len(TIMELINE):
            year, event = TIMELINE[index]
        else:
            year, event = "", ""
        values = [word, meaning, year, event]
        for col, value in enumerate(values, 1):
            apply_cell(ws.cell(row, col), value, bg=bg, bold=(col in (1, 3) and bool(value)))
        _set_height(ws, row, values, [widths[1], widths[2], widths[3], widths[4]])
    finish_sheet(ws, 4, row, 4, widths)
    ws.auto_filter.ref = None
    return ws
