from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

Codec = Literal["h264", "h265", "av1"]
VALID_CODECS = {"h264", "h265", "av1"}


class ConfigError(ValueError):
    """Raised when the user config is missing or invalid."""


@dataclass(frozen=True)
class LadderPointConfig:
    bitrate_kbps: int
    width: int
    height: int
    codec: Codec


@dataclass(frozen=True)
class CodecEncodingSettings:
    preset: str | None = None
    profile: str | None = None
    pix_fmt: str | None = None
    keyint: int | None = None


@dataclass(frozen=True)
class EncodingConfig:
    defaults: CodecEncodingSettings = field(default_factory=CodecEncodingSettings)
    per_codec: dict[Codec, CodecEncodingSettings] = field(default_factory=dict)

    def resolve(self, codec: Codec) -> CodecEncodingSettings:
        override = self.per_codec.get(codec)
        if override is None:
            return self.defaults
        return CodecEncodingSettings(
            preset=override.preset if override.preset is not None else self.defaults.preset,
            profile=override.profile if override.profile is not None else self.defaults.profile,
            pix_fmt=override.pix_fmt if override.pix_fmt is not None else self.defaults.pix_fmt,
            keyint=override.keyint if override.keyint is not None else self.defaults.keyint,
        )


@dataclass(frozen=True)
class VmafConfig:
    model_path: Path | None = None
    evaluation_resolution: tuple[int, int] | None = None
    log_format: str = "json"
    extra_filter_options: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OutputConfig:
    report_path: Path = Path("out/report.json")
    plots_dir: Path | None = None


@dataclass(frozen=True)
class RuntimeConfig:
    threads: int = max(1, os.cpu_count() or 1)
    work_dir: Path = Path("out/work")
    keep_temp: bool = False


@dataclass(frozen=True)
class AppConfig:
    source_path: Path
    points: list[LadderPointConfig]
    encoding: EncodingConfig = field(default_factory=EncodingConfig)
    vmaf: VmafConfig = field(default_factory=VmafConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Config file does not exist: {config_path}")
    raw = _load_raw_config(config_path)
    return parse_config(raw, base_dir=config_path.parent)


def parse_config(raw: dict[str, Any], base_dir: Path | None = None) -> AppConfig:
    if not isinstance(raw, dict):
        raise ConfigError("Config root must be an object")

    base_dir = base_dir or Path.cwd()
    input_raw = _require_object(raw, "input")
    source_path = _resolve_path(base_dir, _require_string(input_raw, "source_path"))
    if not source_path.exists():
        raise ConfigError(f"Input source_path does not exist: {source_path}")
    if not source_path.is_file():
        raise ConfigError(f"Input source_path is not a file: {source_path}")

    ladder_raw = _require_object(raw, "ladder")
    points_raw = ladder_raw.get("points")
    if not isinstance(points_raw, list) or not points_raw:
        raise ConfigError("ladder.points must be a non-empty list")
    points = [_parse_point(point, idx) for idx, point in enumerate(points_raw)]

    encoding = _parse_encoding(raw.get("encoding"))
    vmaf = _parse_vmaf(raw.get("vmaf"), base_dir=base_dir)
    output = _parse_output(raw.get("output"), base_dir=base_dir)
    runtime = _parse_runtime(raw.get("runtime"), base_dir=base_dir)
    return AppConfig(
        source_path=source_path,
        points=points,
        encoding=encoding,
        vmaf=vmaf,
        output=output,
        runtime=runtime,
    )


def _load_raw_config(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")

    if suffix == ".json":
        return _load_json(text, path=path)
    if suffix in {".yaml", ".yml"}:
        return _load_yaml(text, path=path)

    # Fallback for extensionless or non-standard names.
    try:
        return _load_json(text, path=path)
    except ConfigError:
        return _load_yaml(text, path=path)


def _load_json(text: str, path: Path) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigError(f"JSON config must be an object: {path}")
    return value


def _load_yaml(text: str, path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise ConfigError(
            "YAML support requires PyYAML. Install it and retry, or use JSON config."
        ) from exc

    try:
        value = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigError(f"YAML config must be an object: {path}")
    return value


def _parse_point(raw: Any, index: int) -> LadderPointConfig:
    if not isinstance(raw, dict):
        raise ConfigError(f"ladder.points[{index}] must be an object")
    bitrate_kbps = _require_positive_int(raw, "bitrate_kbps", f"ladder.points[{index}]")
    width = _require_positive_int(raw, "width", f"ladder.points[{index}]")
    height = _require_positive_int(raw, "height", f"ladder.points[{index}]")
    codec = _require_string(raw, "codec", f"ladder.points[{index}]")
    if codec not in VALID_CODECS:
        raise ConfigError(
            f"ladder.points[{index}].codec must be one of {sorted(VALID_CODECS)}, got '{codec}'"
        )
    return LadderPointConfig(
        bitrate_kbps=bitrate_kbps,
        width=width,
        height=height,
        codec=cast(Codec, codec),
    )


def _parse_encoding(raw: Any) -> EncodingConfig:
    if raw is None:
        return EncodingConfig()
    if not isinstance(raw, dict):
        raise ConfigError("encoding must be an object")

    has_per_codec = any(key in VALID_CODECS for key in raw)
    if has_per_codec:
        defaults_raw = {k: v for k, v in raw.items() if k not in VALID_CODECS}
        defaults = _parse_encoding_settings(defaults_raw, "encoding")
        per_codec: dict[Codec, CodecEncodingSettings] = {}
        for codec in VALID_CODECS:
            codec_raw = raw.get(codec)
            if codec_raw is None:
                continue
            if not isinstance(codec_raw, dict):
                raise ConfigError(f"encoding.{codec} must be an object")
            per_codec[codec] = _parse_encoding_settings(codec_raw, f"encoding.{codec}")  # type: ignore[index]
        return EncodingConfig(defaults=defaults, per_codec=per_codec)

    defaults = _parse_encoding_settings(raw, "encoding")
    return EncodingConfig(defaults=defaults, per_codec={})


def _parse_encoding_settings(raw: dict[str, Any], path: str) -> CodecEncodingSettings:
    preset = raw.get("preset")
    profile = raw.get("profile")
    pix_fmt = raw.get("pix_fmt")
    keyint = raw.get("keyint")
    if preset is not None and not isinstance(preset, str):
        raise ConfigError(f"{path}.preset must be a string")
    if profile is not None and not isinstance(profile, str):
        raise ConfigError(f"{path}.profile must be a string")
    if pix_fmt is not None and not isinstance(pix_fmt, str):
        raise ConfigError(f"{path}.pix_fmt must be a string")
    if keyint is not None and (not isinstance(keyint, int) or keyint <= 0):
        raise ConfigError(f"{path}.keyint must be a positive integer")
    return CodecEncodingSettings(preset=preset, profile=profile, pix_fmt=pix_fmt, keyint=keyint)


def _parse_vmaf(raw: Any, base_dir: Path) -> VmafConfig:
    if raw is None:
        return VmafConfig()
    if not isinstance(raw, dict):
        raise ConfigError("vmaf must be an object")

    model_path_raw = raw.get("model_path")
    model_path: Path | None = None
    if model_path_raw is not None:
        if not isinstance(model_path_raw, str):
            raise ConfigError("vmaf.model_path must be a string")
        model_path = _resolve_path(base_dir, model_path_raw)

    evaluation_resolution_raw = raw.get("evaluation_resolution")
    evaluation_resolution: tuple[int, int] | None = None
    if evaluation_resolution_raw is not None:
        if not isinstance(evaluation_resolution_raw, str):
            raise ConfigError("vmaf.evaluation_resolution must be a string like '1920x1080'")
        evaluation_resolution = parse_resolution_string(
            evaluation_resolution_raw,
            field_name="vmaf.evaluation_resolution",
        )

    log_format = raw.get("log_format", raw.get("log_fmt", "json"))
    if not isinstance(log_format, str):
        raise ConfigError("vmaf.log_format must be a string")

    extra_raw = raw.get("extra_filter_options", raw.get("extra_args", []))
    if not isinstance(extra_raw, list) or not all(isinstance(item, str) for item in extra_raw):
        raise ConfigError("vmaf.extra_filter_options must be a list of strings")

    return VmafConfig(
        model_path=model_path,
        evaluation_resolution=evaluation_resolution,
        log_format=log_format,
        extra_filter_options=list(extra_raw),
    )


def _parse_output(raw: Any, base_dir: Path) -> OutputConfig:
    if raw is None:
        return OutputConfig()
    if not isinstance(raw, dict):
        raise ConfigError("output must be an object")

    report_path_raw = raw.get("report_path", "out/report.json")
    if not isinstance(report_path_raw, str):
        raise ConfigError("output.report_path must be a string")
    report_path = _resolve_path(base_dir, report_path_raw)

    plots_dir_raw = raw.get("plots_dir")
    if plots_dir_raw is None:
        plots_dir = None
    else:
        if not isinstance(plots_dir_raw, str):
            raise ConfigError("output.plots_dir must be a string")
        plots_dir = _resolve_path(base_dir, plots_dir_raw)

    return OutputConfig(report_path=report_path, plots_dir=plots_dir)


def _parse_runtime(raw: Any, base_dir: Path) -> RuntimeConfig:
    if raw is None:
        return RuntimeConfig()
    if not isinstance(raw, dict):
        raise ConfigError("runtime must be an object")

    threads_raw = raw.get("threads", max(1, os.cpu_count() or 1))
    if not isinstance(threads_raw, int) or threads_raw <= 0:
        raise ConfigError("runtime.threads must be a positive integer")

    work_dir_raw = raw.get("work_dir", "out/work")
    if not isinstance(work_dir_raw, str):
        raise ConfigError("runtime.work_dir must be a string")
    work_dir = _resolve_path(base_dir, work_dir_raw)

    keep_temp_raw = raw.get("keep_temp", False)
    if not isinstance(keep_temp_raw, bool):
        raise ConfigError("runtime.keep_temp must be a boolean")

    return RuntimeConfig(threads=threads_raw, work_dir=work_dir, keep_temp=keep_temp_raw)


def _require_object(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ConfigError(f"{key} must be an object")
    return value


def _require_string(raw: dict[str, Any], key: str, path: str | None = None) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        qualifier = f"{path}." if path else ""
        raise ConfigError(f"{qualifier}{key} must be a non-empty string")
    return value


def _require_positive_int(raw: dict[str, Any], key: str, path: str | None = None) -> int:
    value = raw.get(key)
    qualifier = f"{path}." if path else ""
    if not isinstance(value, int) or value <= 0:
        raise ConfigError(f"{qualifier}{key} must be a positive integer")
    return value


def _resolve_path(base_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (base_dir / path).resolve()


def parse_resolution_string(value: str, field_name: str = "resolution") -> tuple[int, int]:
    cleaned = value.strip().lower()
    parts = cleaned.split("x")
    if len(parts) != 2:
        raise ConfigError(f"{field_name} must be in '<width>x<height>' format")

    width_raw, height_raw = parts
    try:
        width = int(width_raw)
        height = int(height_raw)
    except ValueError as exc:
        raise ConfigError(f"{field_name} must contain integer width and height") from exc

    if width <= 0 or height <= 0:
        raise ConfigError(f"{field_name} width and height must be positive")
    return (width, height)
