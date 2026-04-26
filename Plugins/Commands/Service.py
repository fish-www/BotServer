import asyncio
from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message
from nonebot.log import logger
from nonebot.params import CommandArg

from Scripts.Config import config
from Scripts.Managers import data_manager
from Scripts.Utils import Rules, turn_message, get_permission, get_args

logger.debug('加载命令 Service 完毕！')
matcher = on_command('service', force_whitespace=True, rule=Rules.command_rule)

_ACTIONS = ('start', 'stop', 'restart', 'status', 'reload')
_ACTION_LABEL = {'start': '启动', 'stop': '停止', 'restart': '重启', 'status': '查询状态', 'reload': "重载插件"}
# status 输出可能很长，截断至此行数
_MAX_OUTPUT_LINES = 20


@matcher.handle()
async def handle_service(event: GroupMessageEvent, args: Message = CommandArg()):
    if not get_permission(event):
        await matcher.finish('你没有权限控制服务器！')
    tokens = get_args(args)
    if len(tokens) < 2:
        await matcher.finish('参数不正确！用法：service <start|stop|restart|status|reload> <server>')
    action, server_flag = tokens[0].lower(), tokens[1]
    if action not in _ACTIONS:
        await matcher.finish(f'无效操作 [{action}]！支持：{" / ".join(_ACTIONS)}')
    unit = _resolve_unit(server_flag)
    if unit is None:
        await matcher.finish(f'服务器 [{server_flag}] 未配置服务映射，请在 .env 中设置 service_server_map。')
    if not config.service_ssh_host:
        await matcher.finish('未配置宿主机 SSH 地址，请在 .env 中设置 service_ssh_host。')
    try:
        stdout, stderr, exit_code = await _run_script(unit, action)
    except Exception as e:
        logger.error(f'[Service] SSH 执行失败：{e}')
        await matcher.finish(f'服务控制失败：{e}')
    message = turn_message(_service_lines(server_flag, unit, action, stdout, stderr, exit_code))
    await matcher.finish(message)


def _resolve_unit(server_flag: str) -> str | None:
    """将服务器名称或编号解析为服务标识符。"""
    try:
        index = int(server_flag) - 1
        if 0 <= index < len(data_manager.servers):
            return config.service_server_map.get(data_manager.servers[index])
    except ValueError:
        pass
    return config.service_server_map.get(server_flag)


async def _run_script(unit: str, action: str) -> tuple[str, str, int]:
    """SSH 到宿主机执行受限命令（service.sh），返回 (stdout, stderr, exit_code)。"""
    target = f'{config.service_ssh_user}@{config.service_ssh_host}' if config.service_ssh_user else config.service_ssh_host
    cmd = [
        'ssh',
        '-i', config.service_ssh_key,
        '-o', 'BatchMode=yes',
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'UserKnownHostsFile=/dev/null',
        '-o', 'LogLevel=ERROR',
        target,
        f'{action} {unit}',
    ]
    logger.debug(f'[Service] SSH 到宿主机执行：{action} {unit}')
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=65)
    return stdout_bytes.decode(errors='replace'), stderr_bytes.decode(errors='replace'), proc.returncode


def _service_lines(server: str, unit: str, action: str, stdout: str, stderr: str, exit_code: int):
    label = _ACTION_LABEL[action]
    yield f'===== 服务器 [{server}] {label} ====='
    yield f'单元：{unit}  |  退出码：{exit_code}'
    output = (stdout + stderr).strip()
    if not output:
        yield '（无输出）'
        return
    lines = output.splitlines()
    if len(lines) > _MAX_OUTPUT_LINES:
        lines = lines[:_MAX_OUTPUT_LINES]
        lines.append(f'…（输出过长，已截断，仅显示前 {_MAX_OUTPUT_LINES} 行）')
    yield from lines
