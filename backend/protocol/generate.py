"""Generate Pydantic DTOs locally; frozen schemas remain the validation authority."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from datamodel_code_generator import DataModelType, InputFileType, generate

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    contracts = ROOT / "contracts"
    schemas = {p.name: json.loads(p.read_text()) for p in contracts.glob("*.schema.json")}

    def inline(value):
        if isinstance(value, dict):
            if "$ref" in value and value["$ref"].startswith("https://campusos.dev/contracts/v1/"):
                return inline(schemas[value["$ref"].rsplit("/", 1)[-1]])
            return {k: inline(v) for k, v in value.items() if k not in {"$id", "allOf"}}
        if isinstance(value, list):
            return [inline(v) for v in value]
        return value

    for name, schema in schemas.items():
        module = name.removesuffix(".schema.json").replace("-", "_")
        with TemporaryDirectory() as temporary:
            source = Path(temporary) / name
            source.write_text(json.dumps(inline(schema)))
            generate(
                source,
                input_file_type=InputFileType.JsonSchema,
                output=ROOT / "backend" / "protocol" / f"{module}_models.py",
                output_model_type=DataModelType.PydanticV2BaseModel,
                disable_timestamp=True,
                use_standard_collections=True,
                use_union_operator=True,
                use_annotated=True,
                field_constraints=True,
            )


if __name__ == "__main__":
    main()
