import json
import re
from collections import defaultdict
from typing import List, NamedTuple
import shutil
from pathlib import Path

from .compile import get_template
from .model import Model, Import

RE_MODEL = re.compile("^.*[.](apis?|pkg)[.]")


def collect_imports(module: Import, models: List[Model]):
    imports = set()
    for model in models:
        if model.has_properties:
            for prop in model.properties:
                if prop.import_module:
                    imports.add(prop.import_module)
        else:
            if model.import_module:
                imports.add(model.import_module)

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
        model = Model(name, defi)
        modules[model.module].append(model)

    tmpl = get_template("tools/templates/models.tmpl")
    for module, models in modules.items():
        with p.joinpath(f"{module}.py").open("w") as fw:
            fw.write(tmpl.render(models=models, modules=collect_imports(Import(".", module), models)))


if __name__ == "__main__":
    import sys
    extract(sys.argv[1], Path(sys.argv[2]))
