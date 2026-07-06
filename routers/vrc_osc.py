r"""
读取 VRChat 在本地生成的 OSC 配置文件，用于自动获取可用参数列表。

VRC 启动时会在 `%LOCALAPPDATA%Low\VRChat\VRChat\OSC\` 下为每个用户与 avatar 生成 json：
{
  "id": "avtr_xxx",
  "name": "Avatar Name",
  "parameters": [
    { "name": "/avatar/parameters/EarLDis", "output": { "address": "/avatar/parameters/EarLDis", "type": "Float" } },
    ...
  ]
}
"""
import os
import glob
import json
from typing import List, Dict, Any

import logging

from fastapi import APIRouter, HTTPException, status

# 从 OSC 运行时中获取 VRChat 实时切换的 avatar ID（由 /avatar/change 更新）
from routers.coyote import current_vrc_avatar_id

router = APIRouter(prefix="/api/vrc")


def _get_osc_root() -> str:
    """获取 VRC OSC 配置根目录"""
    local_low = os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "LocalLow")
    return os.path.join(local_low, "VRChat", "VRChat", "OSC")


def _get_current_user_dir() -> str:
    """
    检测当前活跃的 VRChat 用户配置目录。
    取最近修改过的 usr_xxx 目录作为当前登录用户。
    """
    osc_root = _get_osc_root()
    if not os.path.isdir(osc_root):
        return None
    candidates = [
        os.path.join(osc_root, d)
        for d in os.listdir(osc_root)
        if d.startswith("usr_") and os.path.isdir(os.path.join(osc_root, d))
    ]
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def _parse_parameters(params) -> List[Dict[str, str]]:
    """解析 VRC OSC 参数字段（兼容 dict 和 list 格式）"""
    result: List[Dict[str, str]] = []
    if isinstance(params, dict):
        for key, val in params.items():
            addr, ptype = key, ""
            out = val.get("output") if isinstance(val, dict) else None
            if isinstance(out, dict):
                addr = out.get("address", key)
                ptype = out.get("type", "")
            result.append({"name": addr, "type": ptype})
    elif isinstance(params, list):
        for p in params:
            if not isinstance(p, dict):
                continue
            out = p.get("output") if isinstance(p, dict) else None
            addr = ptype = ""
            if isinstance(out, dict):
                addr = out.get("address", "")
                ptype = out.get("type", "")
            if not addr:
                addr = p.get("name") or p.get("address", "")
            if not ptype:
                ptype = p.get("type", "")
            if addr:
                result.append({"name": addr, "type": ptype})
    return result


@router.get("/avatars")
async def list_avatars() -> Dict[str, Any]:
    """
    读取当前 VRChat 用户的 avatar OSC 参数列表。
    自动检测当前登录的用户目录（最近活跃的 usr_xxx），仅返回该用户的模型。
    返回结构: { avatars: [ { id, name, parameters: [ {name, type} ], is_current: bool } ] }
    """
    user_dir = _get_current_user_dir()
    if not user_dir:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到 VRChat 用户配置。请先在 VRChat 中启用 OSC 并切换一次角色。",
        )

    avatars: List[Dict[str, Any]] = []
    newest_time = 0

    # 扫描当前用户目录下的 avatar json（可能直接在用户目录下，也可能在 Avatars/ 子目录）
    for json_path in glob.glob(os.path.join(user_dir, "**", "*.json"), recursive=True):
        try:
            mtime = os.path.getmtime(json_path)
            with open(json_path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except Exception:
            continue

        avatar_id = data.get("id") or data.get("avatar_id")
        if not avatar_id:
            continue

        # 同一个 id 只保留最新修改的文件
        existing = next((a for a in avatars if a["id"] == avatar_id), None)
        if existing:
            if mtime > existing["_mtime"]:
                existing["_mtime"] = mtime
                existing["name"] = data.get("name") or avatar_id
                existing["parameters"] = _parse_parameters(data.get("parameters", {}))
            continue

        avatars.append({
            "id": avatar_id,
            "name": data.get("name") or avatar_id,
            "parameters": _parse_parameters(data.get("parameters", {})),
            "_mtime": mtime,
        })
        if mtime > newest_time:
            newest_time = mtime

    # 标记当前穿戴的模型
    # 优先用 OSC 运行时追踪的 avatar ID（/avatar/change 实时更新）
    # 回退到文件修改时间推测
    tracked_avatar = current_vrc_avatar_id
    logging.info(f"vrc_osc: 扫描到 {len(avatars)} 个 avatar, tracked_avatar={tracked_avatar}")
    for a in avatars:
        if tracked_avatar and a["id"] == tracked_avatar:
            a["is_current"] = True
        else:
            a["is_current"] = a["_mtime"] == newest_time
        logging.info(f"  avatar: {a['name']} (id={a['id']}, is_current={a['is_current']})")
        del a["_mtime"]

    return {"avatars": avatars, "current_user_id": os.path.basename(user_dir)}
