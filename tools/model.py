import re
from typing import NamedTuple
RE_MODEL = re.compile("^.*[.](apis?|pkg)[.]")


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


def make_prop_name(p_name):
    if p_name == 'continue':
        return 'continue_'
    return p_name


def get_module_from_property_def(defi):
    if '$ref' in defi:
        return Import(".", schema_name(defi['$ref']).module)
    elif 'items' in defi and '$ref' in defi['items']:
        return Import(".", schema_name(defi['items']['$ref']).module)


class Import(NamedTuple):
    from_module: str
    module: str


class Property(NamedTuple):
    name: str
    type: str
    required: bool
    import_module: Import

    @property
    def default_repr(self):
        return ' = None' if not self.required else ''


class Model:
    def __init__(self, name, defi):
        sc = schema_name(name)
        self.module = sc.module
        self.name = sc.name
        self.import_module = None
        self.type = None
        if 'properties' in defi:
            self.properties = self.get_props(defi)
        else:
            self.properties = None
            if 'type' not in defi:  # reference to any json type
                self.type = 'Any'
                self.import_module = Import('typing', 'Any')
            elif defi['type'] == 'object':
                self.type = 'Dict'
                self.import_module = Import('typing', 'Dict')
            elif defi['type'] == 'string':
                if 'format' not in defi:
                    self.type = 'str'
                elif defi['format'] == 'date-time':
                    self.type = 'str'

    @property
    def has_properties(self):
        return bool(self.properties)

    def get_props(self, defi):
        required = set(defi.get('required', []))
        properties = []
        for p_name, p_defi in defi['properties'].items():
            req = p_name in required
            p_type = self.to_pytype(p_defi, required=req)
            properties.append(Property(
                name=make_prop_name(p_name),
                type=p_type,
                required=req,
                import_module=get_module_from_property_def(p_defi)
            ))

        properties.sort(key=lambda x: x.required, reverse=True)
        return properties

    def to_pytype(self, defi, required=True):
        if not required:
            return self.to_pytype(defi)
        if 'items' in defi:
            return f'List[{self.to_pytype(defi["items"])}]'

        if '$ref' in defi:
            sc = schema_name(defi['$ref'])
            if sc.module == self.module:
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
