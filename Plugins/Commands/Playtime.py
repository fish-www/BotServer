from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message
from nonebot.log import logger
from nonebot.params import CommandArg

from Scripts.Managers import data_manager
from Scripts.Managers.Playtime import playtime_manager
from Scripts.Utils import Rules, turn_message

logger.debug('加载命令 Playtime 完毕！')
matcher = on_command('playtime', aliases={'pt'}, force_whitespace=True, rule=Rules.command_rule)

# 支持中英文时间段关键字
_PERIOD_MAP: dict[str, str] = {
    'today': 'today', '今日': 'today', '今天': 'today',
    'week':  'week',  '本周': 'week',  '周':   'week',
    'month': 'month', '本月': 'month', '月':   'month',
    'year':  'year',  '今年': 'year',  '年':   'year',
    'all':   'all',   '全部': 'all',   '总':   'all',
}

_PERIOD_LABEL: dict[str, str] = {
    'today': '今日',
    'week':  '本周',
    'month': '本月',
    'year':  '今年',
    'all':   '全部时间',
}


def _fmt(seconds: int) -> str:
    """将秒数格式化为人类可读字符串。"""
    if seconds <= 0:
        return '0 秒'
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    parts = []
    if h: parts.append(f'{h} 小时')
    if m: parts.append(f'{m} 分')
    if s or not parts: parts.append(f'{s} 秒')
    return ' '.join(parts)


@matcher.handle()
async def handle_playtime(event: GroupMessageEvent, args: Message = CommandArg()):
    tokens = args.extract_plain_text().strip().split()
    first = tokens[0].lower() if tokens else ''

    # ── .playtime rank [period] ─────────────────────────────────────────────
    if first == 'rank':
        period = _PERIOD_MAP.get((tokens[1] if len(tokens) > 1 else '').lower(), 'all')
        ranking = await playtime_manager.get_ranking(period)
        await matcher.finish(turn_message(_rank_lines(ranking, period)))

    # ── .playtime [player <name>] [period] ──────────────────────────────────
    if first == 'player':
        # 按玩家名查询，用法：.playtime player <name> [period]
        if len(tokens) < 2:
            await matcher.finish('请提供玩家名称！')
        player_name = tokens[1]
        period = _PERIOD_MAP.get((tokens[2] if len(tokens) > 2 else '').lower(), 'all')
        seconds = await playtime_manager.get_player_seconds(player_name, period)
        by_server = await playtime_manager.get_player_seconds_by_server(player_name, period)
        await matcher.finish(turn_message(_player_detail_lines(player_name, seconds, by_server, period)))

    # ── .playtime [period] ─── 查询自己 ────────────────────────────────────
    period = _PERIOD_MAP.get(first, 'all')
    user = str(event.user_id)
    players: list[str] | None = data_manager.players.get(user)
    if not players:
        await matcher.finish('你还没有绑定玩家，无法查询游玩时长！请先使用 .bound 绑定。')

    # 统计所有绑定玩家的时长并合并
    total = 0
    detail: dict[str, dict[str, int]] = {}
    for player in players:
        secs = await playtime_manager.get_player_seconds(player, period)
        by_server = await playtime_manager.get_player_seconds_by_server(player, period)
        total += secs
        detail[player] = by_server

    await matcher.finish(turn_message(_self_lines(players, total, detail, period)))


# ── 消息生成 ────────────────────────────────────────────────────────────────

def _self_lines(players: list[str], total: int, detail: dict, period: str):
    label = _PERIOD_LABEL[period]
    names = '、'.join(players)
    yield f'===== {label}游玩时长 ====='
    yield f'玩家：{names}'
    yield f'合计：{_fmt(total)}'
    if len(players) > 1:
        yield '── 分角色 ──'
        for player, by_server in detail.items():
            p_total = sum(by_server.values())
            yield f'  {player}：{_fmt(p_total)}'
    # 按服务器细分（合并所有角色）
    merged: dict[str, int] = {}
    for by_server in detail.values():
        for srv, secs in by_server.items():
            merged[srv] = merged.get(srv, 0) + secs
    if merged:
        yield '── 分服务器 ──'
        for srv, secs in sorted(merged.items(), key=lambda x: -x[1]):
            yield f'  [{srv}]：{_fmt(secs)}'


def _player_detail_lines(player: str, total: int, by_server: dict, period: str):
    label = _PERIOD_LABEL[period]
    yield f'===== {player} {label}游玩时长 ====='
    yield f'合计：{_fmt(total)}'
    if by_server:
        for srv, secs in by_server.items():
            yield f'  [{srv}]：{_fmt(secs)}'


def _rank_lines(ranking: list, period: str):
    label = _PERIOD_LABEL[period]
    yield f'===== {label}游玩时长排行 ====='
    if not ranking:
        yield '暂无数据。'
        return
    for i, row in enumerate(ranking, 1):
        player, seconds = row[0], int(row[1])
        yield f'  {i}. {player}  {_fmt(seconds)}'
