from datetime import datetime, timedelta
from pathlib import Path
from time import time

import aiosqlite
from nonebot.log import logger

_DDL = '''
    CREATE TABLE IF NOT EXISTS sessions (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        player    TEXT    NOT NULL,
        server    TEXT    NOT NULL,
        joined_at INTEGER NOT NULL,
        left_at   INTEGER
    );
    CREATE INDEX IF NOT EXISTS idx_sessions_player ON sessions (player);
    CREATE INDEX IF NOT EXISTS idx_sessions_time   ON sessions (joined_at);
'''


class PlaytimeManager:
    db_path = Path('Data/playtime.db')
    _db: aiosqlite.Connection = None

    async def init(self):
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.executescript(_DDL)
        await self._db.commit()
        logger.success('游玩时长数据库初始化完毕！')

    async def close(self):
        if self._db:
            # Bot 正常退出时，将所有未关闭的会话打上当前时间戳
            await self._db.execute(
                'UPDATE sessions SET left_at = ? WHERE left_at IS NULL',
                (int(time()),)
            )
            await self._db.commit()
            await self._db.close()
            self._db = None
            logger.info('游玩时长数据库已关闭。')

    # ------------------------------------------------------------------ writes

    async def record_join(self, player: str, server: str):
        now = int(time())
        # 幂等保护：若此玩家此服务器已有未关闭会话，先关闭再新建
        await self._db.execute(
            'UPDATE sessions SET left_at = ? WHERE player = ? AND server = ? AND left_at IS NULL',
            (now, player, server)
        )
        await self._db.execute(
            'INSERT INTO sessions (player, server, joined_at) VALUES (?, ?, ?)',
            (player, server, now)
        )
        await self._db.commit()
        logger.debug(f'[Playtime] {player} 加入 [{server}]')

    async def record_leave(self, player: str, server: str):
        now = int(time())
        cursor = await self._db.execute(
            'UPDATE sessions SET left_at = ? WHERE player = ? AND server = ? AND left_at IS NULL',
            (now, player, server)
        )
        await self._db.commit()
        if cursor.rowcount:
            logger.debug(f'[Playtime] {player} 离开 [{server}]（本次 {cursor.rowcount} 条）')

    async def close_server_sessions(self, server: str):
        """关闭指定服务器所有未结束的会话（服务器关闭 / Bot 重连时调用）。"""
        now = int(time())
        cursor = await self._db.execute(
            'UPDATE sessions SET left_at = ? WHERE server = ? AND left_at IS NULL',
            (now, server)
        )
        await self._db.commit()
        if cursor.rowcount:
            logger.debug(f'[Playtime] 已关闭 [{server}] 的 {cursor.rowcount} 个悬空会话')

    async def reconcile_online(self, server: str, players: list[str]):
        """Bot 重连后重建在线玩家会话：先关闭旧悬空会话，再为在线玩家开启新会话。"""
        await self.close_server_sessions(server)
        if not players:
            return
        now = int(time())
        await self._db.executemany(
            'INSERT INTO sessions (player, server, joined_at) VALUES (?, ?, ?)',
            [(p, server, now) for p in players]
        )
        await self._db.commit()
        logger.info(f'[Playtime] 已为 [{server}] 重建 {len(players)} 名在线玩家的会话：{players}')

    # ------------------------------------------------------------------ reads

    @staticmethod
    def _time_range(period: str) -> tuple[int, int]:
        now = datetime.now()
        match period:
            case 'today':
                start = datetime(now.year, now.month, now.day)
            case 'week':
                monday = now - timedelta(days=now.weekday())
                start = datetime(monday.year, monday.month, monday.day)
            case 'month':
                start = datetime(now.year, now.month, 1)
            case 'year':
                start = datetime(now.year, 1, 1)
            case _:  # 'all'
                start = datetime(2000, 1, 1)
        return int(start.timestamp()), int(now.timestamp())

    async def get_player_seconds(self, player: str, period: str = 'all') -> int:
        """返回指定玩家在指定时间段内的游玩秒数（在线中的会话实时计入）。"""
        start, end = self._time_range(period)
        now = int(time())
        cursor = await self._db.execute(
            '''
            SELECT COALESCE(SUM(
                MIN(COALESCE(left_at, :now), :end) - MAX(joined_at, :start)
            ), 0)
            FROM sessions
            WHERE player   = :player
              AND joined_at < :end
              AND (left_at  > :start OR left_at IS NULL)
            ''',
            {'now': now, 'end': end, 'start': start, 'player': player}
        )
        row = await cursor.fetchone()
        return int(row[0])

    async def get_ranking(self, period: str = 'all') -> list[tuple[str, int]]:
        """返回 [(player, seconds), ...] 按游玩时长降序排列。"""
        start, end = self._time_range(period)
        now = int(time())
        cursor = await self._db.execute(
            '''
            SELECT player,
                   COALESCE(SUM(
                       MIN(COALESCE(left_at, :now), :end) - MAX(joined_at, :start)
                   ), 0) AS total
            FROM sessions
            WHERE joined_at < :end
              AND (left_at  > :start OR left_at IS NULL)
            GROUP BY player
            ORDER BY total DESC
            ''',
            {'now': now, 'end': end, 'start': start}
        )
        return await cursor.fetchall()

    async def get_player_seconds_by_server(
        self, player: str, period: str = 'all'
    ) -> dict[str, int]:
        """返回 {server_name: seconds} 用于按服务器分类显示。"""
        start, end = self._time_range(period)
        now = int(time())
        cursor = await self._db.execute(
            '''
            SELECT server,
                   COALESCE(SUM(
                       MIN(COALESCE(left_at, :now), :end) - MAX(joined_at, :start)
                   ), 0) AS total
            FROM sessions
            WHERE player    = :player
              AND joined_at < :end
              AND (left_at  > :start OR left_at IS NULL)
            GROUP BY server
            ORDER BY total DESC
            ''',
            {'now': now, 'end': end, 'start': start, 'player': player}
        )
        return {row[0]: int(row[1]) for row in await cursor.fetchall()}


playtime_manager = PlaytimeManager()
