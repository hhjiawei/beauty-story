import os
import asyncio  # [改动] 新增导入
from pathlib import Path
from langchain.tools import tool

SKILL_DIR = Path(__file__).resolve().parent.parent / "backends" / "skills" / "huashu-wechat-image"


@tool
async def generate_image(prompt: str, output_path: str, aspect: str = "wide") -> str:
    """Generate image via Gemini 3 Pro. Args: prompt(EN), output_path, aspect(cover/wide/standard/square)."""
    script = SKILL_DIR / "scripts" / "generate_image.py"
    if not script.exists():
        return f"Error: {script} not found"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = ["python3", str(script), "--prompt", prompt, "--filename", output_path, "--aspect", aspect]
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if api_key:
        cmd.extend(["--api-key", api_key])

    proc = None  # [改动] 初始化，防止超时异常时未定义
    try:
        proc = await asyncio.create_subprocess_exec(  # [改动] 替换 subprocess.run
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)  # [改动] 异步等待+超时

        if proc.returncode == 0 and Path(output_path).exists():
            return f"OK: {output_path}"
        return f"Error: {stderr.decode()[:200]}"
    except asyncio.TimeoutError:
        if proc:
            proc.kill()
            await proc.wait()
        return "Error: Timeout after 120s"
    except Exception as e:
        return f"Error: {e}"


@tool
async def upload_image(image_path: str) -> str:
    """Upload image to ImgBB, return permanent URL."""
    script = SKILL_DIR / "scripts" / "upload_image.py"
    if not script.exists():
        return f"Error: {script} not found"

    api_key = os.environ.get("IMGBB_API_KEY", "")
    if not api_key:
        return "Error: IMGBB_API_KEY not set"

    cmd = ["python3", str(script), image_path, "--api-key", api_key]

    proc = None  # [改动] 初始化
    try:
        proc = await asyncio.create_subprocess_exec(  # [改动] 替换 subprocess.run
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)  # [改动] 异步等待+超时

        for line in stdout.decode().split("\n"):
            url = line.strip()
            if url.startswith("https://"):
                return url
        return f"Error: {stderr.decode()[:200]}"
    except asyncio.TimeoutError:
        if proc:
            proc.kill()
            await proc.wait()
        return "Error: Timeout after 120s"
    except Exception as e:
        return f"Error: {e}"