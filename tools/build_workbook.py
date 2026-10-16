# -*- coding: utf-8 -*-
"""Build the monotone Meiryo UI workbook of safe CloudWatch alarm log appends."""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.styles.fonts import DEFAULT_FONT
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins

DEFAULT_FONT.name = "Meiryo UI"
DEFAULT_FONT.sz = 11

OUT = r"C:\Users\taka_\Grok\Alarm_Insert_Commands_Grok\CloudWatch_Alarm_安全ログ追記コマンド集.xlsx"

INK = "FF1A1A1A"
INK_SOFT = "FF333333"
PAPER = "FFFFFFFF"
PAPER_ALT = "FFF4F4F4"
PAPER_COMMAND = "FFEDEDED"
HEADER_BG = "FF2B2B2B"
HEADER_FG = "FFF7F7F7"
TITLE_BG = "FF3A3A3A"
SECTION_BG = "FFE6E6E6"
LINE = "FFC8C8C8"
LINE_STRONG = "FF6E6E6E"

FONT = "Meiryo UI"
PLACEHOLDER_FILE = "/ここを既存ログの絶対パスに書き換える/app.log"
PLACEHOLDER_MARKER = "ここをメトリクスフィルタが探す文字列に書き換える"
PLACEHOLDER_OPERATOR = "ここを自分の名前に書き換える"
PLACEHOLDER_GROUP = "/ここをロググループ名に書き換える"
PLACEHOLDER_STREAM = "ここをログストリーム名に書き換える"
PLACEHOLDER_ALARM = "ここをアラーム名に書き換える"
PLACEHOLDER_REGION = "ここをリージョン名に書き換える"
PLACEHOLDER_ARN = "ここをロググループのARNに書き換える"


def font(size=11, bold=False, color=INK):
    return Font(name=FONT, size=size, bold=bold, color=color, italic=False)


def fill(rgb):
    return PatternFill(fill_type="solid", fgColor=rgb)


def border(color=LINE):
    side = Side(style="thin", color=color)
    return Border(left=side, right=side, top=side, bottom=side)


def align():
    return Alignment(wrap_text=True, vertical="top", horizontal="left", shrink_to_fit=False)


def visual_units(text: str) -> float:
    total = 0.0
    for char in text:
        if char == "\t":
            total += 4
        elif ord(char) < 128:
            total += 1
        else:
            total += 2
    return total


def wrapped_lines(text: str, width: float) -> int:
    usable = max(width - 2, 8)
    lines = 0
    for paragraph in str(text).split("\n"):
        if paragraph == "":
            lines += 1
            continue
        lines += max(1, math.ceil(visual_units(paragraph) / usable))
    return lines


def row_height(text: str, width: float, size=11) -> float:
    line_pt = 16.5 if size >= 11 else 15.5
    return min(400, wrapped_lines(text, width) * line_pt + 8)


def chunks(text: str, width: float, max_height=320, size=11) -> list[str]:
    line_pt = 16.5 if size >= 11 else 15.5
    max_lines = max(6, int((max_height - 8) / line_pt))
    blocks = []
    current: list[str] = []
    count = 0
    for paragraph in str(text).split("\n"):
        need = wrapped_lines(paragraph, width) if paragraph else 1
        if current and count + need > max_lines:
            blocks.append("\n".join(current))
            current = [paragraph]
            count = need
        else:
            current.append(paragraph)
            count += need
    if current:
        blocks.append("\n".join(current))
    return blocks or [""]


def apply_cell(cell, value, *, size=11, bold=False, color=INK, bg=PAPER, fmt="@", border_color=LINE):
    cell.value = value
    cell.font = font(size, bold, color)
    cell.fill = fill(bg)
    cell.alignment = align()
    cell.number_format = fmt
    cell.border = border(border_color)


def finish_sheet(ws, header_row: int, last_row: int, last_col: int, widths: dict[int, float]):
    ws.sheet_view.showGridLines = False
    ws.sheet_view.zoomScale = 110
    ws.sheet_view.view = "normal"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A3
    ws.page_setup.fitToPage = False
    ws.page_setup.scale = 70
    ws.sheet_properties.pageSetUpPr.fitToPage = False
    ws.page_margins = PageMargins(left=0.45, right=0.45, top=0.7, bottom=0.55, header=0.25, footer=0.25)
    ws.oddHeader.left.text = "CloudWatch Alarm 試験　安全なログ追記"
    ws.oddHeader.left.font = FONT
    ws.oddHeader.left.size = 10
    ws.oddFooter.left.text = "コピーするときはコマンドのセルを1つだけ選ぶ"
    ws.oddFooter.left.font = FONT
    ws.oddFooter.left.size = 9
    ws.oddFooter.right.text = "&P / &N"
    ws.oddFooter.right.font = FONT
    ws.print_title_rows = f"1:{header_row}"
    ws.page_setup.horizontalCentered = False
    ws.sheet_properties.tabColor = "FF4A4A4A"
    for index, width in widths.items():
        ws.column_dimensions[get_column_letter(index)].width = width
    if last_row >= header_row and last_col >= 1:
        ws.auto_filter.ref = f"A{header_row}:{get_column_letter(last_col)}{last_row}"
        ws.freeze_panes = f"A{header_row + 1}"
    for row in ws.iter_rows(min_row=1, max_row=max(last_row, header_row), min_col=1, max_col=last_col):
        for cell in row:
            if cell.font is None or cell.font.name != FONT:
                cell.font = font()
            if cell.alignment is None or not cell.alignment.wrap_text:
                cell.alignment = align()


def write_title(ws, last_col: int, title: str, subtitle: str) -> int:
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)
    apply_cell(ws.cell(1, 1), title, size=16, bold=True, color=HEADER_FG, bg=HEADER_BG)
    ws.row_dimensions[1].height = 28
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=last_col)
    apply_cell(ws.cell(2, 1), subtitle, size=11, bold=False, color=HEADER_FG, bg=TITLE_BG)
    ws.row_dimensions[2].height = min(400, row_height(subtitle, sum(1 for _ in range(last_col)) * 18, 11))
    return 3


def guard(extra: list[str] | None = None) -> list[str]:
    lines = [
        "# bash で実行する。3つの値を現場の値へ書き換えてから実行する。",
        f"LOG_FILE='{PLACEHOLDER_FILE}'",
        f"ALARM_MARKER='{PLACEHOLDER_MARKER}'",
        f"OPERATOR='{PLACEHOLDER_OPERATOR}'",
        "set -eu",
        "set -o pipefail",
        "set -o noclobber",
        'case "$LOG_FILE" in',
        '  /*) ;;',
        '  *) printf "%s\\n" "中止: 絶対パスだけを受け付けます。"; exit 2 ;;',
        "esac",
        'case "$LOG_FILE" in',
        "  *'*'*|*'?'*|*'['*) printf '%s\\n' \"中止: ワイルドカードは使えません。\"; exit 2 ;;",
        "  /|/proc|/proc/*|/sys|/sys/*|/dev|/dev/*) printf '%s\\n' \"中止: システム領域です。\"; exit 2 ;;",
        "  *ここを*) printf '%s\\n' \"中止: パスの例文が残っています。\"; exit 2 ;;",
        "esac",
        'case "$ALARM_MARKER" in',
        "  \"\"|*ここを*) printf '%s\\n' \"中止: 検知文字列を現場の値へ書き換えてください。\"; exit 2 ;;",
        "esac",
        'case "$OPERATOR" in',
        "  \"\"|*ここを*) printf '%s\\n' \"中止: 操作者の名前を書いてください。\"; exit 2 ;;",
        "esac",
        'if [ -L "$LOG_FILE" ]; then printf "%s\\n" "中止: シンボリックリンクです。本物のパスを指定します。"; exit 2; fi',
        'if [ ! -f "$LOG_FILE" ]; then printf "%s\\n" "中止: 既存の通常ファイルではありません。新しいファイルは作りません。"; exit 2; fi',
        'if [ ! -w "$LOG_FILE" ]; then printf "%s\\n" "中止: 書き込めません。"; exit 2; fi',
        'SIZE="$(stat -c "%s" "$LOG_FILE")"',
        'INODE="$(stat -c "%i" "$LOG_FILE")"',
        'printf "%s\\n" "inode=${INODE} size=${SIZE}"',
        'if [ "$SIZE" -gt 0 ]; then',
        '  LAST="$(tail -c 1 "$LOG_FILE" | od -An -tx1 | tr -d "[:space:]")"',
        '  printf "%s\\n" "last_byte=${LAST}"',
        '  if [ "$LAST" != "0a" ]; then printf "%s\\n" "中止: 末尾が改行ではありません。"; exit 2; fi',
        "fi",
        'NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"',
        'HOST="$(hostname 2>/dev/null || printf "%s" unknown-host)"',
        'TEST_ID="$(od -An -N16 -tx1 /dev/urandom | tr -d "[:space:]")"',
        'LINE="CWALARM-TEST time=${NOW} host=${HOST} operator=${OPERATOR} id=${TEST_ID} marker=${ALARM_MARKER}"',
    ]
    if extra:
        lines.extend(extra)
    return lines


def join(lines: list[str]) -> str:
    return "\n".join(lines)


def verify_tail(label: str) -> list[str]:
    return [
        'AFTER_INODE="$(stat -c "%i" "$LOG_FILE")"',
        'AFTER_SIZE="$(stat -c "%s" "$LOG_FILE")"',
        'if [ "$AFTER_INODE" != "$INODE" ]; then printf "%s\\n" "検証失敗: inode が変わりました。戻す操作はしません。"; exit 3; fi',
        'if [ "$AFTER_SIZE" -lt "$SIZE" ]; then printf "%s\\n" "検証失敗: サイズが減りました。戻す操作はしません。"; exit 3; fi',
        'printf "%s\\n" "size_before=${SIZE} size_after=${AFTER_SIZE} delta=$((AFTER_SIZE - SIZE))"',
        f'printf "%s\\n" "{label} id=${{TEST_ID}}"',
    ]


NONE = "この手順に、ログを変えるコマンドはありません。"


def commands() -> list[dict]:
    preview_tail = [
        'printf "%s\\n" "追記予定の1行:"',
        'printf "%s\\n" "$LINE"',
        'printf "%s\\n" "ここまでではファイルは変わっていません。問題なければ、別のセルの手順2を実行します。"',
    ]
    append_tail = ['printf "%s\\n" "$LINE" >> "$LOG_FILE"'] + verify_tail("追記しました。")
    items = [
        {
            "id": "P-05",
            "group": "見るだけ",
            "order": "1",
            "name": "アラームの状態と通知先を見る",
            "touches": "いいえ",
            "step1": join([
                "# 読み取りだけ。ログもアラームも変更しない。",
                f"REGION='{PLACEHOLDER_REGION}'",
                f"ALARM_NAME='{PLACEHOLDER_ALARM}'",
                "aws cloudwatch describe-alarms \\",
                '  --region "$REGION" \\',
                '  --alarm-names "$ALARM_NAME" \\',
                "  --query 'MetricAlarms[].{Name:AlarmName,State:StateValue,Reason:StateReason,Actions:AlarmActions,Period:Period,Eval:EvaluationPeriods,Points:DatapointsToAlarm,Threshold:Threshold,Missing:TreatMissingData}' \\",
                "  --output table",
            ]),
            "step2": NONE,
            "kid": "ベルが、だれの机で鳴るかを先に見ます。試験の1行は、そのベルを本当に鳴らすことがあります。夜中に人を起こす設定なら、起こしてよいと伝わってから実行します。",
            "history": "CloudWatch のアラームは、ログより先の2009年に、数値の監視として始まりました。2014年7月10日に CloudWatch Logs が始まり、ログの言葉を数値へ変えて、その古いベルにつなげられるようになりました。ベルの窓は Period、EvaluationPeriods、DatapointsToAlarm の3つです。1分以上の周期のアラームは、およそ1分ごとに、その窓を見直します。",
            "safety": "describe-alarms は状態を表示するだけで、OK にも ALARM にもしません。通知先の変更や削除はこのセルに入れていません。",
            "before": "アラーム名とリージョンの例文を、現場の値へ書き換えます。",
            "after": "State、AlarmActions、Period、Threshold、TreatMissingData を読みます。AlarmActions が本番の当番につながっているなら、試験はその人に先に伝えます。",
            "limits": "名前を間違えると、何も表示されないか、エラーになります。アラームの中身は変わりません。",
            "meaning": "aws cloudwatch describe-alarms は、ベルの設定を読む命令です。--query は、必要な項目だけを表にします。バックスラッシュは、1つの命令を見やすく改行するための記号で、行の最後に置きます。後ろに空白があると、改行が壊れます。",
            "why": "試験の事故で多いのは、ログを消すことと同じくらい、本番の当番を起こすことです。書く前に、ベルの行き先を見ます。",
        },
        {
            "id": "P-04",
            "group": "見るだけ",
            "order": "2",
            "name": "メトリクスフィルタが探す言葉を見る",
            "touches": "いいえ",
            "step1": join([
                "# 読み取りだけ。フィルタもログも変更しない。",
                f"REGION='{PLACEHOLDER_REGION}'",
                f"LOG_GROUP='{PLACEHOLDER_GROUP}'",
                "aws logs describe-metric-filters \\",
                '  --region "$REGION" \\',
                '  --log-group-name "$LOG_GROUP" \\',
                "  --query 'metricFilters[].{Name:filterName,Pattern:filterPattern,Metric:metricTransformations[0].metricName,Namespace:metricTransformations[0].metricNamespace,Value:metricTransformations[0].metricValue}' \\",
                "  --output table",
            ]),
            "step2": NONE,
            "kid": "ベルは、ノートの全部に反応するのではありません。決まった言葉を数える人（メトリクスフィルタ）がいて、その数が約束を超えると鳴ります。足す字は、その人が探している字そのものにします。",
            "history": "メトリクスフィルタは CloudWatch Logs と一緒に2014年からあります。公式の説明では、フィルタは作ったあとから入ってきたログだけを数えます。昔のログを後から数えることはしません。だから、すでに書いてある行を眺めてもベルは鳴らず、新しい1行を足す試験が必要になりました。一致は少なくとも1回は数に入りますが、まれに同じ行が2回数えられることもあります。",
            "safety": "describe-metric-filters は表示だけです。フィルタの作成、変更、削除はしません。",
            "before": "ロググループ名を書き換えます。アラームがどのメトリクスを見ているかは、P-05 の結果と突き合わせます。",
            "after": "filterPattern を、手順2で足す文字列にそのまま使います。JSON の形（{ $.level = \"ERROR\" } のような形）なら、平文の ERROR では一致しません。L-04 か、その形に合わせた1行を使います。",
            "limits": "ロググループの中のフィルタだけが見えます。別グループのフィルタは出ません。",
            "meaning": "filterPattern が探す言葉、metricNamespace と metricName がベルの見ている数値の名前です。P-05 のアラームと、この名前が同じかを見ます。",
            "why": "言葉が違う1行を足しても、ファイルは汚れ、ベルは鳴りません。先に探す言葉を見ます。",
        },
        {
            "id": "P-01",
            "group": "見るだけ",
            "order": "3",
            "name": "ログファイルの背表紙と厚みを見る",
            "touches": "いいえ",
            "step1": join([
                "# 読み取りだけ。ファイルは変更しない。",
                f"LOG_FILE='{PLACEHOLDER_FILE}'",
                "set -eu",
                'case "$LOG_FILE" in /*) ;; *) printf "%s\\n" "中止: 絶対パスだけを受け付けます。"; exit 2 ;; esac',
                'if [ -L "$LOG_FILE" ]; then printf "%s\\n" "これはシンボリックリンクです。本物のパスを使います。"; exit 2; fi',
                'if [ ! -f "$LOG_FILE" ]; then printf "%s\\n" "通常の既存ファイルではありません。"; exit 2; fi',
                'stat -c "inode=%i size=%s owner=%U group=%G mode=%a name=%n" "$LOG_FILE"',
                'ls -l -- "$LOG_FILE"',
            ]),
            "step2": NONE,
            "kid": "ノートを開いて書き始める前に、背表紙の整理番号と、今の厚みだけを見ます。整理番号は inode、厚みはバイト数です。あとでこの2つがどう変わったかで、別のノートにすり替わっていないか、ページが破られていないかを判断します。",
            "history": "inode は、UNIX が1970年代からファイルを見分けるために使っている番号です。名前が同じに見えても、番号が違えば別のファイルです。上書きで作り直すと、番号が変わることがあります。追記では、同じ番号のまま厚みだけが増えます。ls は UNIX 第1版（1971年）のころからある、名前と大きさを見る命令です。",
            "safety": "stat と ls は読むだけです。リダイレクト（ファイルへ流す記号）を使っていません。",
            "before": "パスの例文を、エージェントが実際に読んでいるファイルの絶対パスへ変えます。ワイルドカード（* や ?）は使いません。",
            "after": "inode と size をメモします。オーナーと mode も見ます。試験で権限や所有者は変えません。変えると、アプリやエージェントが読めなくなることがあります。",
            "limits": "GNU の stat -c を使います。macOS の stat とは書き方が違います。対象は Linux のサーバーです。",
            "meaning": "inode は背表紙の番号、size はバイトの厚み、mode はだれが読んでよいかの許可です。",
            "why": "書く前の番号と厚みがないと、あとで「減っていない」と言い切れません。",
        },
        {
            "id": "P-02",
            "group": "見るだけ",
            "order": "4",
            "name": "最後の1バイトが改行かを見る",
            "touches": "いいえ",
            "step1": join([
                "# 読み取りだけ。1バイトも足さない。",
                f"LOG_FILE='{PLACEHOLDER_FILE}'",
                "set -eu",
                'if [ ! -f "$LOG_FILE" ] || [ -L "$LOG_FILE" ]; then printf "%s\\n" "中止: 既存の通常ファイルではありません。"; exit 2; fi',
                'SIZE="$(stat -c "%s" "$LOG_FILE")"',
                'printf "%s\\n" "size=${SIZE}"',
                'if [ "$SIZE" -eq 0 ]; then printf "%s\\n" "空のファイルです。試験行は改行で終えます。"; exit 0; fi',
                'tail -c 1 "$LOG_FILE" | od -An -tx1',
                'printf "%s\\n" "0a なら改行です。0a でなければ、未完成の行が残っています。"',
            ]),
            "step2": NONE,
            "kid": "集配人（CloudWatch エージェント）は、行の終わりの印がないと、その行を手紙にして運びません。印は改行で、中身のバイトは 0a です。印がないノートに試験行を足すと、書きかけの行と試験行が1通の手紙になることがあります。",
            "history": "改行で行を分ける考えは、初期の UNIX のテキストから続いています。AWS のトラブルシュート記事（2026年5月4日更新）は、監視中のファイルが改行で終わっていないと、エージェントがそのファイルからログを送らない、と説明しています。エラーも警告も出ません。同じ記事は、ファイルのサイズが減ると Re-opening truncated file と記録し、先頭から読み直す、とも言っています。だから試験では、厚みを減らさず、足す行は必ず改行で終えます。",
            "safety": "tail -c 1 は最後の1バイトを読むだけです。od はそのバイトを16進数で見せます。ファイルへは書きません。",
            "before": "P-01 で見たのと同じパスを使います。",
            "after": "表示が 0a なら、このあとの追記へ進めます。0a でないときは、人がアプリの書きかけを確認するまで追記しません。ツール既定も、ここで止まります。",
            "limits": "od の空白の有無は実装で少し違います。0a という文字が見えれば改行です。",
            "meaning": "tail -c 1 は最後の1文字分、od -tx1 はそれを16進数で見せる命令です。",
            "why": "改行のない追記は、試験行が届かないか、前の行とくっついて届くかのどちらかになりやすいです。",
        },
        {
            "id": "R-02",
            "group": "安全ツール",
            "order": "5",
            "name": "bash の安全ツールを一時ファイルで自己検査する",
            "touches": "本番ログは触らない",
            "step1": join([
                "# 本番ログは指定しない。/tmp の中だけで検査する。",
                "TOOL='/ここをsafe_append.shの絶対パスに書き換える'",
                'case "$TOOL" in *ここを*) printf "%s\\n" "中止: ツールのパスを書き換えてください。"; exit 2 ;; esac',
                'bash "$TOOL" --self-test',
            ]),
            "step2": NONE,
            "kid": "本番のノートに触る前に、別の紙で「最後に足す」「最初の字は残る」「ないノートは作らない」を練習します。--self-test はその練習で、終わると練習用の紙だけを捨てます。",
            "history": "追記の記号 >> は、初期の UNIX シェルからあります。1つの > は中身を長さ0にしてから書くので、1979年の csh は noclobber を足しました。それでも >> の付け忘れ、tee の -a の付け忘れ、自分自身へ cat して無限に膨らませる事故は残りました。このスクリプトは、その事故の型を引数として受け取れないようにしてあります。",
            "safety": "自己検査は /tmp/cw-alarm-self-test.* だけを作り、終わったらそのディレクトリだけを削除します。削除前に、パスがその形であることを確認します。本番の LOG_FILE は引数に取れません。",
            "before": "サーバーに safe_append.sh を置き、TOOL のパスをその絶対パスにします。bash で実行します。",
            "after": "RESULT=SELF_TEST_OK を確認します。失敗したら本番ログへ進みません。",
            "limits": "GNU stat、od、bash がある Linux 向けです。Windows では Invoke-SafeLogAppend.ps1 の -SelfTest を使います。",
            "meaning": "--self-test は、本番パスを拒否し、一時ディレクトリの中でドライランと追記と完全一致の確認をします。",
            "why": "本番で初めて試すと、道具の不具合とアラームの不具合が区別できません。",
        },
        {
            "id": "R-01",
            "group": "安全ツール",
            "order": "5",
            "name": "Python の安全ツールを一時ファイルで自己検査する",
            "touches": "本番ログは触らない",
            "step1": join([
                "# 本番ログは指定しない。",
                "TOOL='/ここをsafe_append.pyの絶対パスに書き換える'",
                'case "$TOOL" in *ここを*) printf "%s\\n" "中止: ツールのパスを書き換えてください。"; exit 2 ;; esac',
                'python3 "$TOOL" --self-test',
            ]),
            "step2": NONE,
            "kid": "R-02 と同じ練習を、Python の道具でやります。この道具は、ログを開くとき「追記しかしない」開き方だけを使い、新しく作る旗と、短くする旗を付けません。",
            "history": "POSIX の write では、O_APPEND を付けると、書く直前に位置をファイルの終わりへ動かし、そのあいだにほかの変更を挟まない、と定められています。1つの > は、開くときに長さを0にします。Python のこの道具は、Linux では O_APPEND だけ、Windows では FILE_APPEND_DATA と OPEN_EXISTING だけを使います。FILE_APPEND_DATA は、途中の位置へ書き戻す権利を最初から持たない開き方です。",
            "safety": "自己検査は tempfile のディレクトリだけで行い、終わるとそのディレクトリだけを削除します。O_CREAT はログには使いません。ロック用の空ファイルを一時領域に作ることはあります。それはログではありません。",
            "before": "python3 があり、TOOL が safe_append.py の絶対パスであることを確認します。",
            "after": "RESULT=SELF_TEST_OK を見ます。",
            "limits": "本番ログへの実行は、このセルではしません。追記は G-05 または R-01 の手順2を別セルで行います。",
            "meaning": "--self-test は引数のパスを受け取りません。受け取ったら拒否します。",
            "why": "Windows でも Linux でも、同じ「作らない、短くしない、先頭を残す」約束を検査できます。",
        },
        {
            "id": "P-03",
            "group": "安全ツール",
            "order": "6",
            "name": "本番ログへ書く前のドライラン",
            "touches": "いいえ",
            "step1": join([
                "# --confirm-append が無いので、検査だけして何も書かない。",
                "TOOL='/ここをsafe_append.shの絶対パスに書き換える'",
                f"LOG_FILE='{PLACEHOLDER_FILE}'",
                f"ALARM_MARKER='{PLACEHOLDER_MARKER}'",
                f"OPERATOR='{PLACEHOLDER_OPERATOR}'",
                'bash "$TOOL" \\',
                '  --file "$LOG_FILE" \\',
                '  --marker "$ALARM_MARKER" \\',
                '  --operator "$OPERATOR"',
            ]),
            "step2": join([
                "# 手順1の表示を読んだあとに、このセルだけを実行する。",
                "TOOL='/ここをsafe_append.shの絶対パスに書き換える'",
                f"LOG_FILE='{PLACEHOLDER_FILE}'",
                f"ALARM_MARKER='{PLACEHOLDER_MARKER}'",
                f"OPERATOR='{PLACEHOLDER_OPERATOR}'",
                'bash "$TOOL" \\',
                '  --file "$LOG_FILE" \\',
                '  --marker "$ALARM_MARKER" \\',
                '  --operator "$OPERATOR" \\',
                "  --confirm-append",
            ]),
            "kid": "下書きを声に出して読んでから、ノートの最後に清書します。声に出すのが手順1、清書が手順2です。手順2には --confirm-append という、書くことを明示する言葉が必要です。",
            "history": "ドライランという言葉は、本番の装置を動かさずに手順だけを確認する習慣から来ています。ログ試験でこれが必要になったのは、シェルは Enter を押した瞬間にリダイレクトを実行し、確認の問いを出す暇がないからです。スクリプトの途中で入力を待つと、貼り付けの残りがその入力に吸い込まれ、意図しない続きが走ることがあります。だから確認は、別のセルをあとからコピーする形にしています。",
            "safety": "手順1に --confirm-append はありません。例文の「ここを」が残っていると、ツールは拒否します。手順2も、存在しないファイルは作らず、シンボリックリンクは拒否し、末尾が改行でなければ拒否します。",
            "before": "R-02 の自己検査が成功していること、P-01 と P-02 の結果、P-04 の探す言葉、P-05 の通知先を確認します。",
            "after": "手順1は RESULT=DRY_RUN です。手順2は RESULT=APPENDED、head_unchanged=yes、payload_found=yes です。size が減っていたら、そこで止めて人が見ます。ツールは元に戻そうとしません。戻す操作が、さらに消す操作になり得るからです。",
            "limits": "手順1と手順2では id が別になります。手順1に出た行そのものではなく、同じ形の新しい行が足されます。",
            "meaning": "バックスラッシュで、1つのコマンドを引数ごとに改行しています。--file は既存ログ、--marker はフィルタが探す言葉、--operator はだれが試験したかです。",
            "why": "フラグが無いときの既定を「書かない」にすると、引数の付け忘れが追記事故になりません。",
        },
        {
            "id": "L-02",
            "group": "短い追記",
            "order": "7",
            "name": "変数を分けて見てから、printf で1行足す",
            "touches": "手順2だけが末尾へ足す",
            "step1": join(["# 手順1。ファイルは変更しない。"] + guard(preview_tail)),
            "step2": join(["# 手順2。手順1を読んだあとに、このセルだけを実行する。"] + guard(append_tail)),
            "kid": "足す文を、ノートとは別の場所で組み立てて、画面に出します。よければ、同じ文をノートの最後へ足します。printf は、渡した字をそのまま出し、最後に改行を1つ付けます。",
            "history": "echo は最初期のシェルからあります。ただし -n やバックスラッシュの扱いが、System V と BSD で違いました。POSIX.2（1992年）は、その差を避けるために printf を標準の道具にしました。書式 '%s\\n' は、中身を解釈せずに出し、改行を1つ足します。>> は終わりへ足す開き方、1つの > は一度空にする開き方です。このセルは >> だけを使います。",
            "safety": "絶対パス、ワイルドカード拒否、/proc /sys /dev の拒否、シンボリックリンク拒否、ファイルが無いときの作成拒否、末尾改行の確認、書いたあとの inode とサイズの確認が入っています。noclobber も入れますが、これは > の事故を止める補助で、>> の代わりにはなりません。",
            "before": "P-04 の言葉を ALARM_MARKER にします。通知先へ試験が伝わっていることを確認します。",
            "after": "size_after が size_before 以上であること、inode が同じこと、画面の id をメモすることを確認します。そのあと A-04 と、もう一度 P-05 を実行します。",
            "limits": "1行です。改行を含む長文は G-01 以降です。JSON フィルタには L-04 を使います。アプリが同時に書くと、増分が試験行より大きくなります。それは失敗ではなく、本番ログが生きている印です。",
            "meaning": "set -o noclobber は、既存ファイルへの1つの > を拒否します。LINE= は足す文、printf '%s\\n' はその文と改行、>> は末尾への追記です。",
            "why": "試験の第一歩は、フィルタに一致する短い1行です。短いほど、エージェントの区切りや1MBの上限に触れません。",
        },
        {
            "id": "L-01",
            "group": "短い追記",
            "order": "任意",
            "name": "いちばん短い printf 追記",
            "touches": "手順2だけが末尾へ足す",
            "step1": join([
                "# 短い形。それでも、書く前の検査は残してある。ファイルは変更しない。",
                f"LOG_FILE='{PLACEHOLDER_FILE}'",
                f"ALARM_MARKER='{PLACEHOLDER_MARKER}'",
                "set -eu",
                "set -o noclobber",
                'case "$LOG_FILE" in /*) ;; *) printf "%s\\n" "中止: 絶対パスだけです。"; exit 2 ;; esac',
                'if [ -L "$LOG_FILE" ] || [ ! -f "$LOG_FILE" ]; then printf "%s\\n" "中止: 既存の通常ファイルではありません。"; exit 2; fi',
                'printf "%s\\n" "size=$(stat -c %s "$LOG_FILE") inode=$(stat -c %i "$LOG_FILE")"',
                'printf "%s\\n" "CWALARM-TEST marker=${ALARM_MARKER}"',
                'printf "%s\\n" "このセルではファイルは変わりません。"',
            ]),
            "step2": join([
                "# 手順2。検査をもう一度してから、1行だけ足す。",
                f"LOG_FILE='{PLACEHOLDER_FILE}'",
                f"ALARM_MARKER='{PLACEHOLDER_MARKER}'",
                "set -eu",
                "set -o noclobber",
                'case "$LOG_FILE" in /*) ;; *) printf "%s\\n" "中止: 絶対パスだけです。"; exit 2 ;; esac',
                'if [ -L "$LOG_FILE" ] || [ ! -f "$LOG_FILE" ]; then printf "%s\\n" "中止: 既存の通常ファイルではありません。作りません。"; exit 2; fi',
                'SIZE="$(stat -c %s "$LOG_FILE")"',
                'INODE="$(stat -c %i "$LOG_FILE")"',
                'printf "%s\\n" "CWALARM-TEST marker=${ALARM_MARKER}" >> "$LOG_FILE"',
                'AFTER="$(stat -c %s "$LOG_FILE")"',
                'if [ "$(stat -c %i "$LOG_FILE")" != "$INODE" ] || [ "$AFTER" -lt "$SIZE" ]; then printf "%s\\n" "検証失敗。戻す操作はしません。"; exit 3; fi',
                'printf "%s\\n" "size_before=${SIZE} size_after=${AFTER}"',
            ]),
            "kid": "L-02 から、説明用の情報を減らした形です。それでも、ノートが本当にあるか、リンクでないか、最後に足したあと厚みが減っていないかを見ます。",
            "history": "短い命令が必要になったのは、長い安全手順を読む前に、>> と > の違いだけを見せたい場面があるからです。短くしても、作らないことと、短くしないことの検査は残しています。1970年代からある >> を、確認なしの1行にはしていません。",
            "safety": "手順1に >> はありません。手順2の >> は、存在確認のあとです。inode が変わるか、サイズが減ったら、そこで終了し、修復のための削除や切り詰めはしません。",
            "before": "普段は L-02 か P-03 を使います。この短い形は、違いを理解するためのものです。",
            "after": "size_before と size_after を見ます。",
            "limits": "操作者や試験IDが行に入りません。あとから探すなら L-02 の方が簡単です。",
            "meaning": "printf の '%s\\n' は字と改行、>> は追記です。stat は厚みと inode を見ます。",
            "why": "短い形がないと、安全手順が黒箱に見えます。中身を減らした形も、同じ約束を守ります。",
        },
        {
            "id": "L-03",
            "group": "短い追記",
            "order": "任意",
            "name": "tee -a で画面とファイルの両方へ足す",
            "touches": "手順2だけが末尾へ足す",
            "step1": join(["# 手順1。tee はまだ使いません。"] + guard(preview_tail)),
            "step2": join(["# 手順2。tee には必ず -a を付ける。"] + guard([
                'printf "%s\\n" "$LINE" | tee -a -- "$LOG_FILE"',
            ] + verify_tail("tee -a で追記しました。"))),
            "kid": "T字の管のように、同じ1行を画面とノートの両方へ流します。-a は append、つまり最後に足す、という意味です。-a を忘れると、tee はノートを空にしてから書き始めます。",
            "history": "tee は UNIX 第1版（1971年）のマニュアルにあり、名前は配管のT字継手です。画面を見ながらファイルにも残すために作られました。POSIX は、-a が無い tee はファイルを書き直し、-a があるときは O_APPEND と同じ動きにすることを求めています。昔の実装には、終わりへ移動するだけで O_APPEND ではないものもあり、その差で同時に書いた行が重なることがありました。",
            "safety": "-a と -- を両方付けています。-- は、ファイル名が - で始まってもオプションと誤解されないようにする印です。手順1では tee を起動しません。",
            "before": "コマンドの中に tee -a があることを、実行前に目で見ます。-a が無ければ実行しません。",
            "after": "画面に出た行と、size の増加を確認します。",
            "limits": "tee はパイプの右側です。左側の printf が失敗しても、空の追記にはなりにくい形ですが、ファイル名を間違えると、その間違えた既存ファイルの末尾へ足します。だから絶対パスの検査を先に置いています。",
            "meaning": "printf が行を作り、パイプが tee へ渡し、tee -a が画面とファイルの末尾へコピーします。",
            "why": "書いた行を、ファイルを開き直さずに画面で見たいときに使います。",
        },
        {
            "id": "L-04",
            "group": "短い追記",
            "order": "任意",
            "name": "JSONフィルタ向けに、JSONを1行だけ足す",
            "touches": "手順2だけが末尾へ足す",
            "step1": join(["# 手順1。JSONの形を画面に出すだけ。"] + guard([
                'case "$ALARM_MARKER$OPERATOR" in',
                '  *"\\""*|*"\\\\"*|*$\'\\n\'*) printf "%s\\n" "中止: 引用符やバックスラッシュは、この短い形では扱えません。G-05 の --json を使います。"; exit 2 ;;',
                "esac",
                'LINE="{\\"time\\":\\"${NOW}\\",\\"level\\":\\"ERROR\\",\\"cwAlarmTest\\":true,\\"id\\":\\"${TEST_ID}\\",\\"operator\\":\\"${OPERATOR}\\",\\"message\\":\\"${ALARM_MARKER}\\"}"',
                'printf "%s\\n" "$LINE"',
                'printf "%s\\n" "このセルではファイルは変わりません。level という名前がフィルタと違うなら、合わせてから手順2へ進みます。"',
            ])),
            "step2": join(["# 手順2。1行のJSONだけを足す。"] + guard([
                'case "$ALARM_MARKER$OPERATOR" in',
                '  *"\\""*|*"\\\\"*|*$\'\\n\'*) printf "%s\\n" "中止: 引用符やバックスラッシュは G-05 の --json を使います。"; exit 2 ;;',
                "esac",
                'LINE="{\\"time\\":\\"${NOW}\\",\\"level\\":\\"ERROR\\",\\"cwAlarmTest\\":true,\\"id\\":\\"${TEST_ID}\\",\\"operator\\":\\"${OPERATOR}\\",\\"message\\":\\"${ALARM_MARKER}\\"}"',
                'printf "%s\\n" "$LINE" >> "$LOG_FILE"',
            ] + verify_tail("JSONを1行追記しました。"))),
            "kid": "アプリのノートが、ことばではなく、名前と値の組（JSON）で書かれているとき、試験も同じ形の1行にします。行の途中で改行すると、エージェントは別々の手紙に分けてしまうことがあります。",
            "history": "JSON は2000年代に広まった、データの書き方です。CloudWatch のメトリクスフィルタは、{ $.level = \"ERROR\" } のように、JSONの中の名前を条件にできます。この形は、平文の ERROR とは別の探し方です。2014年のログ監視が、ただの文字列から、構造のある1行へ広がったために、試験行も1行のJSONである必要が出てきました。",
            "safety": "引用符やバックスラッシュが混ざると、この手作業のJSONは壊れます。壊れた行を足す前に、case で拒否します。正しくエスケープするときは、Python の --json を使います。ファイルへの記号は >> だけです。",
            "before": "P-04 の filterPattern を見ます。$.level でなければ、LINE の level という名前を、現場の名前に変えます。変えたあとも1行のままにします。",
            "after": "足した行が1行であること、先頭が { で最後が } であることを、ログの末尾で確認します。",
            "limits": "この短い形は、値に引用符が無いときだけです。複数行のJSONは、改行で複数イベントになります。1イベントにしたい長文は A-03 です。",
            "meaning": "LINE の中の \\ は、シェルの引用符の中で二重引用符を1つの文字として残すための印です。ログに書かれるのは、バックスラッシュではなく二重引用符です。",
            "why": "JSONフィルタのアラームを、平文の試験行で試すと、届いているのに一致しない、という勘違いが起きます。",
        },
    ]
    from more_commands import extra_commands

    items.extend(extra_commands())
    return items


FORBIDDEN = (
    "delete-log-group",
    "delete-log-stream",
    "Clear-Content",
    "Set-Content",
    "Remove-Item",
    "TRUNCATE_EXISTING",
    "FileMode]::Create",
    "FileMode]::Truncate",
    "sed -i",
    "sponge",
    "chattr",
    "logrotate",
    "--no-deletion-protection-enabled",
    "--sequence-token",
    "os.remove",
)


def assert_commands_safe(items: list[dict]) -> None:
    ids = [item["id"] for item in items]
    if len(ids) != len(set(ids)):
        raise SystemExit("コマンドIDが重複しています。")
    for item in items:
        for key in ("step1", "step2"):
            text = item[key]
            for line in text.splitlines():
                if line.strip().startswith("#"):
                    continue
                for bad in FORBIDDEN:
                    if bad in line:
                        raise SystemExit(f"{item['id']} {key} に禁止語があります: {bad}: {line}")
                if "tee " in line and "tee -a" not in line:
                    raise SystemExit(f"{item['id']} の tee に -a がありません: {line}")
                if "rm " in line:
                    if "rm -rf" in line or "/tmp/cw-alarm-test-draft.txt" not in text:
                        raise SystemExit(f"{item['id']} の削除が下書き限定ではありません: {line}")
                stripped = line.replace(">>", "")
                if ">" in stripped and ("LOG_FILE" in stripped or "$LogFile" in stripped):
                    raise SystemExit(f"{item['id']} にログへの上書きがあります: {line}")


def build() -> None:
    from openpyxl import load_workbook
    from workbook_pages import (
        build_accidents,
        build_check,
        build_detail,
        build_intro,
        build_list,
        build_words,
    )

    items = commands()
    assert_commands_safe(items)
    wb = Workbook()
    wb.properties.title = "CloudWatch Alarm 安全ログ追記コマンド集"
    wb.properties.creator = "Alarm Insert Commands"
    wb.properties.subject = "既存ログを消さずに検知文字列を追記する"
    wb.properties.description = "手順1は書き込まない。手順2だけが追記する。Meiryo UI、モノトーン。"
    build_intro(wb)
    build_list(wb, items)
    build_detail(wb, items)
    build_check(wb)
    build_accidents(wb)
    build_words(wb)
    wb.active = 0
    wb.save(OUT)
    from openpyxl.cell.cell import MergedCell

    saved = load_workbook(OUT)
    for ws in saved.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell, MergedCell) or cell.value is None:
                    continue
                if cell.font.name != "Meiryo UI":
                    raise SystemExit(f"フォントが Meiryo UI ではありません: {ws.title} {cell.coordinate} {cell.font.name}")
                if not cell.alignment.wrap_text:
                    raise SystemExit(f"折り返しがありません: {ws.title} {cell.coordinate}")
                color = cell.font.color.rgb if cell.font.color is not None and cell.font.color.rgb else "FF1A1A1A"
                if isinstance(color, str) and len(color) == 8:
                    red, green, blue = color[2:4], color[4:6], color[6:8]
                    if not (red == green == blue):
                        raise SystemExit(f"文字色がモノトーンではありません: {ws.title} {cell.coordinate} {color}")
    print(f"commands={len(items)}")
    print(f"sheets={','.join(saved.sheetnames)}")
    print(OUT)


if __name__ == "__main__":
    build()
