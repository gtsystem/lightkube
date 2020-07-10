import json
import shutil
from collections import defaultdict
import re
from pathlib import Path
from typing import NamedTuple

from jinja2 import Template


RE_PATH = re.compile("/apis?(?P<group>/.*?)?/(?P<version>v[^/]*)(?P<watch>/watch)?(?P<ns>/namespaces/{namespace})?/(?P<plural>[^/]*)(?:/{name}(?P<action>/[^/]*)?)?")


def get_template(fname):
    with open(fname) as f:
        return Template(f.read(), trim_blocks=True, lstrip_blocks=True)


class Compiled(NamedTuple):
    group: str
    version: str
    plural: str
    kind: str
    module: str
    namespaced: bool
    actions: list
    sub_actions: list


def extract(fname):
    with open(fname) as f:
        sw = json.load(f)

    i = 0
    for path, defi in sw["paths"].items():
        g = RE_PATH.match(path)
        if g is None:
            continue
        path_match = g.groupdict()
        if path_match["watch"]:
            continue
        key = ((path_match["group"] or "").lstrip("/"), path_match["version"], path_match["plural"])
        #print(key)
        methods = []
        resource = None
        tags = set()
        namespaced = path_match["ns"] is not None
        sub_action = path_match["action"].lstrip("/") if path_match["action"] else None
        for method, mdef in defi.items():
            if method != "parameters":
                action = mdef.get('x-kubernetes-action', method)
                if action != 'connect':     # TODO: add support for connect
                    methods.append(action)
                if resource is None:
                    resource = mdef.get("x-kubernetes-group-version-kind")
                tags.update(set(mdef.get('tags', [])))
                if "parameters" in mdef:
                    for parameter in mdef["parameters"]:
                        if parameter["name"] == "watch":
                            methods.append("watch")
                #if resource and resource['kind'] == "Pod":
                #    print(method, mdef)
            else:
                for parameter in mdef:
                    if parameter["name"] == "watch":
                        methods.append("watch")
        if resource:
            resource = (resource['group'], resource['version'], resource['kind'])

        if methods:     # at least one method
            yield {
                "path": path,
                "key": key,
                "resource": resource,
                "methods": methods,
                "tag": tags.pop(),
                "namespaced": namespaced,
                "sub_action": sub_action
            }



def aggregate(it):
    resources = defaultdict(list)
    for ele in it:
        print(ele)
        key = ele["key"]
        del ele["key"]
        resources[key].append(ele)
    return resources

def usorted(l):
    return sorted(set(l))


def compile_one(key, elements):
    namespaced = False
    tag = None
    #print()
    #print(key)
    kind = None
    for ele in elements:
        #print(ele['path'], ele['methods'])
        if ele["namespaced"]:
            namespaced = True
        if ele["resource"] and ele["sub_action"] is None:
            kind = ele["resource"][-1]
        if not tag and ele["tag"]:
            tag = ele["tag"]

    if kind is None:
        return

    sub_actions = []
    actions = set()
    for ele in elements:
        if ele["sub_action"]:
            sub_actions.append({
                'name': ele["sub_action"],
                'actions': usorted(ele["methods"]),
                'resource': ele["resource"]
            })
        elif namespaced and not ele["namespaced"]:
            actions.update([f"global_{m}" for m in ele["methods"]])
        else:
            actions.update(ele["methods"])

    if key:
        return Compiled(
            group=key[0],
            version=key[1],
            plural=key[2],
            kind=kind,
            module=tag,
            namespaced=namespaced,
            actions=usorted(actions),
            sub_actions=sub_actions
        )


def model_class(resource):
    group, version, name = resource
    if group == '':
        group = 'core'
    group = group.split(".", 1)[0]
    return f"m_{group}_{version}.{name}"


def add_class(compiled: Compiled):
    #print(compiled)
    res = tuple([compiled.group, compiled.version, compiled.kind])

    class_ = "NamespacedSubResource" if compiled.namespaced else "GlobalSubResource"
    actions = {}
    for suba in compiled.sub_actions:
        kind = compiled.kind + suba["name"].capitalize()

        #class_ = 'res.NamespacedResource' if compiled.namespaced else 'res.GlobalResource'
        #if 'global_list' in suba['actions']:
        #    classes.append('res.GlobalList')
        yield (kind, dict(
            resource=f"res.ResourceDef{suba['resource']}",
            parent=f"res.ResourceDef{res}",
            plural=repr(compiled.plural),
            verbs=suba['actions'],
            action=repr(suba["name"]),
        ), {}, [class_, model_class(suba['resource'])])
        actions[suba["name"].capitalize()] = kind

    #classes = ['res.NamespacedResource' if compiled.namespaced else 'res.GlobalResource']
    #if 'global_list' in compiled.actions:
    #    classes = ['res.NamespacedResourceG']
    if 'global_list' in compiled.actions:
        class_ = "NamespacedResourceG"
    else:
        class_ = "NamespacedResource" if compiled.namespaced else "GlobalResource"
    yield (compiled.kind, dict(
        resource=f"res.ResourceDef{res}",
        plural=repr(compiled.plural),
        verbs=compiled.actions
    ), actions, [class_, model_class(res)])



def compile(resources, path: Path):
    # actions
    # global_actions (only if namespaced)
    # sub_actions
    p = path.joinpath("resources")
    if p.exists():
        shutil.rmtree(p)
    p.mkdir()
    modules = defaultdict(list)
    for key, elements in resources.items():
        c = compile_one(key, elements)
        if c:
            modules[c.module].append(c)

    tmpl = get_template("tools/templates/class.tmpl")
    for module, content in modules.items():
        #print(module, len(content))
        module_name = p.joinpath(f"{module}.py")

        data = []
        for c in content:
            for r in add_class(c):
                data.append(r)
        imports = set()
        for _, _, _, classes in data:
            imports.add(classes[1].split(".")[0])

        imports = [f"{t[2:]} as {t}" for t in imports]

        #print(module_name, len(data))
        with open(module_name, 'w') as fw:
            fw.write(tmpl.render(objects=data, imports=imports))


if __name__ == "__main__":
    import sys
    import yaml

    compile(aggregate(extract(sys.argv[1])), Path(sys.argv[2]))
    #    print()
    #    print(yaml.safe_dump(k, default_flow_style=None))


