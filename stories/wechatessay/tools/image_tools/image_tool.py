import os, asyncio, tempfile
from pathlib import Path
from langchain.tools import tool

# The original working tool code - fixed to use temp dir for output
_HERE = Path(__file__).resolve().parent
_SCRIPT_DIR = _HERE.parent.parent / "backends" / "skills" / "huashu-wechat-image" / "scripts"


@tool
async def doubao_generate_image(prompt: str, output_path: str, aspect: str = "wide") -> str:
    """Generate image via Gemini 3 Pro. Args: prompt(EN), output_path, aspect(cover/wide/standard/square)."""
    script = _SCRIPT_DIR / "doubao_generate_image.py"
    if not script.exists():
        return f"Error: {script} not found"

    # Use temp dir to avoid WinError 3 on virtual paths
    safe_name = Path(output_path).name
    safe_path = Path(tempfile.gettempdir()) / "wechat_images" / safe_name
    safe_path.parent.mkdir(parents=True, exist_ok=True)

    # Use python instead of python3 on Windows
    python_exe = "python" if os.name == "nt" else "python3"
    cmd = [python_exe, str(script), "--prompt", prompt, "--filename", str(safe_path), "--aspect", aspect]
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if api_key:
        cmd.extend(["--api-key", api_key])

    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        if proc.returncode == 0 and safe_path.exists():
            return f"OK: {safe_path}"
        return f"Error: {stderr.decode()[:200]}"
    except asyncio.TimeoutError:
        if proc:
            proc.kill()
            await proc.wait()
        return "Error: Timeout after 120s"
    except Exception as e:
        return f"Error: {e}"


@tool
async def upload_image() -> str:
    """Upload image to ImgBB, return image name and permanent URL. eg:
        {
      "ab95-icapxph1314342.png": "https://i.ibb.co/cKNVpcqR/ab95-icapxph1314342.jpg",
      "fd5d-b866dbecd90751b7d56ad59145cc6d8f.png": "https://i.ibb.co/gFHDk461/fd5d-b866dbecd90751b7d56ad59145cc6d8f.jpg"
        }
    """
    script = _SCRIPT_DIR / "upload_image.py"
    if not script.exists():
        return f"Error: {script} not found"

    python_exe = "python" if os.name == "nt" else "python3"
    cmd = [python_exe, str(script)]
    # Use the correct API key from config
    env = os.environ.copy()
    env["IMGBB_API_KEY"] = "c39a93f52a2b63b4306ef97e106fbc3d"

    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode == 0:
            # Parse the URL from stdout
            output = stdout.decode()
            for line in output.split("\n"):
                if "URL:" in line or "url" in line.lower().strip().startswith("http"):
                    url = line.split("URL:")[-1].strip() if "URL:" in line else line.strip()
                    return url
            return f"OK: {output}"
        return f"Error: {stderr.decode()[:500]}"
    except asyncio.TimeoutError:
        if proc:
            proc.kill()
            await proc.wait()
        return "Error: Timeout after 60s"
    except Exception as e:
        return f"Error: {e}"
