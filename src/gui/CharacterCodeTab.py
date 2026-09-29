import difflib
import json
import re
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlparse
from urllib.request import urlopen

from PySide6.QtCore import QEvent, QPointF, Qt, QSize, QUrl, Signal
from PySide6.QtGui import (
    QColor, QDesktopServices, QFontMetricsF, QPainter, QPixmap, QTextCursor, QTextFormat, QTextLayout,
)
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QAbstractItemView, QHBoxLayout, QHeaderView, QLabel,
    QListWidgetItem, QSplitter, QStyle, QStyleOptionViewItem, QTableWidgetItem, QTextEdit, QVBoxLayout,
    QWidget,
)
from qfluentwidgets.common.style_sheet import setCustomStyleSheet
from qfluentwidgets import (
    BodyLabel, CaptionLabel, ComboBox, FluentIcon, LineEdit, ListItemDelegate, ListWidget, MessageBox, MessageBoxBase,
    PlainTextEdit, PrimaryPushButton, PushButton, SearchLineEdit, SubtitleLabel, TableWidget, TextEdit,
    isDarkTheme, qconfig,
)

from ok import Logger
from ok.gui.tasks.EditTaskTab import CodeEditor
from ok.gui.tasks.PythonHighlighter import PythonHighlighter
from ok.gui.util.app import show_info_bar
from ok.gui.widget.CustomTab import CustomTab
from src.char.CharFactory import apply_team_char_classes, char_dict
from src.char.CustomCharLoader import (
    TEAM_CODE_MODE_BUILTIN, TEAM_CODE_MODE_IMPORT, TEAM_CODE_STATE_NONE,
    changed_import_members, create_custom_team, delete_custom_team, drifted_team_members,
    export_custom_team, get_english_char_name,
    import_custom_team, inspect_team_archive, list_custom_teams, normalize_custom_teams,
    normalize_team, read_builtin_char_code, read_team_char_code,
    save_team_code_as_import, switch_all_teams_code_mode, switch_team_code_mode, team_code_state,
)

BASE_CHAR_URL = "https://raw.githubusercontent.com/ok-oldking/ok-wuthering-waves/refs/heads/master/src/char/BaseChar.py"
UPLOAD_TEAM_URL = "https://github.com/ok-oldking/ok-ww-char-code"
WORKSHOP_TEAMS_ALL_URL = "https://okwwcharcode.ok-script.com/teams.json"
WORKSHOP_TEAM_URL = "https://okwwcharcode.ok-script.com/teams/{slug}.json"
WORKSHOP_ARCHIVE_HOSTS = {"okwwcharcode.ok-script.com", "raw.githubusercontent.com"}
logger = Logger.get_logger(__name__)

# The team list marks each team with a haloed dot, and both switch buttons wear the
# color of the state they switch to, so the buttons double as the legend for the
# dots. Switching always moves a whole team, so a team is blue exactly when its
# members run imported code; a never imported team runs built in code and looks alike.
TEAM_CODE_STATE_COLORS = {
    # state: (light theme, dark theme)
    TEAM_CODE_MODE_IMPORT: ("#0F6CBD", "#479EF5"),
    TEAM_CODE_MODE_BUILTIN: ("#D13438", "#F1707B"),
}
STATE_DOT_SIZE = 14
STATE_DOT_CORE_SIZE = 8
STATE_DOT_HALO_ALPHA = 60
TEAM_CODE_STATE_ROLE = Qt.UserRole + 1


def _state_colors(state):
    return TEAM_CODE_STATE_COLORS[TEAM_CODE_MODE_IMPORT if state == TEAM_CODE_MODE_IMPORT else TEAM_CODE_MODE_BUILTIN]


def team_state_color(state):
    """Return the color of `state` in the current theme."""
    light, dark = _state_colors(state)
    return QColor(dark if isDarkTheme() else light)


def _text_middle_y(option, text_rect):
    """Y of the middle of a full height glyph, laid out the way QCommonStyle lays out a
    single line of item text: the line box is centered with integer math."""
    layout = QTextLayout(option.text, option.font)
    layout.beginLayout()
    line = layout.createLine()
    layout.endLayout()
    top = text_rect.y() + int((text_rect.height() - int(line.height())) / 2)
    glyph = QFontMetricsF(option.font).tightBoundingRect("中")
    return top + line.ascent() + glyph.center().y()


class TeamListDelegate(ListItemDelegate):
    """Paints the code state dot of a team level with the middle of its name.

    An icon would be centered on the row, while the text lands up to two pixels lower
    depending on the font and the scale factor, so the dot is painted here instead.
    """

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        if index.data(TEAM_CODE_STATE_ROLE) is not None:
            # keep the room of an icon in front of the name, paint() fills it
            option.features |= QStyleOptionViewItem.HasDecoration
            option.decorationSize = QSize(STATE_DOT_SIZE, STATE_DOT_SIZE)

    def paint(self, painter, option, index):
        # the base paint moves option.rect in by the margin, so keep an untouched copy
        opt = QStyleOptionViewItem(option)
        super().paint(painter, option, index)
        state = index.data(TEAM_CODE_STATE_ROLE)
        if state is None:
            return
        self.initStyleOption(opt, index)
        opt.rect.adjust(0, self.margin, 0, -self.margin)
        style = opt.widget.style() if opt.widget else QApplication.style()
        icon_rect = style.subElementRect(QStyle.SE_ItemViewItemDecoration, opt, opt.widget)
        text_rect = style.subElementRect(QStyle.SE_ItemViewItemText, opt, opt.widget)
        # snap the core onto device pixels so it stays crisp at any scale factor
        ratio = painter.device().devicePixelRatioF()
        radius = STATE_DOT_CORE_SIZE / 2
        x = round((icon_rect.x() + icon_rect.width() / 2 - radius) * ratio) / ratio + radius
        y = round((_text_middle_y(opt, text_rect) - radius) * ratio) / ratio + radius
        color = team_state_color(state)
        halo = QColor(color)
        halo.setAlpha(STATE_DOT_HALO_ALPHA)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(QPointF(x, y), STATE_DOT_SIZE / 2, STATE_DOT_SIZE / 2)
        painter.setBrush(color)
        painter.drawEllipse(QPointF(x, y), radius, radius)
        painter.restore()


def team_state_tooltip(state):
    if state == TEAM_CODE_MODE_IMPORT:
        return translate_ui("Imported code is in effect")
    if state == TEAM_CODE_MODE_BUILTIN:
        return translate_ui("Built in code is in effect")
    return translate_ui("Never imported code, skipped by Switch All")


def translate_ui(message):
    from ok import og
    locale_str = ""
    if og.app:
        # Check current language/locale
        if hasattr(og.app, "locale") and og.app.locale:
            locale_str = og.app.locale.name() if hasattr(og.app.locale, "name") else str(og.app.locale)
        elif hasattr(og.app, "config") and og.app.config:
            locale_str = str(og.app.config.get("locale", "") or og.app.config.get("language", ""))

        translated = og.app.tr(message)
        if translated and translated != message:
            return translated

    # Fallback dictionaries for all officially supported locales in ok-ww:
    # zh_CN (Simplified Chinese), zh_TW (Traditional Chinese), ja_JP (Japanese), ko_KR (Korean), es_ES (Spanish)
    _locale_fallbacks = {
        "zh_CN": {
            "Search by team, character, author or description...": "搜索队伍、角色、作者或描述...",
            "All Characters": "全部角色",
            "Character:": "角色:",
            "{count} configurations": "{count} 个配置",
            "No shared code matches the search criteria.": "未找到符合搜索条件的配置。",
            "Team Workshop": "队伍创意工坊",
            "{team_name} - Team Workshop": "{team_name} - 队伍工坊",
            "Configuration Details": "配置详情",
            "Team": "队伍",
            "Description": "描述",
            "Author": "作者",
            "Version": "版本",
            "Modified": "修改时间",
            "Action": "操作",
            "Import": "导入",
            "Close": "关闭",
            "Switch to Built In Code": "切换为内置代码",
            "Switch to Imported Code": "切换为导入代码",
            "Switch Character Code": "切换角色代码",
            "Switch the whole team to built in code?": "将整个队伍切换为内置代码？",
            "Switch the whole team to imported code?": "将整个队伍切换为导入代码？",
            "Switch": "切换",
            "Switched to {target}.": "已切换为{target}。",
            "Switched to {target} and reloaded for the matching team.": "已切换为{target}，并已为匹配的队伍重新加载。",
            "built in code": "内置代码",
            "imported code": "导入代码",
            "Save and Switch": "保存并切换",
            "Discard and Switch": "不保存并切换",
            "Save the current character code changes before switching?": "切换前是否保存当前角色代码的更改？",
            "Switch All to Built In Code": "切换全部队伍角色为内置代码",
            "Switch All to Imported Code": "切换全部队伍角色为导入代码",
            "Switch All Team Code": "切换所有队伍代码",
            "Switch all teams to built in code?": "将所有队伍切换为内置代码？",
            "Switch all teams to imported code?": "将所有队伍切换为导入代码？",
            "No team has imported code to switch.": "没有已导入代码的队伍可切换。",
            "Switched {count} teams to {target}.": "已将 {count} 个队伍切换为{target}。",
            "Skipped {count} teams that never imported code.": "已跳过 {count} 个未导入代码的队伍。",
            "Failed {count} teams.": "{count} 个队伍切换失败。",
            "Switch every team between imported and built in code": "在所有队伍的导入代码与内置代码之间一键切换",
            "Imported code is in effect": "生效代码：导入代码",
            "Built in code is in effect": "生效代码：内置代码",
            "Never imported code, skipped by Switch All": "未导入过代码，切换全部时会跳过",
            "Reset this character to built in code for this team?": "将此角色在此队伍中重置为内置代码？",
            "The whole team's current code is now its imported code.": "整个队伍的当前代码已成为导入代码。",
            "Replace Imported Code": "替换导入代码",
            "This team runs built in code. Saving makes the whole team's current code its imported code and replaces the imported code of: {names}": "该队伍当前使用内置代码。保存后，整个队伍的当前代码将成为导入代码，并替换以下角色的导入代码：{names}",
            "The current code of {names} is neither the built in nor the imported code of this team and is lost when switching.": "{names} 的当前代码既不是该队伍的内置代码，也不是导入代码，切换后将丢失。",
            "Keep as Imported Code and Switch": "保存为导入代码并切换",
            "Skipped {count} teams whose current code is not kept as imported code, switch them one by one.": "已跳过 {count} 个当前代码未保存为导入代码的队伍，请逐个切换。",
            "Partially Completed": "部分完成",
        },
        "zh_TW": {
            "Search by team, character, author or description...": "搜尋隊伍、角色、作者或說明...",
            "All Characters": "全部角色",
            "Character:": "角色:",
            "{count} configurations": "{count} 個設定",
            "No shared code matches the search criteria.": "未找到符合搜尋條件的設定。",
            "Team Workshop": "隊伍工作坊",
            "{team_name} - Team Workshop": "{team_name} - 隊伍工作坊",
            "Configuration Details": "設定詳情",
            "Team": "隊伍",
            "Description": "說明",
            "Author": "作者",
            "Version": "版本",
            "Modified": "修改時間",
            "Action": "操作",
            "Import": "匯入",
            "Close": "關閉",
            "Switch to Built In Code": "切換為內建程式碼",
            "Switch to Imported Code": "切換為匯入程式碼",
            "Switch Character Code": "切換角色程式碼",
            "Switch the whole team to built in code?": "將整個隊伍切換為內建程式碼？",
            "Switch the whole team to imported code?": "將整個隊伍切換為匯入程式碼？",
            "Switch": "切換",
            "Switched to {target}.": "已切換為{target}。",
            "Switched to {target} and reloaded for the matching team.": "已切換為{target}，並已為相符的隊伍重新載入。",
            "built in code": "內建程式碼",
            "imported code": "匯入程式碼",
            "Save and Switch": "儲存並切換",
            "Discard and Switch": "不儲存並切換",
            "Save the current character code changes before switching?": "切換前是否儲存目前角色程式碼的變更？",
            "Switch All to Built In Code": "切換全部隊伍角色為內建程式碼",
            "Switch All to Imported Code": "切換全部隊伍角色為匯入程式碼",
            "Switch All Team Code": "切換所有隊伍程式碼",
            "Switch all teams to built in code?": "將所有隊伍切換為內建程式碼？",
            "Switch all teams to imported code?": "將所有隊伍切換為匯入程式碼？",
            "No team has imported code to switch.": "沒有已匯入程式碼的隊伍可切換。",
            "Switched {count} teams to {target}.": "已將 {count} 個隊伍切換為{target}。",
            "Skipped {count} teams that never imported code.": "已跳過 {count} 個未匯入程式碼的隊伍。",
            "Failed {count} teams.": "{count} 個隊伍切換失敗。",
            "Switch every team between imported and built in code": "在所有隊伍的匯入程式碼與內建程式碼之間一鍵切換",
            "Imported code is in effect": "生效程式碼：匯入程式碼",
            "Built in code is in effect": "生效程式碼：內建程式碼",
            "Never imported code, skipped by Switch All": "未匯入過程式碼，切換全部時會跳過",
            "Reset this character to built in code for this team?": "將此角色在此隊伍中重設為內建程式碼？",
            "The whole team's current code is now its imported code.": "整個隊伍的目前程式碼已成為匯入程式碼。",
            "Replace Imported Code": "取代匯入程式碼",
            "This team runs built in code. Saving makes the whole team's current code its imported code and replaces the imported code of: {names}": "該隊伍目前使用內建程式碼。儲存後，整個隊伍的目前程式碼將成為匯入程式碼，並取代以下角色的匯入程式碼：{names}",
            "The current code of {names} is neither the built in nor the imported code of this team and is lost when switching.": "{names} 的目前程式碼既不是該隊伍的內建程式碼，也不是匯入程式碼，切換後將遺失。",
            "Keep as Imported Code and Switch": "儲存為匯入程式碼並切換",
            "Skipped {count} teams whose current code is not kept as imported code, switch them one by one.": "已跳過 {count} 個目前程式碼未儲存為匯入程式碼的隊伍，請逐一切換。",
            "Partially Completed": "部分完成",
        },
        "ja_JP": {
            "Search by team, character, author or description...": "チーム、キャラクター、作者、説明を検索...",
            "All Characters": "すべてのキャラクター",
            "Character:": "キャラクター:",
            "{count} configurations": "{count} 件の構成",
            "No shared code matches the search criteria.": "検索条件に一致する共有コードが見つかりません。",
            "Team Workshop": "チームワークショップ",
            "{team_name} - Team Workshop": "{team_name} - チームワークショップ",
            "Configuration Details": "構成の詳細",
            "Team": "チーム",
            "Description": "説明",
            "Author": "作者",
            "Version": "バージョン",
            "Modified": "更新日時",
            "Action": "操作",
            "Import": "インポート",
            "Close": "閉じる",
            "Switch to Built In Code": "組み込みコードに切り替え",
            "Switch to Imported Code": "インポートしたコードに切り替え",
            "Switch Character Code": "キャラクターコードの切り替え",
            "Switch the whole team to built in code?": "チーム全体を組み込みコードに切り替えますか？",
            "Switch the whole team to imported code?": "チーム全体をインポートしたコードに切り替えますか？",
            "Switch": "切り替え",
            "Switched to {target}.": "{target}に切り替えました。",
            "Switched to {target} and reloaded for the matching team.": "{target}に切り替え、該当チーム向けに再読み込みしました。",
            "built in code": "組み込みコード",
            "imported code": "インポートしたコード",
            "Save and Switch": "保存して切り替え",
            "Discard and Switch": "保存せずに切り替え",
            "Save the current character code changes before switching?": "切り替える前に現在のキャラクターコードの変更を保存しますか？",
            "Switch All to Built In Code": "すべてを組み込みコードに切り替え",
            "Switch All to Imported Code": "すべてをインポートしたコードに切り替え",
            "Switch All Team Code": "すべてのチームのコードを切り替え",
            "Switch all teams to built in code?": "すべてのチームを組み込みコードに切り替えますか？",
            "Switch all teams to imported code?": "すべてのチームをインポートしたコードに切り替えますか？",
            "No team has imported code to switch.": "インポートしたコードを持つチームがありません。",
            "Switched {count} teams to {target}.": "{count} 個のチームを{target}に切り替えました。",
            "Skipped {count} teams that never imported code.": "コードをインポートしていない {count} 個のチームをスキップしました。",
            "Failed {count} teams.": "{count} 個のチームの切り替えに失敗しました。",
            "Switch every team between imported and built in code": "すべてのチームのインポートコードと組み込みコードを一括で切り替えます",
            "Imported code is in effect": "有効なコード：インポートしたコード",
            "Built in code is in effect": "有効なコード：組み込みコード",
            "Never imported code, skipped by Switch All": "コードをインポートしていないため、一括切り替えではスキップされます",
            "Reset this character to built in code for this team?": "このキャラクターをこのチームの内蔵コードにリセットしますか？",
            "The whole team's current code is now its imported code.": "チーム全体の現在のコードがインポートしたコードになりました。",
            "Replace Imported Code": "インポートしたコードを置き換え",
            "This team runs built in code. Saving makes the whole team's current code its imported code and replaces the imported code of: {names}": "このチームは組み込みコードで動作しています。保存すると、チーム全体の現在のコードがインポートしたコードになり、次のキャラクターのインポートしたコードが置き換えられます：{names}",
            "The current code of {names} is neither the built in nor the imported code of this team and is lost when switching.": "{names} の現在のコードは、このチームの組み込みコードでもインポートしたコードでもないため、切り替えると失われます。",
            "Keep as Imported Code and Switch": "インポートしたコードとして保存して切り替え",
            "Skipped {count} teams whose current code is not kept as imported code, switch them one by one.": "現在のコードがインポートしたコードとして保存されていない {count} 個のチームをスキップしました。個別に切り替えてください。",
            "Partially Completed": "一部完了",
        },
        "ko_KR": {
            "Search by team, character, author or description...": "파티, 캐릭터, 제작자 또는 설명 검색...",
            "All Characters": "모든 캐릭터",
            "Character:": "캐릭터:",
            "{count} configurations": "{count}개 구성",
            "No shared code matches the search criteria.": "검색 조건과 일치하는 공유 코드가 없습니다.",
            "Team Workshop": "파티 창작마당",
            "{team_name} - Team Workshop": "{team_name} - 파티 창작마당",
            "Configuration Details": "구성 상세 정보",
            "Team": "파티",
            "Description": "설명",
            "Author": "제작자",
            "Version": "버전",
            "Modified": "수정일",
            "Action": "동작",
            "Import": "가져오기",
            "Close": "닫기",
            "Switch to Built In Code": "내장 코드로 전환",
            "Switch to Imported Code": "가져온 코드로 전환",
            "Switch Character Code": "캐릭터 코드 전환",
            "Switch the whole team to built in code?": "파티 전체를 내장 코드로 전환하시겠습니까?",
            "Switch the whole team to imported code?": "파티 전체를 가져온 코드로 전환하시겠습니까?",
            "Switch": "전환",
            "Switched to {target}.": "{target}(으)로 전환했습니다.",
            "Switched to {target} and reloaded for the matching team.": "{target}(으)로 전환하고 해당 파티에 다시 불러왔습니다.",
            "built in code": "내장 코드",
            "imported code": "가져온 코드",
            "Save and Switch": "저장 후 전환",
            "Discard and Switch": "저장하지 않고 전환",
            "Save the current character code changes before switching?": "전환하기 전에 현재 캐릭터 코드 변경 사항을 저장하시겠습니까?",
            "Switch All to Built In Code": "모두 내장 코드로 전환",
            "Switch All to Imported Code": "모두 가져온 코드로 전환",
            "Switch All Team Code": "모든 팀 코드 전환",
            "Switch all teams to built in code?": "모든 팀을 내장 코드로 전환하시겠습니까?",
            "Switch all teams to imported code?": "모든 팀을 가져온 코드로 전환하시겠습니까?",
            "No team has imported code to switch.": "가져온 코드가 있는 팀이 없습니다.",
            "Switched {count} teams to {target}.": "{count}개 팀을 {target}(으)로 전환했습니다.",
            "Skipped {count} teams that never imported code.": "코드를 가져오지 않은 {count}개 팀을 건너뛰었습니다.",
            "Failed {count} teams.": "{count}개 팀 전환에 실패했습니다.",
            "Switch every team between imported and built in code": "모든 팀의 가져온 코드와 내장 코드를 한 번에 전환합니다",
            "Imported code is in effect": "적용 중인 코드: 가져온 코드",
            "Built in code is in effect": "적용 중인 코드: 내장 코드",
            "Never imported code, skipped by Switch All": "코드를 가져온 적이 없어 전체 전환에서 건너뜁니다",
            "Reset this character to built in code for this team?": "이 캐릭터를 이 파티의 내장 코드로 초기화할까요?",
            "The whole team's current code is now its imported code.": "팀 전체의 현재 코드가 가져온 코드가 되었습니다.",
            "Replace Imported Code": "가져온 코드 교체",
            "This team runs built in code. Saving makes the whole team's current code its imported code and replaces the imported code of: {names}": "이 팀은 내장 코드를 사용 중입니다. 저장하면 팀 전체의 현재 코드가 가져온 코드가 되며, 다음 캐릭터의 가져온 코드를 교체합니다: {names}",
            "The current code of {names} is neither the built in nor the imported code of this team and is lost when switching.": "{names}의 현재 코드는 이 팀의 내장 코드도 가져온 코드도 아니므로 전환하면 사라집니다.",
            "Keep as Imported Code and Switch": "가져온 코드로 저장 후 전환",
            "Skipped {count} teams whose current code is not kept as imported code, switch them one by one.": "현재 코드가 가져온 코드로 저장되지 않은 {count}개 팀을 건너뛰었습니다. 하나씩 전환하세요.",
            "Partially Completed": "일부 완료",
        },
        "es_ES": {
            "Search by team, character, author or description...": "Buscar por equipo, personaje, autor o descripción...",
            "All Characters": "Todos los personajes",
            "Character:": "Personaje:",
            "{count} configurations": "{count} configuraciones",
            "No shared code matches the search criteria.": "No se encontraron códigos compartidos que coincidan.",
            "Team Workshop": "Taller de equipos",
            "{team_name} - Team Workshop": "{team_name} - Taller de equipos",
            "Configuration Details": "Detalles de configuración",
            "Team": "Equipo",
            "Description": "Descripción",
            "Author": "Autor",
            "Version": "Versión",
            "Modified": "Modificado",
            "Action": "Acción",
            "Import": "Importar",
            "Close": "Cerrar",
            "Switch to Built In Code": "Cambiar a código integrado",
            "Switch to Imported Code": "Cambiar a código importado",
            "Switch Character Code": "Cambiar código del personaje",
            "Switch the whole team to built in code?": "¿Cambiar todo el equipo al código integrado?",
            "Switch the whole team to imported code?": "¿Cambiar todo el equipo al código importado?",
            "Switch": "Cambiar",
            "Switched to {target}.": "Cambiado a {target}.",
            "Switched to {target} and reloaded for the matching team.": "Cambiado a {target} y recargado para el equipo correspondiente.",
            "built in code": "código integrado",
            "imported code": "código importado",
            "Save and Switch": "Guardar y cambiar",
            "Discard and Switch": "Descartar y cambiar",
            "Save the current character code changes before switching?": "¿Guardar los cambios del código del personaje actual antes de cambiar?",
            "Switch All to Built In Code": "Cambiar todo a código integrado",
            "Switch All to Imported Code": "Cambiar todo a código importado",
            "Switch All Team Code": "Cambiar el código de todos los equipos",
            "Switch all teams to built in code?": "¿Cambiar todos los equipos a código integrado?",
            "Switch all teams to imported code?": "¿Cambiar todos los equipos a código importado?",
            "No team has imported code to switch.": "No hay equipos con código importado para cambiar.",
            "Switched {count} teams to {target}.": "Se cambiaron {count} equipos a {target}.",
            "Skipped {count} teams that never imported code.": "Se omitieron {count} equipos que nunca importaron código.",
            "Failed {count} teams.": "{count} equipos no se pudieron cambiar.",
            "Switch every team between imported and built in code": "Cambia todos los equipos entre código importado y código integrado",
            "Imported code is in effect": "Código en vigor: importado",
            "Built in code is in effect": "Código en vigor: integrado",
            "Never imported code, skipped by Switch All": "Nunca importó código; el cambio global lo omitirá",
            "Reset this character to built in code for this team?": "¿Restablecer este personaje al código integrado en este equipo?",
            "The whole team's current code is now its imported code.": "El código actual de todo el equipo es ahora su código importado.",
            "Replace Imported Code": "Reemplazar código importado",
            "This team runs built in code. Saving makes the whole team's current code its imported code and replaces the imported code of: {names}": "Este equipo usa el código integrado. Al guardar, el código actual de todo el equipo pasa a ser su código importado y reemplaza el código importado de: {names}",
            "The current code of {names} is neither the built in nor the imported code of this team and is lost when switching.": "El código actual de {names} no es ni el código integrado ni el importado de este equipo y se perderá al cambiar.",
            "Keep as Imported Code and Switch": "Guardar como código importado y cambiar",
            "Skipped {count} teams whose current code is not kept as imported code, switch them one by one.": "Se omitieron {count} equipos cuyo código actual no está guardado como código importado; cámbialos uno por uno.",
            "Partially Completed": "Completado parcialmente",
        },
    }

    # Match locale prefix/exact match
    for loc_key, d in _locale_fallbacks.items():
        if locale_str == loc_key or (locale_str and loc_key.startswith(locale_str[:2])):
            if message in d:
                return d[message]

    # Default to English (source text)
    return message


class TranslatedDialog(MessageBoxBase):
    def tr(self, message):
        return translate_ui(message)

    def set_dialog_title(self, title):
        self.setWindowTitle(title)
        self.title_label = SubtitleLabel(title, self.widget)
        self.viewLayout.addWidget(self.title_label)

    def add_field(self, label, value):
        label_widget = BodyLabel(label, self.widget)
        value_widget = BodyLabel(str(value), self.widget)
        value_widget.setWordWrap(True)
        self.viewLayout.addWidget(label_widget)
        self.viewLayout.addWidget(value_widget)
        return value_widget


def workshop_team_slug(team):
    names = sorted((
        re.sub(r"[^A-Za-z0-9-]+", "_", get_english_char_name(name)).strip("_")
        for name in normalize_team(team)
    ), key=str.casefold)
    return "_".join(names)


def workshop_team_url(team):
    return WORKSHOP_TEAM_URL.format(slug=quote(workshop_team_slug(team), safe="_-"))


def fetch_all_workshop_teams():
    url = WORKSHOP_TEAMS_ALL_URL
    logger.info(f"char code workshop all teams request: {url}")
    try:
        with urlopen(url, timeout=15) as response:
            content = response.read(5_000_001)
    except HTTPError as error:
        if error.code == 404:
            return []
        raise
    if len(content) > 5_000_000:
        raise ValueError(translate_ui("Workshop response is too large."))
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(translate_ui("Workshop returned invalid JSON.")) from error
    if not isinstance(payload, dict) or not isinstance(payload.get("teams"), list):
        raise ValueError(translate_ui("Workshop response is invalid."))

    all_codes = []
    for team_entry in payload["teams"]:
        if not isinstance(team_entry, dict):
            continue
        team_str = team_entry.get("team", "")
        members = team_entry.get("members", [])
        codes = team_entry.get("codes", [])
        for code in codes:
            if not isinstance(code, dict):
                continue
            item = dict(code)
            if "team" not in item or not item["team"]:
                item["team"] = team_str
            if "members" not in item or not item["members"]:
                item["members"] = members
            all_codes.append(item)

    return sorted(all_codes, key=lambda code: int(code.get("timestamp") or 0), reverse=True)


def fetch_workshop_codes(team):
    expected_members = sorted((get_english_char_name(name) for name in normalize_team(team)), key=str.casefold)
    url = workshop_team_url(team)
    logger.info(f"char code workshop request: {url}")
    try:
        with urlopen(url, timeout=15) as response:
            content = response.read(2_000_001)
    except HTTPError as error:
        if error.code == 404:
            return []
        raise
    if len(content) > 2_000_000:
        raise ValueError(translate_ui("Workshop response is too large."))
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(translate_ui("Workshop returned invalid JSON.")) from error
    if not isinstance(payload, dict) or not isinstance(payload.get("codes"), list):
        raise ValueError(translate_ui("Workshop response is invalid."))
    members = payload.get("members")
    if members is not None and sorted(members, key=str.casefold) != expected_members:
        raise ValueError(translate_ui("Workshop returned a different team."))
    codes = [code for code in payload["codes"] if isinstance(code, dict)]
    return sorted(codes, key=lambda code: int(code.get("timestamp") or 0), reverse=True)


def format_workshop_local_time(code, date_only=False):
    modified_at = code.get("modifiedAt")
    try:
        if modified_at:
            value = datetime.fromisoformat(str(modified_at).replace("Z", "+00:00")).astimezone()
        else:
            value = datetime.fromtimestamp(float(code.get("timestamp") or 0)).astimezone()
        return value.strftime("%Y-%m-%d") if date_only else value.strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return ""


class TeamSelectionDialog(TranslatedDialog):
    def __init__(self, characters, defaults, parent=None):
        super().__init__(parent)
        self.widget.setMinimumWidth(440)
        self.set_dialog_title(self.tr("Create Team"))
        self.viewLayout.addWidget(BodyLabel(self.tr("Select 3 different characters"), self.widget))
        self.combos = []
        for index in range(3):
            combo = ComboBox(self.widget)
            for char_cls in characters:
                combo.addItem(self.tr(get_english_char_name(char_cls)), userData=char_cls.__name__)
            default_name = defaults[index].__name__ if index < len(defaults) else None
            default_index = combo.findData(default_name)
            combo.setCurrentIndex(default_index if default_index >= 0 else index)
            combo.currentIndexChanged.connect(self._update_create_enabled)
            self.combos.append(combo)
            self.viewLayout.addWidget(combo)
        self.yesButton.setText(self.tr("Create Team"))
        self.cancelButton.setText(self.tr("Cancel"))
        self._update_create_enabled()

    def _update_create_enabled(self):
        names = [combo.currentData() for combo in self.combos]
        self.yesButton.setEnabled(len(set(names)) == 3)

    def selected_names(self):
        return [combo.currentData() for combo in self.combos]


class ExportTeamDialog(TranslatedDialog):
    def __init__(self, default_name, parent=None):
        super().__init__(parent)
        self.widget.setMinimumWidth(520)
        self.set_dialog_title(self.tr("Export Team"))
        self.name_edit = LineEdit(self.widget)
        self.name_edit.setText(default_name)
        self.description_edit = TextEdit(self.widget)
        self.description_edit.setFixedHeight(90)
        self.author_edit = LineEdit(self.widget)
        self.version_edit = LineEdit(self.widget)
        self.version_edit.setText("1.0.0")
        for label, field in (
            (self.tr("Name"), self.name_edit), (self.tr("Description"), self.description_edit),
            (self.tr("Author"), self.author_edit), (self.tr("Version"), self.version_edit),
        ):
            self.viewLayout.addWidget(BodyLabel(label, self.widget))
            self.viewLayout.addWidget(field)
        self.yesButton.setText(self.tr("Export"))
        self.cancelButton.setText(self.tr("Cancel"))

    def validate(self):
        values = (self.name_edit.text(), self.description_edit.toPlainText(),
                  self.author_edit.text(), self.version_edit.text())
        if not all(value.strip() for value in values):
            show_info_bar(self.window(), self.tr("All fields are required."),
                          title=self.tr("Missing Information"), error=True)
            return False
        return True

    def values(self):
        return {
            "name": self.name_edit.text().strip(),
            "description": self.description_edit.toPlainText().strip(),
            "author": self.author_edit.text().strip(),
            "version": self.version_edit.text().strip(),
        }


class ImportTeamDialog(TranslatedDialog):
    def __init__(self, manifest, translated_team, parent=None):
        super().__init__(parent)
        self.widget.setMinimumWidth(560)
        self.set_dialog_title(self.tr("Import Team"))
        self.add_field(self.tr("Name"), manifest["name"])
        self.add_field(self.tr("Description"), manifest["description"])
        self.add_field(self.tr("Team"), translated_team)
        self.add_field(self.tr("Version"), manifest["version"])
        warning = BodyLabel(self.tr("Importing will override the local code for this team."), self.widget)
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #d13438;")
        self.viewLayout.addWidget(warning)
        self.yesButton.setText(self.tr("Confirm Import"))
        self.cancelButton.setText(self.tr("Cancel"))


class WorkshopDialog(TranslatedDialog):
    import_requested = Signal(object)

    def __init__(self, codes, team_name=None, parent=None):
        super().__init__(parent)
        self.all_codes = list(codes)
        self.filtered_codes = list(codes)
        self.widget.setMinimumSize(1100, 560)
        if team_name:
            title = self.tr("{team_name} - Team Workshop").format(team_name=team_name)
        else:
            title = self.tr("Team Workshop")
        self.set_dialog_title(title)

        filter_layout = QHBoxLayout()
        self.search_edit = SearchLineEdit(self.widget)
        self.search_edit.setPlaceholderText(
            self.tr("Search by team, character, author or description...")
        )
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._apply_filter)

        self.char_filter_combo = ComboBox(self.widget)
        self.char_filter_combo.setMinimumWidth(160)
        self.char_filter_combo.addItem(self.tr("All Characters"), userData="")

        all_chars = set()
        for code in self.all_codes:
            for member in code.get("members", []):
                if member:
                    all_chars.add(member)

        sorted_chars = sorted(
            all_chars,
            key=lambda c: self.tr(get_english_char_name(c)).casefold(),
        )
        for char_name in sorted_chars:
            display_name = self.tr(get_english_char_name(char_name))
            self.char_filter_combo.addItem(display_name, userData=char_name)
        self.char_filter_combo.currentIndexChanged.connect(self._apply_filter)

        self.count_label = CaptionLabel("", self.widget)

        filter_layout.addWidget(self.search_edit, 1)
        filter_layout.addWidget(BodyLabel(self.tr("Character:"), self.widget))
        filter_layout.addWidget(self.char_filter_combo)
        filter_layout.addWidget(self.count_label)
        self.viewLayout.addLayout(filter_layout)

        self.table = TableWidget(self.widget)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            self.tr("Team"), self.tr("Description"), self.tr("Author"),
            self.tr("Version"), self.tr("Modified"), self.tr("Action"),
        ])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 185)
        self.table.setColumnWidth(2, 130)
        self.table.setColumnWidth(3, 85)
        self.table.setColumnWidth(4, 120)
        self.table.setColumnWidth(5, 80)
        setCustomStyleSheet(
            self.table,
            "QTableView::item { padding-left: 5px; padding-right: 5px; }",
            "QTableView::item { padding-left: 5px; padding-right: 5px; }",
        )
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)

        # Container for table and external vertical scrollbar
        table_container = QWidget(self.widget)
        table_container_layout = QHBoxLayout(table_container)
        table_container_layout.setContentsMargins(0, 0, 16, 0)
        table_container_layout.setSpacing(0)
        table_container_layout.addWidget(self.table)

        # Place the floating vertical scrollbar into table_container, cleanly outside the table
        sb = self.table.scrollDelagate.vScrollBar
        sb.setParent(table_container)
        sb.raise_()

        orig_event_filter = self.table.scrollDelagate.eventFilter
        def _scroll_event_filter(obj, e):
            res = orig_event_filter(obj, e)
            if e.type() == QEvent.Resize and obj is self.table.viewport():
                sb.resize(12, self.table.height() - 2)
                sb.move(self.table.x() + self.table.width() + 4, self.table.y() + 1)
            return res
        self.table.scrollDelagate.eventFilter = _scroll_event_filter

        self.viewLayout.addWidget(table_container, 1)

        self.empty_label = BodyLabel(self.tr("No shared code matches the search criteria."), self.widget)
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.viewLayout.addWidget(self.empty_label)
        self.empty_label.hide()

        self.yesButton.setText(self.tr("Close"))
        self.hideCancelButton()
        self._apply_filter()

    def _team_display_text(self, code):
        members = code.get("members")
        if members and isinstance(members, list):
            names = [self.tr(get_english_char_name(m.strip())) for m in members if m.strip()]
            return ", ".join(names)
        raw_team = code.get("team", "")
        if raw_team:
            names = [self.tr(get_english_char_name(m.strip())) for m in raw_team.split(",") if m.strip()]
            return ", ".join(names)
        return ""

    def _apply_filter(self):
        query = self.search_edit.text().strip().lower()
        selected_char = self.char_filter_combo.currentData()

        matched = []
        for code in self.all_codes:
            if selected_char:
                members = [str(m).casefold() for m in code.get("members", [])]
                if selected_char.casefold() not in members:
                    continue

            if query:
                name = str(code.get("name", "")).lower()
                author = str(code.get("author", "")).lower()
                description = str(code.get("description", "")).lower()
                raw_team = str(code.get("team", "")).lower()
                display_team = self._team_display_text(code).lower()
                member_names = " ".join(str(m).lower() for m in code.get("members", []))
                
                search_target = f"{name} {author} {description} {raw_team} {display_team} {member_names}"
                if query not in search_target:
                    continue

            matched.append(code)

        self.filtered_codes = matched
        self._update_table()

    def _update_table(self):
        codes = self.filtered_codes
        count_text = self.tr("{count} configurations").format(count=len(codes))
        self.count_label.setText(count_text)

        if not codes:
            self.table.setRowCount(0)
            self.table.hide()
            self.empty_label.show()
            return

        self.empty_label.hide()
        self.table.show()
        self.table.setRowCount(len(codes))
        for row, code in enumerate(codes):
            display_team = self._team_display_text(code)
            raw_desc = str(code.get("description", "") or "")
            # Take only the first non-empty line for a crisp single-line preview in table
            lines = [line.strip() for line in raw_desc.splitlines() if line.strip()]
            desc = lines[0] if lines else ""
            values = (
                display_team,
                desc,
                code.get("author", ""),
                code.get("version", ""),
                format_workshop_local_time(code, date_only=True),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                if column == 1:
                    # Hovering shows the original full multi-line description without loss
                    item.setToolTip(raw_desc)
                self.table.setItem(row, column, item)

            # Cell widget with container and layout to ensure button is neatly centered
            container = QWidget(self.table)
            container_layout = QHBoxLayout(container)
            container_layout.setContentsMargins(0, 2, 0, 2)
            container_layout.setAlignment(Qt.AlignCenter)
            button = PrimaryPushButton(self.tr("Import"), container)
            button.setFixedSize(60, 28)
            button.clicked.connect(lambda _checked=False, item=code: self.import_requested.emit(item))
            container_layout.addWidget(button)
            self.table.setCellWidget(row, 5, container)

    def _on_row_double_clicked(self, row, _col):
        if 0 <= row < len(self.filtered_codes):
            code = self.filtered_codes[row]
            dialog = TranslatedDialog(self.window())
            dialog.widget.setMinimumWidth(560)
            dialog.set_dialog_title(self.tr("Configuration Details"))
            dialog.add_field(self.tr("Team"), self._team_display_text(code))
            dialog.add_field(self.tr("Name"), code.get("name", ""))
            dialog.add_field(self.tr("Author"), code.get("author", ""))
            dialog.add_field(self.tr("Version"), code.get("version", ""))
            dialog.add_field(self.tr("Modified"), format_workshop_local_time(code))
            
            desc_label = BodyLabel(self.tr("Description"), dialog.widget)
            desc_edit = TextEdit(dialog.widget)
            desc_edit.setPlainText(code.get("description", ""))
            desc_edit.setReadOnly(True)
            desc_edit.setFixedHeight(180)
            dialog.viewLayout.addWidget(desc_label)
            dialog.viewLayout.addWidget(desc_edit)

            dialog.yesButton.setText(self.tr("Import"))
            dialog.cancelButton.setText(self.tr("Close"))
            if dialog.exec():
                self.import_requested.emit(code)


class CharacterCodeTab(CustomTab):
    def __init__(self):
        super().__init__()
        self.characters = self._unique_characters()
        self.char_by_name = {char_cls.__name__: char_cls for char_cls in self.characters}
        self.current_team = None
        self.current_char_cls = None
        self.current_team_row = -1
        self.current_member_index = -1
        self.clean_code = ""
        self.loading_editor = False
        self.suppress_selection_guard = False
        self.current_code_state = TEAM_CODE_STATE_NONE
        self.char_label_by_cls = self._char_labels()
        self.char_feature_index = self._load_char_feature_index()
        self.char_feature_images = {}
        self.char_source_pixmaps = {}
        self.show_char_feature_image = False

        splitter = QSplitter(Qt.Horizontal, self.view)
        splitter.setChildrenCollapsible(False)
        left = QWidget(splitter)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.addWidget(BodyLabel(self.tr("Teams")))
        self.team_list = ListWidget(left)
        self.team_list.setMinimumWidth(210)
        self.team_list.setMaximumWidth(300)
        self.team_list.setItemDelegate(TeamListDelegate(self.team_list))
        self.team_list.currentRowChanged.connect(self._team_selected)
        left_layout.addWidget(self.team_list, 1)
        self.switch_all_button = PushButton(translate_ui("Switch All to Built In Code"))
        self.switch_all_button.setToolTip(
            translate_ui("Switch every team between imported and built in code"))
        self.switch_all_button.clicked.connect(self._switch_all_code_mode)
        left_layout.addWidget(self.switch_all_button)
        team_buttons = QVBoxLayout()
        first_team_button_row = QHBoxLayout()
        self.create_team_button = PrimaryPushButton(FluentIcon.ADD, self.tr("Create Team"))
        self.create_team_button.clicked.connect(self._create_team)
        self.delete_team_button = PushButton(FluentIcon.DELETE, self.tr("Delete Team"))
        self.delete_team_button.clicked.connect(self._delete_team)
        self.workshop_button = PushButton(FluentIcon.LIBRARY, self.tr("Workshop"))
        self.workshop_button.clicked.connect(self._open_workshop)
        first_team_button_row.addWidget(self.create_team_button)
        first_team_button_row.addWidget(self.delete_team_button)
        second_team_button_row = QHBoxLayout()
        self.import_team_button = PushButton(FluentIcon.DOWNLOAD, self.tr("Import Team"))
        self.import_team_button.clicked.connect(self._import_team)
        self.export_team_button = PushButton(FluentIcon.SHARE, self.tr("Export Team"))
        self.export_team_button.clicked.connect(self._export_team)
        second_team_button_row.addWidget(self.workshop_button)
        second_team_button_row.addWidget(self.import_team_button)
        third_team_button_row = QHBoxLayout()
        self.upload_team_button = PushButton(FluentIcon.GITHUB, self.tr("Upload Team"))
        self.upload_team_button.clicked.connect(self._open_upload_team)
        third_team_button_row.addWidget(self.export_team_button)
        third_team_button_row.addWidget(self.upload_team_button)
        team_buttons.addLayout(first_team_button_row)
        team_buttons.addLayout(second_team_button_row)
        team_buttons.addLayout(third_team_button_row)
        left_layout.addLayout(team_buttons)

        right = QWidget(splitter)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)
        top = QHBoxLayout()
        self.char_image_label = QLabel()
        self.char_image_label.setFixedSize(52, 52)
        self.char_image_label.setAlignment(Qt.AlignCenter)
        self.member_combo = ComboBox(right)
        self.member_combo.setMinimumWidth(190)
        self.member_combo.currentIndexChanged.connect(self._member_selected)
        self.ask_ai_button = PushButton(FluentIcon.ROBOT, self.tr("Ask AI"))
        self.ask_ai_button.clicked.connect(self._copy_ask_ai_template)
        top.addWidget(self.char_image_label)
        top.addWidget(BodyLabel(self.tr("Character Code")))
        top.addWidget(self.member_combo)
        top.addStretch(1)
        top.addWidget(self.ask_ai_button)
        right_layout.addLayout(top)

        self.editor = CodeEditor(right)
        self.editor.setMinimumHeight(520)
        self.editor.setLineWrapMode(PlainTextEdit.NoWrap)
        font = self.editor.font()
        font.setFamily("Consolas")
        font.setPointSize(10)
        self.editor.setFont(font)
        self.highlighter = PythonHighlighter(self.editor.document())
        self.editor.textChanged.connect(self._editor_text_changed)
        right_layout.addWidget(self.editor, 1)

        bottom = QHBoxLayout()
        self.status_label = BodyLabel("")
        self.reset_button = PushButton(FluentIcon.SYNC, self.tr("Reset to Built In"))
        self.reset_button.clicked.connect(self._switch_code_mode)
        self.save_button = PrimaryPushButton(FluentIcon.SAVE, self.tr("Save"))
        self.save_button.clicked.connect(self._save_current)
        bottom.addWidget(self.status_label, 1)
        bottom.addWidget(self.reset_button)
        bottom.addWidget(self.save_button)
        right_layout.addLayout(bottom)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        self.add_widget(splitter, stretch=1)
        self._set_editor_enabled(False)
        normalize_custom_teams()
        self._refresh_team_list()
        qconfig.themeChangedFinished.connect(self.team_list.viewport().update)

    @property
    def name(self):
        return self.tr("Character Code")

    @property
    def icon(self):
        return FluentIcon.CODE

    def _unique_characters(self):
        return sorted({info["cls"] for info in char_dict.values()},
                      key=lambda cls: get_english_char_name(cls).casefold())

    def _char_labels(self):
        result = {}
        for label, info in char_dict.items():
            result.setdefault(info["cls"], self._label_name(label))
        return result

    def _refresh_team_list(self, selected_team=None):
        selected_team = normalize_team(selected_team) if selected_team else self.current_team
        teams = list_custom_teams()
        states = {team: team_code_state(team) for team in teams}
        self.team_list.blockSignals(True)
        self.team_list.clear()
        selected_row = -1
        for row, team in enumerate(teams):
            display_team = sorted(team, key=lambda name: get_english_char_name(name).casefold())
            label = ", ".join(self.tr(get_english_char_name(name)) for name in display_team)
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, list(team))
            self._mark_team_state(item, states[team])
            self.team_list.addItem(item)
            if team == selected_team:
                selected_row = row
        self.team_list.blockSignals(False)
        if selected_row < 0 and teams:
            selected_row = 0
        if selected_row >= 0:
            self.team_list.setCurrentRow(selected_row)
        else:
            self.current_team = None
            self.current_char_cls = None
            self.member_combo.clear()
            self._set_editor_enabled(False)
        self._update_switch_all_button(states)
        self._update_code_mode_button()

    @staticmethod
    def _mark_team_state(item, state):
        """TeamListDelegate paints the dot of the state in front of the team name."""
        item.setData(TEAM_CODE_STATE_ROLE, state)
        item.setToolTip(team_state_tooltip(state))

    def _refresh_team_state_marker(self):
        """Patch the marker of the current row after a single team switch.

        Rebuilding the whole list would drop the scroll position and re-run
        every team on disk, while this only re-reads the states once."""
        teams = list_custom_teams()
        states = {team: team_code_state(team) for team in teams}
        team = self.current_team
        row = teams.index(team) if team in teams else -1
        if row >= 0:
            item = self.team_list.item(row)
            if item is not None:
                self._mark_team_state(item, states[team])
        self._update_switch_all_button(states)

    def _team_selected(self, row):
        if self.suppress_selection_guard:
            return
        if not self._guard_unsaved_changes():
            self.suppress_selection_guard = True
            self.team_list.setCurrentRow(self.current_team_row)
            self.suppress_selection_guard = False
            return
        item = self.team_list.item(row)
        if item is None:
            return
        team = normalize_team(item.data(Qt.UserRole))
        # A list rebuild re-selects the same team, which must not jump back to the first member.
        member_index = max(self.current_member_index, 0) if team == self.current_team else 0
        self.current_team = team
        self.current_team_row = row
        self.member_combo.blockSignals(True)
        self.member_combo.clear()
        for class_name in self.current_team:
            self.member_combo.addItem(self.tr(get_english_char_name(class_name)), userData=class_name)
        self.member_combo.setCurrentIndex(member_index)
        self.member_combo.blockSignals(False)
        self._set_editor_enabled(True)
        self._member_selected(member_index)

    def _member_selected(self, index):
        if index < 0 or self.current_team is None or self.suppress_selection_guard:
            return
        if not self._guard_unsaved_changes():
            self.suppress_selection_guard = True
            self.member_combo.setCurrentIndex(self.current_member_index)
            self.suppress_selection_guard = False
            return
        self.current_char_cls = self.char_by_name.get(self.member_combo.itemData(index))
        self.current_member_index = index
        self._load_editor_code()
        self._update_char_image()
        self._update_code_mode_button()

    def _set_editor_enabled(self, enabled):
        self.editor.setReadOnly(not enabled)
        for widget in (self.member_combo, self.delete_team_button,
                       self.export_team_button, self.ask_ai_button, self.reset_button, self.save_button):
            widget.setEnabled(enabled)
        # Workshop button should always remain enabled to allow browsing & importing any team
        self.workshop_button.setEnabled(True)
        if not enabled:
            self.loading_editor = True
            self.editor.clear()
            self.loading_editor = False
            self.status_label.setText(self.tr("Create or import a team to edit character code."))
            self.reset_button.setText(self.tr("Reset to Built In"))
            self._set_switch_icon(self.reset_button, TEAM_CODE_MODE_BUILTIN)

    def _load_editor_code(self):
        if self.current_team is None or self.current_char_cls is None:
            return
        code = read_team_char_code(self.current_team, self.current_char_cls)
        self.loading_editor = True
        self.editor.setPlainText(code)
        self.clean_code = code
        self.loading_editor = False
        self.status_label.setText("")
        self._highlight_changed_lines()

    def _editor_text_changed(self):
        if self.loading_editor:
            return
        self._highlight_changed_lines()
        self.status_label.setText(self.tr("Unsaved changes") if self._has_unsaved_changes() else "")
        self._update_reset_enabled()

    def _has_unsaved_changes(self):
        return self.current_team is not None and self.editor.toPlainText() != self.clean_code

    def _confirm_discard_changes(self):
        box = MessageBox(self.tr("Unsaved Changes"), self.tr("Discard unsaved character code changes?"), self.window())
        return bool(box.exec())

    def _guard_unsaved_changes(self):
        """Ask before unsaved code gets dropped and return whether to go on.

        Discarding puts the saved code back into the editor right away, so the
        reloads that follow do not ask a second time."""
        if not self._has_unsaved_changes():
            return True
        if not self._confirm_discard_changes():
            return False
        self._load_editor_code()
        return True

    def _create_team(self):
        defaults = self._detected_team()
        if len(defaults) != 3:
            defaults = self.characters[:3]
        dialog = TeamSelectionDialog(self.characters, defaults, self.window())
        if not dialog.exec():
            return
        team = normalize_team(dialog.selected_names())
        try:
            create_custom_team(team)
            self._refresh_team_list(team)
            show_info_bar(self.window(), self.tr("Team created."), title=self.tr("Success"))
        except Exception as e:
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)

    def _delete_team(self):
        if self.current_team is None:
            return
        team = self.current_team
        display_team = sorted(team, key=lambda name: get_english_char_name(name).casefold())
        team_name = ", ".join(self.tr(get_english_char_name(name)) for name in display_team)
        box = MessageBox(
            self.tr("Delete Team"),
            self.tr("Permanently delete the team {team}?").format(team=team_name),
            self.window(),
        )
        if not box.exec():
            return
        try:
            delete_custom_team(team)
            self._reload_live_team_code(team)
            self.current_team = None
            self.current_char_cls = None
            self._refresh_team_list()
            show_info_bar(self.window(), self.tr("Team deleted."), title=self.tr("Success"))
        except Exception as e:
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)

    def _detected_team(self):
        if self.executor is None:
            return []
        tasks = list(getattr(self.executor, "onetime_tasks", [])) + list(getattr(self.executor, "trigger_tasks", []))
        for task in tasks:
            chars = getattr(task, "chars", None)
            if not chars or len(chars) != 3 or any(char is None for char in chars):
                continue
            classes = []
            for char in chars:
                info = char_dict.get(getattr(char, "char_name", None))
                if info is None:
                    break
                classes.append(info["cls"])
            if len(classes) == 3 and len(set(classes)) == 3:
                return classes
        return []

    def _save_current(self):
        """Save the editor and return whether it was written.

        Saving always makes the whole team's current code its imported code: a
        never imported team gets its first imported code, and a team running
        built in code first confirms replacing the imported code it keeps."""
        if self.current_team is None or self.current_char_cls is None:
            return False
        team = self.current_team
        code = self.editor.toPlainText()
        codes = {self.current_char_cls.__name__: code}
        try:
            state = team_code_state(team)
            if state == TEAM_CODE_MODE_BUILTIN and not self._confirm_replace_import(team, codes):
                return False
            save_team_code_as_import(team, codes)
            reloaded = self._reload_live_team_code(team)
            self.clean_code = code
            self.status_label.setText(self.tr("Saved and reloaded"))
            message = self.tr("Team character code saved.")
            if reloaded:
                message = self.tr("Team character code saved and reloaded for the matching team.")
            if state == TEAM_CODE_STATE_NONE:
                message += " " + translate_ui("The whole team's current code is now its imported code.")
            show_info_bar(self.window(), message, title=self.tr("Success"))
            self.logger.info(f"saved team char code {self.current_char_cls.__name__} as imported code: {team}")
        except Exception as e:
            self.logger.error(f"save team char code failed: {e}")
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)
            return False
        self._update_code_mode_button()
        self._refresh_team_state_marker()
        return True

    def _confirm_replace_import(self, team, codes):
        changed = changed_import_members(team, codes)
        if not changed:
            return True
        names = ", ".join(self.tr(get_english_char_name(name)) for name in changed)
        box = MessageBox(
            translate_ui("Replace Imported Code"),
            translate_ui("This team runs built in code. Saving makes the whole team's current code its imported code "
                         "and replaces the imported code of: {names}").format(names=names),
            self.window(),
        )
        box.yesButton.setText(self.tr("Save"))
        box.cancelButton.setText(translate_ui("Cancel"))
        return bool(box.exec())

    @staticmethod
    def _switch_all_target(states):
        """Return (target, switchable teams). Only teams owning imported code can
        switch, and they decide which way the global button points."""
        switchable = [team for team, state in states.items() if state != TEAM_CODE_STATE_NONE]
        if switchable and all(states[team] == TEAM_CODE_MODE_IMPORT for team in switchable):
            return TEAM_CODE_MODE_BUILTIN, switchable
        return TEAM_CODE_MODE_IMPORT, switchable

    @staticmethod
    def _set_switch_icon(button, target_mode):
        """Color a switch button like the dot of the state it switches to, which
        turns the two buttons into the legend for the team list dots."""
        light, dark = _state_colors(target_mode)
        button.setIcon(FluentIcon.SYNC.colored(QColor(light), QColor(dark)))

    def _update_switch_all_button(self, states=None):
        if states is None:
            states = {team: team_code_state(team) for team in list_custom_teams()}
        target, switchable = self._switch_all_target(states)
        self._set_switch_icon(self.switch_all_button, target)
        self.switch_all_button.setText(
            translate_ui("Switch All to Built In Code") if target == TEAM_CODE_MODE_BUILTIN
            else translate_ui("Switch All to Imported Code"))
        self.switch_all_button.setEnabled(bool(switchable))

    def _update_code_mode_button(self):
        if self.current_team is None or self.current_char_cls is None:
            return
        state = team_code_state(self.current_team)
        self.current_code_state = state
        if state == TEAM_CODE_MODE_IMPORT:
            target = TEAM_CODE_MODE_BUILTIN
            self.reset_button.setText(translate_ui("Switch to Built In Code"))
        elif state == TEAM_CODE_MODE_BUILTIN:
            target = TEAM_CODE_MODE_IMPORT
            self.reset_button.setText(translate_ui("Switch to Imported Code"))
        else:
            target = TEAM_CODE_MODE_BUILTIN
            self.reset_button.setText(translate_ui("Reset to Built In"))
        self._set_switch_icon(self.reset_button, target)
        self._update_reset_enabled()

    def _update_reset_enabled(self):
        """A never imported team has nothing to switch; its button only resets the
        editor, which is pointless while the editor already holds the built in code."""
        if self.current_team is None or self.current_char_cls is None:
            return
        enabled = True
        if self.current_code_state == TEAM_CODE_STATE_NONE:
            enabled = self.editor.toPlainText() != read_builtin_char_code(self.current_char_cls)
        self.reset_button.setEnabled(enabled)

    def _settle_unsaved_changes(self):
        """Let the user save or drop unsaved editor code before a switch rewrites it.
        Returns whether the switch may go on."""
        if not self._has_unsaved_changes():
            return True
        action = self._confirm_switch_changes()
        if action == "save":
            return self._save_current()
        if action == "discard":
            self._load_editor_code()
            return True
        return False

    def _switch_all_code_mode(self):
        if not self._settle_unsaved_changes():
            return
        states = {team: team_code_state(team) for team in list_custom_teams()}
        target, switchable = self._switch_all_target(states)
        if not switchable:
            show_info_bar(self.window(), translate_ui("No team has imported code to switch."),
                          title=self.tr("Team"))
            return
        content = (translate_ui("Switch all teams to built in code?")
                   if target == TEAM_CODE_MODE_BUILTIN
                   else translate_ui("Switch all teams to imported code?"))
        box = MessageBox(translate_ui("Switch All Team Code"), content, self.window())
        box.yesButton.setText(translate_ui("Switch"))
        box.cancelButton.setText(translate_ui("Cancel"))
        if not box.exec():
            return
        try:
            summary = switch_all_teams_code_mode(target)
        except Exception as e:
            self.logger.error(f"switch all teams code mode failed: {e}")
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)
            return
        target_text = translate_ui("built in code") if target == TEAM_CODE_MODE_BUILTIN else translate_ui("imported code")
        for team in summary["switched"]:
            self._reload_live_team_code(team)
        self._refresh_team_list()
        if self.current_team is not None and self.current_char_cls is not None:
            self._load_editor_code()
        self.logger.info(f"switched all teams char code to {target}: {len(summary['switched'])} switched, "
                         f"{len(summary['drifted'])} drifted, {len(summary['failed'])} failed")
        parts = [translate_ui("Switched {count} teams to {target}.").format(
            count=len(summary["switched"]), target=target_text)]
        skipped = len(states) - len(switchable)
        if skipped:
            parts.append(translate_ui("Skipped {count} teams that never imported code.").format(count=skipped))
        if summary["drifted"]:
            parts.append(translate_ui(
                "Skipped {count} teams whose current code is not kept as imported code, switch them one by one."
            ).format(count=len(summary["drifted"])))
        if summary["failed"]:
            parts.append(translate_ui("Failed {count} teams.").format(count=len(summary["failed"])))
            title = translate_ui("Partially Completed") if summary["switched"] else self.tr("Error")
        else:
            title = self.tr("Success")
        show_info_bar(self.window(), " ".join(parts), title=title, error=bool(summary["failed"]))

    def _switch_code_mode(self):
        if self.current_team is None or self.current_char_cls is None:
            return
        team = self.current_team
        state = team_code_state(team)
        if state == TEAM_CODE_STATE_NONE:
            self._reset_to_builtin_code()
            return
        target = TEAM_CODE_MODE_BUILTIN if state == TEAM_CODE_MODE_IMPORT else TEAM_CODE_MODE_IMPORT
        if not self._settle_unsaved_changes():
            return
        # saving from built in code lands the team on imported code already
        if team_code_state(team) == target:
            return
        target_text = translate_ui("built in code") if target == TEAM_CODE_MODE_BUILTIN else translate_ui("imported code")
        drifted = drifted_team_members(team)
        keep_drifted = False
        if drifted:
            names = ", ".join(self.tr(get_english_char_name(name)) for name in drifted)
            action = self._confirm_switch_changes(
                translate_ui("Switch Character Code"),
                translate_ui("The current code of {names} is neither the built in nor the imported code of this team "
                             "and is lost when switching.").format(names=names),
                translate_ui("Keep as Imported Code and Switch"),
            )
            if action == "cancel":
                return
            keep_drifted = action == "save"
        else:
            content = (translate_ui("Switch the whole team to built in code?")
                       if target == TEAM_CODE_MODE_BUILTIN
                       else translate_ui("Switch the whole team to imported code?"))
            box = MessageBox(translate_ui("Switch Character Code"), content, self.window())
            box.yesButton.setText(translate_ui("Switch"))
            box.cancelButton.setText(translate_ui("Cancel"))
            if not box.exec():
                return
        try:
            if keep_drifted:
                save_team_code_as_import(team, {})
            if team_code_state(team) != target:
                switch_team_code_mode(team, target)
            reloaded = self._reload_live_team_code(team)
            message = translate_ui("Switched to {target}.").format(target=target_text)
            if reloaded:
                message = translate_ui("Switched to {target} and reloaded for the matching team.").format(target=target_text)
            show_info_bar(self.window(), message, title=self.tr("Success"))
            self.logger.info(f"switched team char code to {target}: {team}")
        except Exception as e:
            self.logger.error(f"switch team char code failed: {e}")
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)
        self._load_editor_code()
        self._update_code_mode_button()
        self._refresh_team_state_marker()

    def _confirm_switch_changes(self, title=None, content=None, save_text=None):
        box = MessageBox(
            title or translate_ui("Unsaved Changes"),
            content or translate_ui("Save the current character code changes before switching?"),
            self.window(),
        )
        box.yesButton.setText(save_text or translate_ui("Save and Switch"))
        box.cancelButton.setText(translate_ui("Cancel"))
        discard_button = PushButton(translate_ui("Discard and Switch"), box.buttonGroup)
        buttons = [box.yesButton, discard_button, box.cancelButton]
        box.buttonLayout.insertWidget(1, discard_button, 1, Qt.AlignVCenter)
        # MessageBox pins the widget size at construction time, before the
        # layout runs, and only accounts for its own two buttons. Grow it from
        # the real hints so the third button is not squeezed: every button gets
        # an equal share of the row, so the widest label decides the width.
        text_width = max(box.titleLabel.sizeHint().width(), box.contentLabel.sizeHint().width()) + 48
        button_width = max(button.sizeHint().width() for button in buttons) * len(buttons) + 96
        box.widget.setFixedSize(max(box.widget.width(), text_width, button_width), box.widget.height())
        result = "cancel"

        def choose(action):
            nonlocal result
            result = action

        box.yesButton.clicked.connect(lambda: choose("save"))
        discard_button.clicked.connect(lambda: choose("discard"))
        discard_button.clicked.connect(box.accept)
        box.cancelButton.clicked.connect(lambda: choose("cancel"))
        box.exec()
        return result

    def _reset_to_builtin_code(self):
        """Put the built in code of the current character into the editor. Nothing
        is written; saving it afterwards works like saving any other edit."""
        if self.current_char_cls is None:
            return
        box = MessageBox(
            translate_ui("Reset Character Code"),
            translate_ui("Reset this character to built in code for this team?"),
            self.window())
        if not box.exec():
            return
        self.editor.setPlainText(read_builtin_char_code(self.current_char_cls))

    def _export_team(self):
        if self.current_team is None:
            return
        if self._has_unsaved_changes():
            show_info_bar(self.window(), self.tr("Save changes before exporting."), title=self.tr("Error"), error=True)
            return
        default_name = "_".join(get_english_char_name(name).replace(" ", "_") for name in self.current_team)
        dialog = ExportTeamDialog(default_name, self.window())
        if not dialog.exec():
            return
        destination = QFileDialog.getExistingDirectory(self.window(), self.tr("Choose Export Folder"))
        if not destination:
            return
        try:
            path = export_custom_team(self.current_team, destination, **dialog.values())
            show_info_bar(self.window(), self.tr("Team exported to {path}").format(path=path), title=self.tr("Success"))
        except Exception as e:
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)

    def _import_team(self):
        if not self._guard_unsaved_changes():
            return
        archive_path, _filter = QFileDialog.getOpenFileName(
            self.window(), self.tr("Import Team"), "", self.tr("Zip files (*.zip)"))
        if not archive_path:
            return
        self._preview_and_import_archive(archive_path)

    def _open_workshop(self):
        # An import selects the imported team, so ask before anything is downloaded.
        if not self._guard_unsaved_changes():
            return
        try:
            codes = fetch_all_workshop_teams()
        except Exception as e:
            show_info_bar(self.window(), str(e), title=self.tr("Workshop Error"), error=True)
            return
        dialog = WorkshopDialog(codes, parent=self.window())
        dialog.import_requested.connect(lambda code: self._import_workshop_code(code, dialog))
        dialog.exec()

    def _import_workshop_code(self, code, parent):
        url = code.get("downloadUrl") or code.get("rawUrl")
        parsed = urlparse(str(url or ""))
        if parsed.scheme != "https" or parsed.hostname not in WORKSHOP_ARCHIVE_HOSTS:
            show_info_bar(parent, self.tr("Workshop download URL is invalid."), title=self.tr("Error"), error=True)
            return
        try:
            with urlopen(url, timeout=30) as response:
                content = response.read(20_000_001)
            if len(content) > 20_000_000:
                raise ValueError(self.tr("Workshop archive is too large."))
            with tempfile.TemporaryDirectory() as temp_dir:
                archive_path = Path(temp_dir) / Path(str(code.get("filename") or "team.zip")).name
                archive_path.write_bytes(content)
                self._preview_and_import_archive(archive_path, expected_team=None)
        except Exception as e:
            show_info_bar(parent, str(e), title=self.tr("Workshop Error"), error=True)

    def _preview_and_import_archive(self, archive_path, expected_team=None):
        try:
            info = inspect_team_archive(archive_path)
            if expected_team is not None and normalize_team(info["team"]) != normalize_team(expected_team):
                raise ValueError(self.tr("The archive is for a different team."))
        except Exception as e:
            box = MessageBox(translate_ui("Invalid Team Archive"), str(e), self.window())
            box.yesButton.setText(translate_ui("Close"))
            box.cancelButton.hide()
            box.exec()
            return False
        translated_team = ", ".join(
            self.tr(name.strip()) for name in info["manifest"]["team"].split(",")
        )
        dialog = ImportTeamDialog(info["manifest"], translated_team, self.window())
        if not dialog.exec():
            return False
        try:
            import_custom_team(info)
            self._refresh_team_list(info["team"])
            reloaded = self._reload_live_team_code(info["team"])
            message = self.tr("Team imported.")
            if reloaded:
                message = self.tr("Team imported and reloaded for the matching team.")
            show_info_bar(self.window(), message, title=self.tr("Success"))
            return True
        except Exception as e:
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)
            return False

    def _reload_live_team_code(self, team):
        if self.executor is None:
            return 0
        reloaded = 0
        expected_team = normalize_team(team)
        tasks = list(getattr(self.executor, "onetime_tasks", [])) + list(getattr(self.executor, "trigger_tasks", []))
        for task in tasks:
            chars = getattr(task, "chars", None)
            if not chars or len(chars) != 3 or any(char is None for char in chars):
                continue
            infos = [char_dict.get(char.char_name) for char in chars]
            if any(info is None for info in infos):
                continue
            if normalize_team(info["cls"] for info in infos) != expected_team:
                continue
            old_types = tuple(type(char) for char in chars)
            apply_team_char_classes(task, chars)
            reloaded += sum(old is not type(char) for old, char in zip(old_types, chars))
        return reloaded

    def _highlight_changed_lines(self):
        if self.current_char_cls is None:
            self.editor.setExtraSelections([])
            return
        builtin_lines = read_builtin_char_code(self.current_char_cls).splitlines()
        current_lines = self.editor.toPlainText().splitlines()
        changed_lines = set()
        for tag, _i1, _i2, j1, j2 in difflib.SequenceMatcher(None, builtin_lines, current_lines).get_opcodes():
            if tag != "equal":
                changed_lines.update(range(j1, max(j2, j1 + 1)))
        selections = []
        highlight = QColor(255, 230, 130, 80)
        for line in sorted(changed_lines):
            block = self.editor.document().findBlockByNumber(line)
            if block.isValid():
                selection = QTextEdit.ExtraSelection()
                selection.cursor = QTextCursor(block)
                selection.format.setBackground(highlight)
                selection.format.setProperty(QTextFormat.FullWidthSelection, True)
                selections.append(selection)
        self.editor.setExtraSelections(selections)

    def _copy_ask_ai_template(self):
        if self.current_char_cls is None:
            return
        class_name = self.current_char_cls.__name__
        template = f'''```python\n{self.editor.toPlainText()}\n```\n\n{self.tr("I want to implement:")}\n\n{self.tr("Please modify the full {class_name} character automation code above.").format(class_name=class_name)}\n\n{self.tr("Return only the complete modified Python code for the whole file, not a patch and not an explanation.")}\n{self.tr("Keep the class name as {class_name}. Preserve imports that are still needed.").format(class_name=class_name)}\n\n{self.tr("Use this BaseChar reference while reasoning about helper methods, task APIs, state, switching, cooldowns, and combat flow:")}\n{BASE_CHAR_URL}\n'''
        QApplication.clipboard().setText(template)
        show_info_bar(self.window(), self.tr("Ask AI template copied. Paste it into an AI chatbot."), title=self.tr("Copied"))

    def _open_upload_team(self):
        QDesktopServices.openUrl(QUrl(UPLOAD_TEAM_URL))

    def _update_char_image(self):
        self.char_image_label.clear()
        if not self.show_char_feature_image:
            return
        pixmap = self._get_char_feature_image(self.char_label_by_cls.get(self.current_char_cls))
        if pixmap is not None and not pixmap.isNull():
            self.char_image_label.setPixmap(pixmap)

    def _load_char_feature_index(self):
        feature_index = {}
        coco_path = Path("assets") / "coco_annotations.json"
        if not coco_path.exists():
            return feature_index
        try:
            data = json.loads(coco_path.read_text(encoding="utf-8"))
            image_by_id = {image["id"]: image["file_name"] for image in data.get("images", [])}
            category_by_id = {category["id"]: category["name"] for category in data.get("categories", [])}
            for annotation in data.get("annotations", []):
                name = category_by_id.get(annotation.get("category_id"))
                image_name = image_by_id.get(annotation.get("image_id"))
                bbox = annotation.get("bbox", [])
                if name and image_name and len(bbox) == 4:
                    feature_index[name] = (coco_path.parent / image_name, tuple(round(value) for value in bbox))
        except Exception as e:
            self.logger.error(f"load char feature image index failed: {e}")
        return feature_index

    def _get_char_feature_image(self, label_name):
        if not label_name:
            return None
        if label_name in self.char_feature_images:
            return self.char_feature_images[label_name]
        image_info = self.char_feature_index.get(label_name)
        if not image_info:
            return None
        image_path, (x, y, width, height) = image_info
        pixmap = self.char_source_pixmaps.get(image_path)
        if pixmap is None:
            pixmap = QPixmap(str(image_path))
            self.char_source_pixmaps[image_path] = pixmap
        if pixmap.isNull():
            return None
        image = pixmap.copy(x, y, width, height).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.char_feature_images[label_name] = image
        return image

    @staticmethod
    def _label_name(label):
        if isinstance(label, tuple):
            label = label[0]
        return getattr(label, "value", label)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.show_char_feature_image:
            self.show_char_feature_image = True
        self._update_char_image()

    def hideEvent(self, event):
        if self._has_unsaved_changes():
            self._confirm_discard_changes()
        super().hideEvent(event)
