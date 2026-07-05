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

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/api/vrc")


def _get_osc_root() -> str:
    """获取 VRC OSC 配置根目录"""
    local_low = os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "LocalLow")
    return os.path.join(local_low, "VRChat", "VRChat", "OSC")


@router.get("/avatars")
async def list_avatars() -> Dict[str, Any]:
    """
    列出所有 VRC OSC 配置中可用的 avatar 及其参数。
    返回结构: { avatars: [ { id, name, parameters: [ {name, type} ] } ] }
    """
    osc_root = _get_osc_root()
    if not os.path.isdir(osc_root):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"VRC OSC 目录不存在: {osc_root}。请确保 VRChat 已启动过一次。",
        )

    avatars: List[Dict[str, Any]] = []
    seen_ids = set()

    # 递归查找所有 .json 文件
    for json_path in glob.glob(os.path.join(osc_root, "**", "*.json"), recursive=True):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        avatar_id = data.get("id") or data.get("avatar_id")
        if not avatar_id or avatar_id in seen_ids:
            continue
        seen_ids.add(avatar_id)

        name = data.get("name") or avatar_id
        parameters: List[Dict[str, str]] = []

        # VRC OSC json 的 parameters 字段可能是字典或列表
        params = data.get("parameters", {})
        if isinstance(params, dict):
            for key, val in params.items():
                # val 形如 { "input": {...}, "output": { "address": "...", "type": "Float" } }
                addr = key
                ptype = ""
                out = val.get("output") if isinstance(val, dict) else None
                if isinstance(out, dict):
                    addr = out.get("address", key)
                    ptype = out.get("type", "")
                parameters.append({"name": addr, "type": ptype})
        elif isinstance(params, list):
            for p in params:
                if isinstance(p, dict):
                    addr = p.get("name") or p.get("address", "")
                    ptype = p.get("type", "")
                    if addr:
                        parameters.append({"name": addr, "type": ptype})

        avatars.append(
            {
                "id": avatar_id,
                "name": name,
                "parameters": parameters,
            }
        )

    return {"avatars": avatars}
