from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "external" / "story_forge" / "src"))

from story_forge.movie_renderer import launch_movie_post_render_hook


def test_post_render_hook_receives_an_existing_final_frames_directory(tmp_path):
    frames_dir = tmp_path / "final" / "frames"
    frames_dir.mkdir(parents=True)
    hook = "/opt/storyforge-spatialize"

    with patch.dict("os.environ", {"MOVIE_POST_RENDER_HOOK": hook}), patch(
        "story_forge.movie_renderer.subprocess.Popen"
    ) as popen:
        assert launch_movie_post_render_hook(frames_dir) is True

    popen.assert_called_once_with(
        [hook, str(frames_dir)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def test_post_render_hook_is_fail_open_when_final_frames_are_missing(tmp_path):
    missing_frames_dir = tmp_path / "not-promoted" / "frames"

    with patch.dict("os.environ", {"MOVIE_POST_RENDER_HOOK": "/missing/hook"}), patch(
        "story_forge.movie_renderer.subprocess.Popen"
    ) as popen:
        assert launch_movie_post_render_hook(missing_frames_dir) is False

    popen.assert_not_called()
