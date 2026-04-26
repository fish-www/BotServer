import json
import re
from pathlib import Path

# 匹配 i18n key 的正则：至少包含两个点的点分式标识符（如 title.goety.0）
_I18N_KEY_RE = re.compile(r'[a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+){2,}')


class I18nManager:
    def __init__(self, path: str = 'Resources/zh_cn.json'):
        self._data: dict[str, str] = {}
        try:
            p = Path(path)
            if p.exists():
                self._data = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            pass

    def strip_i18n(self, text: str) -> str:
        """移除文本中所有 i18n key，返回原始玩家名（用于数据库存储与统计）。"""
        result = _I18N_KEY_RE.sub('', text)
        return re.sub(r'\s+', ' ', result).strip()

    def translate_i18n(self, text: str) -> str:
        """将文本中的 i18n key 替换为对应翻译，未命中时保留原 key（用于显示）。"""
        def replace(m: re.Match) -> str:
            return self._data.get(m.group(0), m.group(0))
        result = _I18N_KEY_RE.sub(replace, text)
        return re.sub(r'\s+', ' ', result).strip()


i18n_manager = I18nManager()
