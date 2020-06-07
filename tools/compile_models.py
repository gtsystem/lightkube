import json
import re
from collections import defaultdict
from typing import NamedTuple
RE_MODEL = re.compile("^.*[.](apis?|pkg)[.]")
import shutil
from pathlib import Path

from .compile import get_template

class Schema(NamedTuple):
    module: str
    name: str


def schema_name(orig_name) -> Schema:
    module = RE_MODEL.sub("", orig_name)
    parts = module.split(".")
    assert len(parts) <= 3
    if len(parts) == 3:
        module = f"{parts[0]}_{parts[1]}"
    else:
        module = parts[0]
    model = parts[-1]
    return Schema(module, model)


def to_pytype(defi, module, required=True):
    if not required:
        return to_pytype(defi, module)
    if 'items' in defi:
        return f'List[{to_pytype(defi["items"], module)}]'

    if '$ref' in defi:
        sc = schema_name(defi['$ref'])
        if sc.module == module:
            return sc.name
        else:
            return f'{sc.module}.{sc.name}'

    if 'type' in defi:
        return {
            'string': 'str',
            'integer': 'int',
            'number': 'float',
            'boolean': 'bool',
            'object': 'dict'
        }[defi['type']]

def make_prop_name(p_name):
    if p_name == 'continue':
        return 'continue_'
    return p_name


def get_props(defi, module):
    required = set(defi.get('required', []))
    props = []
    for p_name, p_defi in defi['properties'].items():
        props.append((p_name in required, p_name, p_defi))
    props.sort(key=lambda x:x[0], reverse=True)
    return [(make_prop_name(p_name), to_pytype(p_def, module, req), f' = None' if not req else '') for req, p_name, p_def in props]


def collect_imports(module, models):
    imports = set()
    for _, defi in models:
        if 'properties' in defi:
            for p_defi in defi['properties'].values():
                if '$ref' in p_defi:
                    imports.add(schema_name(p_defi['$ref']).module)
                elif 'items' in p_defi and '$ref' in p_defi['items']:
                    imports.add(schema_name(p_defi['items']['$ref']).module)

    if module in imports:
        imports.remove(module)
    return imports


def extract(fname, path):
    with open(fname) as f:
        sw = json.load(f)

    p = path.joinpath("models")
    shutil.rmtree(p)
    p.mkdir()

    modules = defaultdict(list)

    for name, defi in sw["definitions"].items():
        sn = schema_name(name)
        modules[sn.module].append((sn.name, defi))

    tmpl = get_template("tools/templates/models.tmpl")
    for module, models in modules.items():
        with p.joinpath(f"{module}.py").open("w") as fw:
            fw.write(tmpl.render(module=module, models=models, schema_name=schema_name, get_props=get_props, collect_imports=collect_imports))


if __name__ == "__main__":
    import sys
    extract(sys.argv[1], Path(sys.argv[2]))
